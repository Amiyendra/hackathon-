"""
Factual Match Engine.

Coordinates claim extraction, evidence validation, and deterministic comparison.

PIPELINE FLOW:
Transcript -> LLM Extraction -> EvidenceIndex Validation -> Deterministic Python Comparison -> CheckResult

ARCHITECTURAL MANDATES:
- The LLM is NOT the final authority.
- The LLM never decides PASS, FAIL, AMBIGUOUS, criticality, check_version, or timestamps.
- All timestamps and evidence slices originate exclusively from EvidenceIndex.
- Criticality and check version originate exclusively from CheckDefinition.
- Final evaluation is performed by pure Python deterministic comparators.
"""

from typing import Any, Dict, List, Optional, Union
from app.checks.models import CheckDefinition, ResolvedRuleSet
from app.evidence.index import EvidenceIndex
from app.factual.comparator import DeterministicComparator
from app.factual.exceptions import MissingExpectedValueError
from app.factual.extractor import ClaimExtractor
from app.factual.models import CheckResult, CheckStatus
from app.models import CanonicalTranscript, EvidenceReference


class FactualEngine:
    """
    Core engine evaluating factual QA checks against canonical transcripts and ground truth.
    """

    def __init__(
        self,
        extractor: Optional[ClaimExtractor] = None,
        comparator: Optional[DeterministicComparator] = None
    ):
        self.extractor = extractor or ClaimExtractor()
        self.comparator = comparator or DeterministicComparator()

    def evaluate_check(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
        expected_value: Any
    ) -> CheckResult:
        """
        Evaluate a single factual check definition.
        
        Args:
            check: Resolved CheckDefinition (source of truth for criticality, version, criteria).
            transcript: Verified CanonicalTranscript.
            evidence_index: Verified EvidenceIndex.
            expected_value: Ground-truth expected value.
            
        Returns:
            Deterministic CheckResult.
        """
        # Invariants strictly derived from CheckDefinition (LLM cannot override)
        critical = check.critical
        check_version = check.version
        check_type = check.type
        target_field = check.criteria.get("field", check.check_id)

        # 1. Ground truth validation: Missing expected value cannot automatically pass
        if expected_value is None:
            raise MissingExpectedValueError(
                f"Ground-truth expected value is missing for check '{check.check_id}' (field '{target_field}')."
            )

        # 2. Extract claim via LLM abstraction
        claim = self.extractor.extract_claim(check, transcript)

        # 3. Handle missing utterance ID or unmentioned claim
        if not claim.utterance_id or not str(claim.utterance_id).strip():
            return CheckResult(
                check_id=check.check_id,
                check_type=check_type,
                critical=critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=claim.confidence,
                expected=expected_value,
                observed=claim.value,
                evidence=None,
                reason=f"No factual claim detected in transcript for field '{target_field}'.",
                check_version=check_version,
                field=target_field,
                utterance_id=None
            )

        # 4. EvidenceIndex Validation: Verify utterance_id exists in transcript
        utterance = evidence_index.get_utterance(claim.utterance_id.strip())
        if utterance is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check_type,
                critical=critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=claim.confidence,
                expected=expected_value,
                observed=claim.value,
                evidence=None,
                reason=f"LLM referenced an unknown utterance_id: '{claim.utterance_id}'.",
                check_version=check_version,
                field=target_field,
                utterance_id=claim.utterance_id
            )

        # Construct verified evidence reference directly from backend EvidenceIndex
        # (Discard any timestamps or texts the LLM might have returned)
        evidence = EvidenceReference.from_utterance(utterance)

        # 5. Extraction Confidence Threshold Validation
        min_confidence = check.criteria.get("confidence_requirements", {}).get("min_confidence", 0.80)
        if claim.confidence < min_confidence:
            return CheckResult(
                check_id=check.check_id,
                check_type=check_type,
                critical=critical,
                status=CheckStatus.LOW_CONFIDENCE,
                confidence=claim.confidence,
                expected=expected_value,
                observed=claim.value,
                evidence=evidence,
                reason=f"Extraction confidence ({claim.confidence:.2f}) is below minimum threshold ({min_confidence:.2f}).",
                check_version=check_version,
                field=target_field,
                utterance_id=evidence.utterance_id
            )

        # 6. Check if observed claim value is null
        if claim.value is None:
            return CheckResult(
                check_id=check.check_id,
                check_type=check_type,
                critical=critical,
                status=CheckStatus.AMBIGUOUS,
                confidence=claim.confidence,
                expected=expected_value,
                observed=None,
                evidence=evidence,
                reason=f"No reliable factual claim value found in referenced utterance '{evidence.utterance_id}'.",
                check_version=check_version,
                field=target_field,
                utterance_id=evidence.utterance_id
            )

        # 7. Deterministic Python Comparison
        comparison_method = check.criteria.get("comparison_method")
        is_match, comp_reason = self.comparator.compare(
            expected=expected_value,
            observed=claim.value,
            method=comparison_method,
            allow_semantic_variation=check.allow_semantic_variation,
            criteria=check.criteria
        )

        final_status = CheckStatus.PASS if is_match else CheckStatus.FAIL

        return CheckResult(
            check_id=check.check_id,
            check_type=check_type,
            critical=critical,
            status=final_status,
            confidence=claim.confidence,
            expected=expected_value,
            observed=claim.value,
            evidence=evidence,
            reason=comp_reason,
            check_version=check_version,
            field=target_field,
            utterance_id=evidence.utterance_id
        )

    def evaluate_ruleset(
        self,
        ruleset: ResolvedRuleSet,
        transcript: CanonicalTranscript,
        evidence_index: EvidenceIndex,
        ground_truth: Union[Dict[str, Any], List[Dict[str, Any]]]
    ) -> List[CheckResult]:
        """
        Evaluate an entire resolved rule set against ground truth.
        """
        # Normalize ground truth lookup table
        gt_by_key: Dict[str, Any] = {}
        if isinstance(ground_truth, list):
            for item in ground_truth:
                if isinstance(item, dict):
                    if "check_id" in item:
                        gt_by_key[item["check_id"]] = item.get("expected_value")
                    if "field" in item:
                        gt_by_key[item["field"]] = item.get("expected_value")
        elif isinstance(ground_truth, dict):
            if "ground_truth_records" in ground_truth:
                for item in ground_truth["ground_truth_records"]:
                    if "check_id" in item:
                        gt_by_key[item["check_id"]] = item.get("expected_value")
                    if "field" in item:
                        gt_by_key[item["field"]] = item.get("expected_value")
            else:
                gt_by_key = dict(ground_truth)

        results: List[CheckResult] = []
        for check in ruleset.checks:
            target_field = check.criteria.get("field", check.check_id)
            expected_val = gt_by_key.get(check.check_id, gt_by_key.get(target_field))

            result = self.evaluate_check(
                check=check,
                transcript=transcript,
                evidence_index=evidence_index,
                expected_value=expected_val
            )
            results.append(result)

        return results
