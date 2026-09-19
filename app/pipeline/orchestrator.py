"""
End-to-End Deterministic QA Pipeline Orchestrator.

Provides the single top-level orchestration entry point:
Canonical Transcript Normalization
    ↓
EvidenceIndex Construction
    ↓
Versioned Check-Library Resolution (retailer + call_date)
    ↓
Verbatim QA Engine Evaluation
    ↓
Factual QA Engine Evaluation
    ↓
Behaviour QA Engine Evaluation
    ↓
Aggregate CheckResults Collection
    ↓
DeterministicGate Evaluation
    ↓
Final Routing: AUTO_SUBMIT / HOLD / QA_REVIEW

ARCHITECTURAL RULES:
1. Exactly one top-level orchestration entry point (QAPipeline.run / evaluate_lead).
2. The orchestrator contains ZERO business rules. Rules remain inside engines and Gate.
3. No unnecessary LLM calls. Uses MockLLMClient for offline testing.
4. Optional real-Anthropic path provided but not executed automatically.
5. Preserves every CheckResult for complete auditability.
"""

from datetime import date
import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.behaviour import BehaviourEngine
from app.checks import (
    CheckDefinition,
    CheckLibrary,
    CheckType,
    NoMatchingVersionError,
    OverlappingVersionError,
    VersionResolver,
    load_check_library_from_yaml,
)
from app.evidence.index import EvidenceIndex
from app.factual import ClaimExtractor, DeterministicComparator, FactualEngine, MockLLMClient
from app.factual.llm import BaseLLMClient
from app.factual.models import CheckResult, CheckStatus
from app.gate import DeterministicGate, GateDecision, GateResult
from app.ingestion.normalizer import TranscriptNormalizer
from app.models import CanonicalTranscript


def load_default_broadband_library(project_root: Optional[Path] = None) -> CheckLibrary:
    """Load and combine all versioned Tangent Broadband check libraries."""
    root = project_root or Path(__file__).resolve().parent.parent.parent
    checks_dir = root / "app" / "checks"

    factual_lib = load_check_library_from_yaml(checks_dir / "broadband_library.yaml")
    verbatim_lib = load_check_library_from_yaml(checks_dir / "broadband_verbatim_library.yaml")
    behaviour_lib = load_check_library_from_yaml(checks_dir / "broadband_behaviour_library.yaml")

    combined_checks: List[CheckDefinition] = (
        list(factual_lib.checks) + list(verbatim_lib.checks) + list(behaviour_lib.checks)
    )

    return CheckLibrary(
        version="1.0.0",
        description="Unified Tangent Broadband Check Library (Factual, Verbatim & Behaviour)",
        checks=combined_checks,
    )


def load_default_broadband_ground_truth(project_root: Optional[Path] = None) -> Dict[str, Any]:
    """Load default ground truth records for Tangent Broadband."""
    root = project_root or Path(__file__).resolve().parent.parent.parent
    gt_path = root / "data" / "broadband_ground_truth.json"
    with open(gt_path, "r", encoding="utf-8") as f:
        return json.load(f)


class QAPipeline:
    """
    Unified Orchestrator coordinating transcript normalization, evidence indexing,
    versioned check resolution, engine evaluations, and deterministic gate routing.
    """

    def __init__(
        self,
        check_library: Optional[CheckLibrary] = None,
        ground_truth: Optional[Dict[str, Any]] = None,
        llm_client: Optional[BaseLLMClient] = None,
        use_real_anthropic: bool = False,
        min_confidence_threshold: float = 0.80,
    ):
        self.check_library = check_library or load_default_broadband_library()
        self.ground_truth = ground_truth or load_default_broadband_ground_truth()
        self.min_confidence_threshold = min_confidence_threshold

        # Configure LLM client: Default offline MockLLMClient unless explicitly requested
        use_anthropic = (
            use_real_anthropic
            or os.environ.get("FACTUAL_LLM_PROVIDER", "").strip().lower() == "anthropic"
        )
        if llm_client is not None:
            self.llm_client = llm_client
        elif use_anthropic:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                raise ValueError(
                    "QA evaluation unavailable — configure Anthropic API credentials."
                )
            from app.factual.anthropic_client import AnthropicClient
            self.llm_client = AnthropicClient(api_key=api_key)
        else:
            self.llm_client = MockLLMClient()

        # Build ground-truth lookup table
        self._gt_lookup: Dict[str, Any] = {}
        records = self.ground_truth.get("ground_truth_records", [])
        for rec in records:
            if "check_id" in rec and "expected_value" in rec:
                self._gt_lookup[rec["check_id"]] = rec["expected_value"]

        # Instantiate sub-engines
        self.normalizer = TranscriptNormalizer()
        self.factual_engine = FactualEngine(
            extractor=ClaimExtractor(llm_client=self.llm_client),
            comparator=DeterministicComparator(),
        )
        from app.verbatim.engine import VerbatimEngine
        self.verbatim_engine = VerbatimEngine(llm_client=self.llm_client)
        self.behaviour_engine = BehaviourEngine(llm_client=self.llm_client)

    def evaluate_lead(
        self,
        raw_transcript: Union[Dict[str, Any], str, Path, CanonicalTranscript],
        retailer: Optional[str] = None,
        call_date: Optional[Union[str, date]] = None,
        expected_values_override: Optional[Dict[str, Any]] = None,
        target_check_ids: Optional[List[str]] = None,
    ) -> GateResult:
        """
        Execute full end-to-end evaluation of a lead interaction.
        
        Args:
            raw_transcript: Raw transcript dictionary, JSON filepath, JSON string, or CanonicalTranscript.
            retailer: Optional explicit retailer code (defaults to transcript metadata if omitted).
            call_date: Optional explicit call date (defaults to transcript metadata if omitted).
            expected_values_override: Optional expected value overrides for testing.
            target_check_ids: Optional list of check IDs to evaluate (defaults to all active checks).
            
        Returns:
            Final deterministic GateResult with decision, counts, reasons, and all CheckResults.
        """
        # 1. Ingestion & Canonical Normalization
        raw_data: Optional[Dict[str, Any]] = None
        if isinstance(raw_transcript, CanonicalTranscript):
            canonical = raw_transcript
        elif isinstance(raw_transcript, (str, Path)):
            path = Path(raw_transcript)
            if path.exists():
                with open(path, "r", encoding="utf-8") as f:
                    raw_data = json.load(f)
            else:
                raw_data = json.loads(str(raw_transcript))
            canonical = self.normalizer.normalize(raw_data)
        elif isinstance(raw_transcript, dict):
            raw_data = raw_transcript
            canonical = self.normalizer.normalize(raw_data)
        else:
            raise ValueError(f"Unsupported transcript type: {type(raw_transcript).__name__}")

        lead_id = canonical.transcript_id
        if not lead_id and raw_data and isinstance(raw_data, dict):
            metadata = raw_data.get("call_metadata", {})
            lead_id = metadata.get("call_id") or metadata.get("lead_id") or metadata.get("transcript_id")

        # 2. Extract Retailer and Call Date
        resolved_retailer = retailer
        resolved_call_date = call_date
        if raw_data and isinstance(raw_data, dict):
            metadata = raw_data.get("call_metadata", {})
            if not resolved_retailer:
                resolved_retailer = metadata.get("retailer") or metadata.get("provider")
            if not resolved_call_date:
                resolved_call_date = metadata.get("call_date")

        if not resolved_retailer:
            resolved_retailer = "TANGENT_BROADBAND"
        if not resolved_call_date:
            resolved_call_date = "2026-09-19"

        call_date_str = str(resolved_call_date)

        # 3. Evidence Index Construction
        evidence_index = EvidenceIndex(canonical)

        # 4. Versioned Check-Library Resolution
        resolver = VersionResolver(self.check_library)
        try:
            resolved_ruleset = resolver.resolve_ruleset(resolved_retailer, call_date_str)
            active_checks = resolved_ruleset.checks
        except (NoMatchingVersionError, OverlappingVersionError, Exception) as err:
            # Rule 11F: Check-library version mismatch fails closed to QA_REVIEW
            return GateResult(
                lead_id=lead_id,
                retailer=resolved_retailer,
                call_date=call_date_str,
                decision=GateDecision.QA_REVIEW,
                critical_checks_total=0,
                critical_checks_passed=0,
                critical_checks_failed=0,
                critical_checks_ambiguous=1,
                non_critical_failures=0,
                blocking_check_ids=[],
                review_check_ids=["VERSION_RESOLUTION_ERROR"],
                reasons=[
                    f"FAIL-CLOSED CONFIGURATION ALERT: Failed to resolve check library version for "
                    f"retailer '{resolved_retailer}' on call date '{call_date_str}': {err}"
                ],
                check_results=[],
            )

        # Filter by target_check_ids if specified
        if target_check_ids:
            target_set = set(target_check_ids)
            active_checks = [c for c in active_checks if c.check_id in target_set]

        # 5. Engine Evaluations (Verbatim, Factual, Behaviour)
        check_results: List[CheckResult] = []

        for check in active_checks:
            if check.type == CheckType.VERBATIM:
                res = self.verbatim_engine.evaluate_check(
                    check=check,
                    transcript=canonical,
                    evidence_index=evidence_index,
                )
                check_results.append(res)

            elif check.type == CheckType.FACTUAL:
                # Resolve ground-truth expected value
                expected_val = None
                if expected_values_override and check.check_id in expected_values_override:
                    expected_val = expected_values_override[check.check_id]
                elif check.check_id in self._gt_lookup:
                    expected_val = self._gt_lookup[check.check_id]
                elif "expected_value" in check.criteria:
                    expected_val = check.criteria["expected_value"]

                if expected_val is None:
                    # Inconclusive ground truth maps safely to AMBIGUOUS
                    res = CheckResult(
                        check_id=check.check_id,
                        check_type=check.type,
                        critical=check.critical,
                        status=CheckStatus.AMBIGUOUS,
                        confidence=0.0,
                        expected="MISSING_GROUND_TRUTH",
                        observed=None,
                        evidence=None,
                        reason=f"Ground-truth expected value could not be resolved for check '{check.check_id}'.",
                        check_version=check.version,
                    )
                else:
                    res = self.factual_engine.evaluate_check(
                        check=check,
                        transcript=canonical,
                        evidence_index=evidence_index,
                        expected_value=expected_val,
                    )
                check_results.append(res)

            elif check.type == CheckType.BEHAVIOUR:
                res = self.behaviour_engine.evaluate_check(
                    check=check,
                    transcript=canonical,
                    evidence_index=evidence_index,
                )
                check_results.append(res)

        # 6. Deterministic QA Gate Evaluation
        gate_result = DeterministicGate.evaluate(
            check_results=check_results,
            lead_id=lead_id,
            retailer=resolved_retailer,
            call_date=call_date_str,
            min_confidence_threshold=self.min_confidence_threshold,
        )

        return gate_result


# Top-level functional entry point
def run_pipeline(
    raw_transcript: Union[Dict[str, Any], str, Path, CanonicalTranscript],
    check_library: Optional[CheckLibrary] = None,
    ground_truth: Optional[Dict[str, Any]] = None,
    retailer: Optional[str] = None,
    call_date: Optional[Union[str, date]] = None,
    use_real_anthropic: bool = False,
    min_confidence_threshold: float = 0.80,
    expected_values_override: Optional[Dict[str, Any]] = None,
    target_check_ids: Optional[List[str]] = None,
) -> GateResult:
    """
    Top-level orchestration function executing full deterministic evaluation pipeline.
    """
    pipeline = QAPipeline(
        check_library=check_library,
        ground_truth=ground_truth,
        use_real_anthropic=use_real_anthropic,
        min_confidence_threshold=min_confidence_threshold,
    )
    return pipeline.evaluate_lead(
        raw_transcript=raw_transcript,
        retailer=retailer,
        call_date=call_date,
        expected_values_override=expected_values_override,
        target_check_ids=target_check_ids,
    )
