"""
Unit and Integration Tests for Speech-to-Text (STT) Audio Ingestion & Deepgram Provider.

Tests cover:
- Valid audio ingestion (MP3 and WAV)
- Audio format validation (rejection of non-MP3/WAV)
- Empty audio file validation
- Deepgram response conversion to CanonicalTranscript
- Speaker role mapping (including explicit inversion where speaker 0 != AGENT)
- Deterministic utterance IDs ('utt_001', 'utt_002', ...)
- Monotonic timestamps and validity
- Word-level timestamps preservation
- Audio ingestion_id integration directly into existing /api/v1/qa/run pipeline
- Deepgram API and Auth failure handling (502 / 503)
- Security assertion: DEEPGRAM_API_KEY never leaks into responses or errors
"""

import io
from typing import Any, Dict
from fastapi.testclient import TestClient
import httpx
import pytest

from app.api.app import app
from app.api import routes
from app.api.ingestion_store import ingestion_store
from app.models import CanonicalTranscript
from app.stt.adapter import DeepgramAdapter
from app.stt.base import BaseSTTClient
from app.stt.deepgram_client import DeepgramSTTClient
from app.stt.exceptions import DeepgramAPIError, DeepgramAuthError


# Mock Deepgram JSON Response fixture
MOCK_DEEPGRAM_RESPONSE: Dict[str, Any] = {
    "metadata": {
        "duration": 14.85,
        "channels": 1,
        "model_info": {"name": "nova-2"},
    },
    "results": {
        "channels": [
            {
                "alternatives": [
                    {
                        "transcript": "Hello, thank you for calling Tangent Broadband. This call may be recorded.",
                        "confidence": 0.99,
                        "words": [
                            {"word": "hello", "start": 0.42, "end": 0.95, "confidence": 0.99, "speaker": 0, "punctuated_word": "Hello,"},
                            {"word": "thank", "start": 1.02, "end": 1.30, "confidence": 0.98, "speaker": 0, "punctuated_word": "thank"},
                            {"word": "you", "start": 1.32, "end": 1.45, "confidence": 0.99, "speaker": 0, "punctuated_word": "you"},
                            {"word": "for", "start": 1.48, "end": 1.62, "confidence": 0.99, "speaker": 0, "punctuated_word": "for"},
                            {"word": "calling", "start": 1.65, "end": 1.95, "confidence": 0.99, "speaker": 0, "punctuated_word": "calling"},
                            {"word": "tangent", "start": 2.05, "end": 2.45, "confidence": 0.97, "speaker": 0, "punctuated_word": "Tangent"},
                            {"word": "broadband", "start": 2.50, "end": 2.95, "confidence": 0.98, "speaker": 0, "punctuated_word": "Broadband."},
                        ],
                    }
                ]
            }
        ],
        "utterances": [
            {
                "start": 0.42,
                "end": 3.10,
                "confidence": 0.98,
                "channel": 0,
                "transcript": "Hello, thank you for calling Tangent Broadband. This call may be recorded.",
                "speaker": 0,
                "words": [
                    {"word": "hello", "start": 0.42, "end": 0.95, "confidence": 0.99, "speaker": 0, "punctuated_word": "Hello,"},
                    {"word": "thank", "start": 1.02, "end": 1.30, "confidence": 0.98, "speaker": 0, "punctuated_word": "thank"},
                    {"word": "you", "start": 1.32, "end": 1.45, "confidence": 0.99, "speaker": 0, "punctuated_word": "you"},
                    {"word": "for", "start": 1.48, "end": 1.62, "confidence": 0.99, "speaker": 0, "punctuated_word": "for"},
                    {"word": "calling", "start": 1.65, "end": 1.95, "confidence": 0.99, "speaker": 0, "punctuated_word": "calling"},
                    {"word": "tangent", "start": 2.05, "end": 2.45, "confidence": 0.97, "speaker": 0, "punctuated_word": "Tangent"},
                    {"word": "broadband", "start": 2.50, "end": 2.95, "confidence": 0.98, "speaker": 0, "punctuated_word": "Broadband."},
                ],
            },
            {
                "start": 3.80,
                "end": 7.50,
                "confidence": 0.96,
                "channel": 0,
                "transcript": "Hi, my current provider is Telstra and I want to switch my service.",
                "speaker": 1,
                "words": [
                    {"word": "hi", "start": 3.80, "end": 4.10, "confidence": 0.99, "speaker": 1, "punctuated_word": "Hi,"},
                    {"word": "my", "start": 4.15, "end": 4.30, "confidence": 0.98, "speaker": 1, "punctuated_word": "my"},
                    {"word": "current", "start": 4.35, "end": 4.70, "confidence": 0.97, "speaker": 1, "punctuated_word": "current"},
                    {"word": "provider", "start": 4.75, "end": 5.15, "confidence": 0.98, "speaker": 1, "punctuated_word": "provider"},
                    {"word": "is", "start": 5.20, "end": 5.35, "confidence": 0.99, "speaker": 1, "punctuated_word": "is"},
                    {"word": "telstra", "start": 5.40, "end": 5.85, "confidence": 0.98, "speaker": 1, "punctuated_word": "Telstra"},
                ],
            },
        ],
    },
}


class MockSTTClient(BaseSTTClient):
    """Deterministic offline STT client for tests."""

    def __init__(self, response_data: Optional[Dict[str, Any]] = None, fail_with: Optional[Exception] = None):
        self.response_data = response_data or MOCK_DEEPGRAM_RESPONSE
        self.fail_with = fail_with
        self.calls = []

    def transcribe(self, audio_bytes: bytes, mime_type: str = "audio/wav", **kwargs: Any) -> Dict[str, Any]:
        self.calls.append({"bytes_len": len(audio_bytes), "mime_type": mime_type, "kwargs": kwargs})
        if self.fail_with:
            raise self.fail_with
        return self.response_data


@pytest.fixture(autouse=True)
def clean_ingestion_store_and_stt():
    """Reset store and mock STT client before each test."""
    ingestion_store.clear()
    routes._stt_client_override = None
    yield
    ingestion_store.clear()
    routes._stt_client_override = None


# 1. Deepgram Response Conversion Tests
def test_deepgram_adapter_response_conversion():
    adapter = DeepgramAdapter()
    canonical = adapter.to_canonical_transcript(
        deepgram_response=MOCK_DEEPGRAM_RESPONSE,
        transcript_id="call_test_01",
    )

    assert isinstance(canonical, CanonicalTranscript)
    assert canonical.transcript_id == "call_test_01"
    assert len(canonical.utterances) == 2

    # Utterance IDs check
    assert canonical.utterances[0].utterance_id == "utt_001"
    assert canonical.utterances[1].utterance_id == "utt_002"

    # Default speaker roles
    assert canonical.utterances[0].speaker == "AGENT"
    assert canonical.utterances[1].speaker == "CUSTOMER"

    # Timestamps
    assert canonical.utterances[0].start_time == 0.42
    assert canonical.utterances[0].end_time == 3.10
    assert canonical.utterances[1].start_time == 3.80
    assert canonical.utterances[1].end_time == 7.50

    # Text content
    assert "Tangent Broadband" in canonical.utterances[0].text
    assert "Telstra" in canonical.utterances[1].text

    # Word-level timestamps
    words0 = canonical.utterances[0].words
    assert words0 is not None
    assert len(words0) == 7
    assert words0[0].word == "Hello,"
    assert words0[0].start_time == 0.42
    assert words0[0].end_time == 0.95
    assert words0[0].confidence == 0.99


# 2. Speaker Mapping Tests (Do not assume speaker 0 is always AGENT)
def test_deepgram_adapter_speaker_mapping_inversion():
    adapter = DeepgramAdapter()
    # Invert mapping: speaker 0 is CUSTOMER, speaker 1 is AGENT
    canonical = adapter.to_canonical_transcript(
        deepgram_response=MOCK_DEEPGRAM_RESPONSE,
        speaker_0_role="CUSTOMER",
        speaker_1_role="AGENT",
    )

    assert canonical.utterances[0].speaker == "CUSTOMER"
    assert canonical.utterances[1].speaker == "AGENT"


def test_deepgram_adapter_custom_role_map():
    adapter = DeepgramAdapter()
    canonical = adapter.to_canonical_transcript(
        deepgram_response=MOCK_DEEPGRAM_RESPONSE,
        speaker_role_map={0: "SUPERVISOR", 1: "PROSPECT"},
    )

    assert canonical.utterances[0].speaker == "SUPERVISOR"
    assert canonical.utterances[1].speaker == "PROSPECT"


# 3. Client Unit Tests (Mocked HTTP transport)
def test_deepgram_client_missing_api_key(monkeypatch):
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    client = DeepgramSTTClient(api_key="")

    with pytest.raises(DeepgramAuthError) as exc_info:
        client.transcribe(b"fake_audio_bytes")

    assert "Deepgram API key not configured" in str(exc_info.value)


def test_deepgram_client_missing_api_key_makes_no_http_request(monkeypatch):
    """Verify that no HTTP request is made when the API key is missing or empty."""
    http_called = False

    def mock_handler(request: httpx.Request):
        nonlocal http_called
        http_called = True
        return httpx.Response(200, json={})

    transport = httpx.MockTransport(mock_handler)
    http_client = httpx.Client(transport=transport)

    # 1. Explicit empty string
    client_empty = DeepgramSTTClient(api_key="", http_client=http_client)
    with pytest.raises(DeepgramAuthError):
        client_empty.transcribe(b"fake_audio_bytes")
    assert not http_called, "HTTP request was unexpectedly made for empty api_key"

    # 2. Whitespace-only string
    client_ws = DeepgramSTTClient(api_key="   ", http_client=http_client)
    with pytest.raises(DeepgramAuthError):
        client_ws.transcribe(b"fake_audio_bytes")
    assert not http_called, "HTTP request was unexpectedly made for whitespace api_key"

    # 3. None with environment variable removed
    monkeypatch.delenv("DEEPGRAM_API_KEY", raising=False)
    client_none = DeepgramSTTClient(api_key=None, http_client=http_client)
    with pytest.raises(DeepgramAuthError):
        client_none.transcribe(b"fake_audio_bytes")
    assert not http_called, "HTTP request was unexpectedly made for missing environment API key"


def test_deepgram_client_mocked_http_success():
    def mock_handler(request: httpx.Request):
        assert request.headers.get("authorization") == "Token test_token_xyz"
        assert request.content == b"fake_wav_bytes"
        return httpx.Response(200, json=MOCK_DEEPGRAM_RESPONSE)

    transport = httpx.MockTransport(mock_handler)
    http_client = httpx.Client(transport=transport)

    client = DeepgramSTTClient(api_key="test_token_xyz", http_client=http_client)
    res = client.transcribe(b"fake_wav_bytes", mime_type="audio/wav")

    assert res["metadata"]["duration"] == 14.85
    assert len(res["results"]["utterances"]) == 2


def test_deepgram_client_mocked_http_auth_failure():
    def mock_handler(request: httpx.Request):
        return httpx.Response(401, json={"err_msg": "Invalid credentials"})

    transport = httpx.MockTransport(mock_handler)
    http_client = httpx.Client(transport=transport)

    client = DeepgramSTTClient(api_key="bad_token", http_client=http_client)
    with pytest.raises(DeepgramAuthError) as exc_info:
        client.transcribe(b"fake_wav_bytes")

    assert "authentication failed" in str(exc_info.value).lower()


def test_deepgram_client_mocked_http_api_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(500, json={"message": "Internal error in engine"})

    transport = httpx.MockTransport(mock_handler)
    http_client = httpx.Client(transport=transport)

    client = DeepgramSTTClient(api_key="test_token", http_client=http_client)
    with pytest.raises(DeepgramAPIError) as exc_info:
        client.transcribe(b"fake_wav_bytes")

    assert "HTTP 500" in str(exc_info.value)
    assert exc_info.value.status_code == 500


# 4. Audio Ingestion API Endpoint Tests
def test_audio_ingest_endpoint_valid_wav():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    wav_content = b"RIFF\x24\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00D\xac\x00\x00"
    files = {"file": ("call_sample.wav", io.BytesIO(wav_content), "audio/wav")}
    data = {
        "retailer": "TANGENT_BROADBAND",
        "call_date": "2026-09-19",
        "speaker_0_role": "AGENT",
        "speaker_1_role": "CUSTOMER",
    }

    res = client.post("/api/v1/ingest/audio", files=files, data=data)
    assert res.status_code == 201
    body = res.json()

    assert "ingestion_id" in body
    assert body["ingestion_id"].startswith("ingest_")
    assert body["status"] == "ready"
    assert body["source_type"] == "audio"
    assert body["utterance_count"] == 2
    assert body["duration_seconds"] == 14.85
    assert body["retailer"] == "TANGENT_BROADBAND"
    assert body["call_date"] == "2026-09-19"
    assert body["transcript"] is not None
    assert len(body["transcript"]["utterances"]) == 2


def test_audio_ingest_endpoint_valid_mp3():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    mp3_content = b"ID3\x03\x00\x00\x00\x00\x00\x00\xff\xfb\x90\x00"
    files = {"file": ("recording.mp3", io.BytesIO(mp3_content), "audio/mpeg")}

    res = client.post("/api/v1/ingest/audio", files=files)
    assert res.status_code == 201
    body = res.json()

    assert body["status"] == "ready"
    assert body["source_type"] == "audio"
    assert body["utterance_count"] == 2


def test_audio_ingest_endpoint_invalid_format():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    files = {"file": ("transcript.txt", io.BytesIO(b"Hello world"), "text/plain")}
    res = client.post("/api/v1/ingest/audio", files=files)

    assert res.status_code == 400
    assert "Only MP3 and WAV files are supported" in res.json()["detail"]


def test_audio_ingest_endpoint_empty_file():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    files = {"file": ("empty.wav", io.BytesIO(b""), "audio/wav")}
    res = client.post("/api/v1/ingest/audio", files=files)

    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_audio_ingest_endpoint_missing_file():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    res = client.post(
        "/api/v1/ingest/audio",
        data={"retailer": "TANGENT_BROADBAND"},
        files={"other_field": ("note.txt", io.BytesIO(b"abc"), "text/plain")},
    )
    assert res.status_code == 400
    assert "Missing 'file' field" in res.json()["detail"]


def test_audio_ingest_custom_speaker_roles():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    wav_content = b"RIFF....WAVE"
    files = {"file": ("call.wav", io.BytesIO(wav_content), "audio/wav")}
    data = {
        "speaker_0_role": "CUSTOMER",
        "speaker_1_role": "AGENT",
    }

    res = client.post("/api/v1/ingest/audio", files=files, data=data)
    assert res.status_code == 201
    body = res.json()

    # Verify session store was populated with inverted roles
    record = ingestion_store.get(body["ingestion_id"])
    assert record is not None
    assert record.canonical_transcript.utterances[0].speaker == "CUSTOMER"
    assert record.canonical_transcript.utterances[1].speaker == "AGENT"


# 5. Pipeline Compatibility: audio ingestion_id -> POST /api/v1/qa/run
def test_audio_ingestion_id_seamless_with_qa_run():
    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    # Step 1: Ingest audio
    wav_content = b"RIFF....WAVE"
    files = {"file": ("call.wav", io.BytesIO(wav_content), "audio/wav")}
    data = {
        "retailer": "TANGENT_BROADBAND",
        "call_date": "2026-09-19",
    }
    ingest_res = client.post("/api/v1/ingest/audio", files=files, data=data)
    assert ingest_res.status_code == 201
    ingestion_id = ingest_res.json()["ingestion_id"]

    # Step 2: Feed directly to existing POST /api/v1/qa/run without modifications
    qa_res = client.post(
        "/api/v1/qa/run",
        json={
            "ingestion_id": ingestion_id,
            "retailer": "TANGENT_BROADBAND",
            "call_date": "2026-09-19",
        },
    )
    assert qa_res.status_code == 200
    qa_body = qa_res.json()

    assert "decision" in qa_body
    assert qa_body["decision"] in ("AUTO_SUBMIT", "HOLD", "QA_REVIEW")
    assert "check_results" in qa_body
    assert len(qa_body["check_results"]) > 0

    # Step 3: GET /api/v1/transcript with ingestion_id also works
    t_res = client.get(f"/api/v1/transcript?ingestion_id={ingestion_id}")
    assert t_res.status_code == 200
    t_body = t_res.json()
    assert len(t_body["utterances"]) == 2


# 6. Deepgram Service Failure Tests
def test_audio_ingest_deepgram_auth_failure_status_503():
    routes._stt_client_override = MockSTTClient(
        fail_with=DeepgramAuthError("Authentication failed")
    )
    client = TestClient(app)

    files = {"file": ("call.wav", io.BytesIO(b"RIFF....WAVE"), "audio/wav")}
    res = client.post("/api/v1/ingest/audio", files=files)

    assert res.status_code == 503
    assert "unavailable" in res.json()["detail"].lower()


def test_audio_ingest_deepgram_api_failure_status_502():
    routes._stt_client_override = MockSTTClient(
        fail_with=DeepgramAPIError("Rate limit exceeded", status_code=429)
    )
    client = TestClient(app)

    files = {"file": ("call.wav", io.BytesIO(b"RIFF....WAVE"), "audio/wav")}
    res = client.post("/api/v1/ingest/audio", files=files)

    assert res.status_code == 502
    assert "Rate limit exceeded" in res.json()["detail"]


# 7. Security Assertion: API Key Never Appears in Responses
def test_deepgram_api_key_never_appears_in_responses(monkeypatch):
    canary_key = "super_secret_deepgram_key_999988887777"
    monkeypatch.setenv("DEEPGRAM_API_KEY", canary_key)

    routes._stt_client_override = MockSTTClient()
    client = TestClient(app)

    # Test audio upload
    files = {"file": ("call.wav", io.BytesIO(b"RIFF....WAVE"), "audio/wav")}
    res = client.post("/api/v1/ingest/audio", files=files)
    assert canary_key not in res.text
    for h_val in res.headers.values():
        assert canary_key not in h_val

    # Test error condition
    routes._stt_client_override = MockSTTClient(
        fail_with=DeepgramAuthError("Invalid credentials provided")
    )
    err_res = client.post("/api/v1/ingest/audio", files=files)
    assert canary_key not in err_res.text
    for h_val in err_res.headers.values():
        assert canary_key not in h_val
