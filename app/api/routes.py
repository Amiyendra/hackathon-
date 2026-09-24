"""
FastAPI Routes for Deterministic QA Gate Layer & Ingestion Boundary.

All evaluation logic is delegated to the existing QAPipeline / DeterministicGate.
This layer strictly handles request validation, ingestion, error formatting, and routing.
"""

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Header, HTTPException, Request, status

from app.api.ingestion_store import ingestion_store
from app.api.models import (
    AudioIngestionResponse,
    HealthResponse,
    IngestionResponse,
    QARunRequest,
    ScenarioInfo,
)
from app.gate import DeterministicGate
from app.gate.models import GateResult
from app.ingestion.normalizer import TranscriptNormalizationError, TranscriptNormalizer
from app.models import CanonicalTranscript
from app.stt import (
    BaseSTTClient,
    DeepgramAdapter,
    DeepgramAPIError,
    DeepgramAuthError,
    DeepgramSTTClient,
)
from app.pipeline.orchestrator import (
    QAPipeline,
    load_default_broadband_ground_truth,
    load_default_broadband_library,
)

router = APIRouter()

# Default project assets
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_TRANSCRIPT_PATH = PROJECT_ROOT / "data" / "broadband_transcript.json"

# Max allowed transcript upload size (5 MB)
MAX_TRANSCRIPT_SIZE_BYTES = 5 * 1024 * 1024

# Max allowed audio upload size (50 MB)
MAX_AUDIO_SIZE_BYTES = 50 * 1024 * 1024

# STT Client resolver (allows test injection / mocking)
_stt_client_override: Optional[BaseSTTClient] = None


def get_stt_client() -> BaseSTTClient:
    """Resolve STT client instance (supports test mocking and dependency injection)."""
    if _stt_client_override is not None:
        return _stt_client_override
    return DeepgramSTTClient()

# Pre-cached library and ground truth for efficiency
_DEFAULT_LIBRARY = load_default_broadband_library(PROJECT_ROOT)
_DEFAULT_GROUND_TRUTH = load_default_broadband_ground_truth(PROJECT_ROOT)

# Auto-submit target checks (verified passing critical checks + non-blocking behaviour)
AUTO_SUBMIT_TARGET_IDS: List[str] = [
    "CHK_FACT_BB_001_CURRENT_PROVIDER",
    "CHK_FACT_BB_002_CUSTOMER_NAME",
    "CHK_FACT_BB_003_SERVICE_ADDRESS",
    "CHK_FACT_BB_004_DOWNLOAD_SPEED",
    "CHK_FACT_BB_005_UPLOAD_SPEED",
    "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
    "CHK_FACT_BB_007_PROMOTIONAL_PERIOD",
    "CHK_FACT_BB_008_REGULAR_PRICE",
    "CHK_FACT_BB_010_MODEM_COST",
    "CHK_FACT_BB_013_MINIMUM_COST",
    "CHK_FACT_BB_016_TECHNOLOGY_TYPE",
    "CHK_VERB_BB_001_GREETING_BRAND",
    "CHK_VERB_BB_002_STATUTORY_MIN_COST",
    "CHK_BEHAV_BB_001_DEAD_AIR",
    "CHK_BEHAV_BB_002_DEAD_AIR_STRICT",  # Non-blocking failure
    "CHK_BEHAV_BB_003_INTERRUPTIONS",
]

SUPPORTED_SCENARIOS: Dict[str, ScenarioInfo] = {
    "default": ScenarioInfo(
        scenario_id="default",
        name="Full Broadband Lead Evaluation",
        description="Evaluates all active Tangent Broadband checks against the full synthetic lead.",
        expected_decision="HOLD",
    ),
    "auto_submit": ScenarioInfo(
        scenario_id="auto_submit",
        name="Compliant Sale with Non-Blocking Warning",
        description="All critical checks pass with verified evidence, plus a strict dead-air warning. Auto-submits.",
        expected_decision="AUTO_SUBMIT",
    ),
    "hold": ScenarioInfo(
        scenario_id="hold",
        name="Rate-Card Pricing Mismatch",
        description="Promotional price quoted in transcript ($42.90) fails rate-card check ($55.00). Holds lead.",
        expected_decision="HOLD",
    ),
    "qa_review": ScenarioInfo(
        scenario_id="qa_review",
        name="Unsupported Recording Disclosure",
        description="Evaluates unsupported disclosure check, safely failing closed to human QA review.",
        expected_decision="QA_REVIEW",
    ),
}


@router.get("/health", response_model=HealthResponse, tags=["System"])
def health_check() -> HealthResponse:
    """System health and operational status endpoint."""
    provider_name = (
        "Anthropic Claude"
        if os.environ.get("FACTUAL_LLM_PROVIDER", "").strip().lower() == "anthropic"
        else "MockLLMClient (Offline)"
    )
    return HealthResponse(
        status="ok",
        service="qa-gate-backend",
        version="1.0.0",
        checks_loaded=len(_DEFAULT_LIBRARY.checks),
        default_provider=provider_name,
    )


@router.get("/api/v1/scenarios", response_model=List[ScenarioInfo], tags=["Scenarios"])
def list_scenarios() -> List[ScenarioInfo]:
    """List available pre-configured deterministic demonstration scenarios."""
    return list(SUPPORTED_SCENARIOS.values())


@router.get("/api/v1/retailers", tags=["Retailers"])
def list_retailers() -> List[str]:
    """List all retailer codes available in loaded check libraries."""
    return sorted(list(set(c.retailer for c in _DEFAULT_LIBRARY.checks)))


@router.get("/api/v1/checks", tags=["Checks"])
def list_checks() -> List[Dict[str, Any]]:
    """List all loaded QA check definitions from the check library."""
    return [
        {
            "check_id": c.check_id,
            "retailer": c.retailer,
            "name": c.name,
            "type": c.type.value,
            "version": c.version,
            "critical": c.critical,
            "description": c.description,
            "criteria": c.criteria,
        }
        for c in _DEFAULT_LIBRARY.checks
    ]


@router.post(
    "/api/v1/ingest/transcript",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestion"],
)
async def ingest_transcript(request: Request) -> IngestionResponse:
    """
    Ingest and canonically normalize a transcript file or JSON payload.
    
    Accepts:
    - multipart/form-data with a .json file (and optional lead_id, retailer, call_date)
    - application/json with a transcript object / utterances array
    
    Validates:
    - Payload size (<= 5MB)
    - Malformed JSON detection
    - Required utterance fields (speaker, text, timestamps)
    - Monotonically non-decreasing timestamps
    - Canonical normalization
    """
    content_type = request.headers.get("content-type", "").lower()
    override_lead_id: Optional[str] = None
    override_retailer: Optional[str] = None
    override_call_date: Optional[str] = None
    raw_data: Any = None

    if "multipart/form-data" in content_type:
        form = await request.form()
        file_field = form.get("file")
        if not file_field or not hasattr(file_field, "read"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Missing 'file' field in multipart/form-data upload.",
            )

        content = await file_field.read()
        if len(content) > MAX_TRANSCRIPT_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Uploaded file exceeds maximum allowed size of {MAX_TRANSCRIPT_SIZE_BYTES // (1024*1024)}MB.",
            )

        try:
            raw_text = content.decode("utf-8")
            raw_data = json.loads(raw_text)
        except UnicodeDecodeError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Uploaded file is not valid UTF-8 text: {err}",
            )
        except json.JSONDecodeError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed JSON transcript file: {err}",
            )

        # Form metadata overrides
        lead_id_form = form.get("lead_id")
        retailer_form = form.get("retailer")
        call_date_form = form.get("call_date")
        if lead_id_form and str(lead_id_form).strip():
            override_lead_id = str(lead_id_form).strip()
        if retailer_form and str(retailer_form).strip():
            override_retailer = str(retailer_form).strip().upper()
        if call_date_form and str(call_date_form).strip():
            override_call_date = str(call_date_form).strip()

    elif "application/json" in content_type:
        body = await request.body()
        if len(body) > MAX_TRANSCRIPT_SIZE_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Payload exceeds maximum allowed size of {MAX_TRANSCRIPT_SIZE_BYTES // (1024*1024)}MB.",
            )
        try:
            raw_data = json.loads(body.decode("utf-8"))
        except json.JSONDecodeError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Malformed JSON transcript: {err}",
            )
        if isinstance(raw_data, dict):
            if "lead_id" in raw_data and raw_data["lead_id"]:
                override_lead_id = str(raw_data["lead_id"]).strip()
            if "retailer" in raw_data and raw_data["retailer"]:
                override_retailer = str(raw_data["retailer"]).strip().upper()
            if "call_date" in raw_data and raw_data["call_date"]:
                override_call_date = str(raw_data["call_date"]).strip()
    else:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type. Expected multipart/form-data or application/json.",
        )

    # Validate structural payload
    if not isinstance(raw_data, (dict, list)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript JSON must be an object or array of utterances, got {type(raw_data).__name__}.",
        )

    raw_utterances: List[Any] = (
        raw_data if isinstance(raw_data, list) else raw_data.get("utterances", [])
    )
    if not isinstance(raw_utterances, list) or len(raw_utterances) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Transcript contains no utterances.",
        )

    # Validate monotonically valid timing across utterances
    prev_start = -1.0
    for idx, u in enumerate(raw_utterances, start=1):
        if not isinstance(u, dict):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Utterance at index {idx} must be a dictionary.",
            )
        st_raw = u.get("start_time")
        et_raw = u.get("end_time")
        if st_raw is None or et_raw is None or isinstance(st_raw, bool) or isinstance(et_raw, bool):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Utterance at index {idx} is missing valid numeric start_time or end_time.",
            )
        try:
            st = float(st_raw)
            et = float(et_raw)
        except (ValueError, TypeError) as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Utterance at index {idx} has invalid timestamp: {err}",
            )
        if st < 0.0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Utterance at index {idx} has negative start_time ({st}).",
            )
        if et < st:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Utterance at index {idx} end_time ({et}) cannot precede start_time ({st}).",
            )
        if st < prev_start:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Utterance at index {idx} start_time ({st}s) occurs before previous utterance start_time "
                    f"({prev_start}s). Timestamps must be monotonically non-decreasing."
                ),
            )
        prev_start = st

    # Canonical Normalization through existing domain normalizer
    normalizer = TranscriptNormalizer()
    try:
        canonical = normalizer.normalize(raw_data)
    except TranscriptNormalizationError as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Transcript normalization error: {err}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to normalize transcript: {err}",
        )

    # Extract metadata strictly from transcript or explicit overrides (never invent)
    call_metadata: Dict[str, Any] = (
        raw_data.get("call_metadata", {}) if isinstance(raw_data, dict) else {}
    )
    resolved_lead_id = (
        override_lead_id
        or call_metadata.get("lead_id")
        or call_metadata.get("call_id")
        or (canonical.transcript_id if canonical.transcript_id else None)
    )
    resolved_retailer = (
        override_retailer
        or call_metadata.get("retailer")
        or call_metadata.get("provider")
    )
    if resolved_retailer:
        resolved_retailer = str(resolved_retailer).strip().upper()

    resolved_call_date = (
        override_call_date
        or call_metadata.get("call_date")
    )

    # Save into thread-safe session store
    record = ingestion_store.save(
        canonical_transcript=canonical,
        raw_data=raw_data if isinstance(raw_data, dict) else {"utterances": raw_data},
        lead_id=resolved_lead_id,
        retailer=resolved_retailer,
        call_date=resolved_call_date,
    )

    return IngestionResponse(
        ingestion_id=record.ingestion_id,
        lead_id=record.lead_id,
        retailer=record.retailer,
        call_date=record.call_date,
        utterance_count=len(canonical.utterances),
        status="READY_FOR_QA",
        transcript=canonical,
    )


@router.post(
    "/api/v1/ingest/audio",
    response_model=AudioIngestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["Ingestion"],
)
async def ingest_audio(request: Request) -> AudioIngestionResponse:
    """
    Ingest, transcribe, and canonically normalize a prerecorded audio file (MP3/WAV).

    Accepts:
    multipart/form-data:
    - file: MP3 or WAV audio file
    - retailer: Optional retailer code (e.g. TANGENT_BROADBAND)
    - call_date: Optional call date (YYYY-MM-DD)
    - speaker_0_role: Role assigned to Deepgram speaker 0 (default: AGENT)
    - speaker_1_role: Role assigned to Deepgram speaker 1 (default: CUSTOMER)
    - lead_id: Optional lead identifier

    Validates:
    - Content-Type is multipart/form-data
    - 'file' field exists and is not empty
    - Audio format is strictly MP3 or WAV
    - File size is <= 50MB

    Flow:
    audio → Deepgram transcription → canonical transcript → existing ingestion_store → ingestion_id

    Returns:
    AudioIngestionResponse with ingestion_id compatible with /api/v1/qa/run.
    """
    content_type = request.headers.get("content-type", "").lower()
    if "multipart/form-data" not in content_type:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Unsupported content type. Expected multipart/form-data.",
        )

    try:
        form = await request.form()
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse multipart form data: {err}",
        )

    file_field = form.get("file")
    if not file_field or not hasattr(file_field, "read"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Missing 'file' field in multipart/form-data upload.",
        )

    filename = getattr(file_field, "filename", "") or ""
    filename_lower = filename.lower().strip()
    if not (filename_lower.endswith(".mp3") or filename_lower.endswith(".wav")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid audio format for '{filename}'. Only MP3 and WAV files are supported.",
        )

    content = await file_field.read()
    if len(content) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded audio file is empty.",
        )

    if len(content) > MAX_AUDIO_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Uploaded audio file exceeds maximum allowed size of {MAX_AUDIO_SIZE_BYTES // (1024 * 1024)}MB.",
        )

    # Determine audio MIME type
    if filename_lower.endswith(".mp3"):
        mime_type = "audio/mpeg"
    else:
        mime_type = "audio/wav"

    # Speaker role mappings (defaults: speaker_0 = AGENT, speaker_1 = CUSTOMER)
    spk0_raw = form.get("speaker_0_role")
    spk1_raw = form.get("speaker_1_role")
    spk0_role = str(spk0_raw).strip().upper() if spk0_raw and str(spk0_raw).strip() else "AGENT"
    spk1_role = str(spk1_raw).strip().upper() if spk1_raw and str(spk1_raw).strip() else "CUSTOMER"

    # Retailer, call date, and lead ID overrides
    retailer_form = form.get("retailer")
    call_date_form = form.get("call_date")
    lead_id_form = form.get("lead_id")

    resolved_retailer = str(retailer_form).strip().upper() if retailer_form and str(retailer_form).strip() else None
    resolved_call_date = str(call_date_form).strip() if call_date_form and str(call_date_form).strip() else None
    resolved_lead_id = str(lead_id_form).strip() if lead_id_form and str(lead_id_form).strip() else None

    # Step 1: Transcribe via Deepgram STT
    stt_client = get_stt_client()
    try:
        dg_response = stt_client.transcribe(audio_bytes=content, mime_type=mime_type)
    except DeepgramAuthError as err:
        # Crucial security guarantee: never expose raw API keys in responses
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Deepgram STT service unavailable — API key not configured or authentication failed.",
        )
    except DeepgramAPIError as err:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Deepgram STT transcription service error: {err}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Deepgram audio transcription failed: {err}",
        )

    # Step 2: Convert to canonical transcript
    adapter = DeepgramAdapter()
    try:
        canonical = adapter.to_canonical_transcript(
            deepgram_response=dg_response,
            transcript_id=resolved_lead_id,
            speaker_0_role=spk0_role,
            speaker_1_role=spk1_role,
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to normalize Deepgram transcription into canonical transcript: {err}",
        )

    # Step 3: Save into thread-safe session store
    record = ingestion_store.save(
        canonical_transcript=canonical,
        raw_data=dg_response,
        lead_id=resolved_lead_id or canonical.transcript_id,
        retailer=resolved_retailer,
        call_date=resolved_call_date,
    )

    # Calculate duration
    duration = canonical.duration
    metadata = dg_response.get("metadata", {}) if isinstance(dg_response, dict) else {}
    if isinstance(metadata, dict) and "duration" in metadata:
        try:
            meta_dur = float(metadata["duration"])
            if meta_dur > duration:
                duration = meta_dur
        except (ValueError, TypeError):
            pass

    return AudioIngestionResponse(
        ingestion_id=record.ingestion_id,
        status="ready",
        source_type="audio",
        utterance_count=len(canonical.utterances),
        duration_seconds=round(duration, 2),
        lead_id=record.lead_id,
        retailer=record.retailer,
        call_date=record.call_date,
        transcript=canonical,
    )


@router.get("/api/v1/transcript", tags=["Transcript"])
def get_transcript(ingestion_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Retrieve the canonical transcript for the active ingestion session or default lead.
    """
    if ingestion_id:
        record = ingestion_store.get(ingestion_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingestion session '{ingestion_id}' not found or expired.",
            )
        return {
            "transcript_id": record.canonical_transcript.transcript_id,
            "lead_id": record.lead_id,
            "retailer": record.retailer,
            "call_date": record.call_date,
            "call_metadata": record.raw_data.get("call_metadata", {}) if record.raw_data else {},
            "utterances": [u.model_dump() for u in record.canonical_transcript.utterances],
        }

    if not DEFAULT_TRANSCRIPT_PATH.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Default transcript not found at '{DEFAULT_TRANSCRIPT_PATH}'.",
        )
    with open(DEFAULT_TRANSCRIPT_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@router.post(
    "/api/v1/qa/run",
    response_model=GateResult,
    status_code=status.HTTP_200_OK,
    tags=["QA Evaluation"],
)
def run_qa_evaluation(
    request: QARunRequest,
    x_test_min_confidence_threshold: Optional[float] = Header(
        default=None,
        alias="X-Test-Min-Confidence-Threshold",
        include_in_schema=False,
        description="Internal test-only confidence threshold override (excluded from public schema).",
    ),
) -> GateResult:
    """
    Execute full end-to-end QA Gate evaluation of an ingested transcript or named scenario.
    
    Accepts:
    - Ingested transcript session via `ingestion_id`
    - Named deterministic scenarios ('default', 'auto_submit', 'hold', 'qa_review')
    - Custom raw transcript dict / JSON string / CanonicalTranscript
    - Optional rate-card overrides, target check IDs, retailer, and call_date
    
    Returns:
    Structured GateResult containing decision, counts, reasons, and all CheckResults.
    """
    # 1. Scenario resolution
    scenario_key = request.scenario.lower() if request.scenario else None
    if scenario_key and scenario_key not in SUPPORTED_SCENARIOS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                f"Unsupported scenario '{request.scenario}'. "
                f"Available scenarios: {list(SUPPORTED_SCENARIOS.keys())}"
            ),
        )

    # 2. Determine raw transcript source and metadata
    raw_transcript: Any = None
    resolved_lead_id: Optional[str] = request.lead_id
    resolved_retailer: Optional[str] = request.retailer
    resolved_call_date: Optional[str] = request.call_date

    if request.ingestion_id:
        record = ingestion_store.get(request.ingestion_id)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ingestion session '{request.ingestion_id}' not found or expired.",
            )
        raw_transcript = record.canonical_transcript
        resolved_lead_id = resolved_lead_id or record.lead_id
        resolved_retailer = resolved_retailer or record.retailer
        resolved_call_date = resolved_call_date or record.call_date

    elif request.transcript is not None:
        raw_transcript = request.transcript
    else:
        if not DEFAULT_TRANSCRIPT_PATH.exists():
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Default transcript not found at '{DEFAULT_TRANSCRIPT_PATH}'.",
            )
        raw_transcript = DEFAULT_TRANSCRIPT_PATH

    # 3. Determine overrides and targets based on scenario
    target_ids = request.target_check_ids
    expected_overrides = request.expected_values_override

    if scenario_key == "auto_submit" and target_ids is None:
        target_ids = AUTO_SUBMIT_TARGET_IDS
    elif scenario_key == "hold" and expected_overrides is None:
        expected_overrides = {"CHK_FACT_BB_006_PROMOTIONAL_PRICE": 55.0}
    elif scenario_key == "qa_review" and target_ids is None:
        target_ids = ["CHK_VERB_BB_003_RECORDING_DISCLOSURE"]

    # 4. Initialize pipeline (deterministic offline by default, backend threshold as source of truth)
    confidence_threshold = (
        x_test_min_confidence_threshold
        if x_test_min_confidence_threshold is not None
        else DeterministicGate.DEFAULT_MIN_CONFIDENCE
    )

    try:
        pipeline = QAPipeline(
            check_library=_DEFAULT_LIBRARY,
            ground_truth=_DEFAULT_GROUND_TRUTH,
            use_real_anthropic=request.use_real_anthropic,
            min_confidence_threshold=confidence_threshold,
        )
    except ValueError as err:
        # Clear failure when Anthropic credentials/configuration are missing
        if "Anthropic" in str(err) or "credentials" in str(err):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=str(err),
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Pipeline initialization configuration error: {err}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to initialize QA pipeline: {err}",
        )

    # 5. Execute evaluation
    try:
        gate_result = pipeline.evaluate_lead(
            raw_transcript=raw_transcript,
            retailer=resolved_retailer,
            call_date=resolved_call_date,
            expected_values_override=expected_overrides,
            target_check_ids=target_ids,
        )
        if resolved_lead_id:
            gate_result = gate_result.model_copy(update={"lead_id": resolved_lead_id})

    except (ValueError, TypeError) as err:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid or malformed transcript input: {err}",
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Pipeline evaluation error: {err}",
        )

    return gate_result
