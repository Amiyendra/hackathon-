"""
Deterministic QA Gate Evaluation Engine.

Synthesizes the outputs of Factual QA, Verbatim QA, and Behaviour QA into exactly
one final deterministic disposition:
- AUTO_SUBMIT
- HOLD
- QA_REVIEW

STRICT ARCHITECTURAL INVARIANTS:
1. Python is the sole authority for routing. The LLM has zero routing authority.
2. Criticality originates strictly from the CheckDefinition / check library.
3. Behaviour checks can NEVER cause HOLD or block AUTO_SUBMIT.
4. Any critical FAIL forces HOLD.
5. Any critical AMBIGUOUS, LOW_CONFIDENCE, UNSUPPORTED, or missing evidence forces QA_REVIEW.
6. Zero critical checks triggers fail-closed QA_REVIEW.
7. All individual CheckResult instances are preserved in the GateResult.
"""

from typing import Any, List, Optional

from app.factual.models import CheckResult, CheckStatus
from app.gate.exceptions import EmptyGateEvaluationError, InvalidGateInputError
from app.gate.models import GateDecision, GateResult
from app.models import EvidenceReference


class DeterministicGate:
    """
    Evaluator for final call submission and compliance routing.
    
    Synthesizes the outputs of Factual QA, Verbatim QA, and Behaviour QA into exactly
    one final deterministic disposition:
    - AUTO_SUBMIT
    - HOLD
    - QA_REVIEW
    """

    DEFAULT_MIN_CONFIDENCE: float = 0.80

    @classmethod
    def _is_valid_evidence(cls, evidence: Any) -> bool:
        """Verify that evidence is a valid, non-empty EvidenceReference."""
        if evidence is None:
            return False
        if not isinstance(evidence, EvidenceReference):
            return False
        if not evidence.utterance_id or not str(evidence.utterance_id).strip():
            return False
        if not evidence.text or not str(evidence.text).strip():
            return False
        if evidence.end_time < evidence.start_time:
            return False
        return True

    @classmethod
    def evaluate(
        cls,
        check_results: List[CheckResult],
        lead_id: Optional[str] = None,
        retailer: Optional[str] = None,
        call_date: Optional[str] = None,
        required_critical_check_ids: Optional[List[str]] = None,
        min_confidence_threshold: float = DEFAULT_MIN_CONFIDENCE,
        raise_on_empty: bool = False,
    ) -> GateResult:
        """
        Evaluate a collection of CheckResult objects and produce a deterministic GateResult.
        
        Args:
            check_results: List of CheckResult objects from factual, verbatim, or behaviour engines.
            lead_id: Optional identifier for the call or lead transcript.
            retailer: Optional retailer identifier.
            call_date: Optional call date.
            required_critical_check_ids: Optional list of critical check IDs required to be evaluated.
            min_confidence_threshold: Minimum extraction confidence required for a critical PASS.
            raise_on_empty: If True, raises EmptyGateEvaluationError when check_results is empty.
            
        Returns:
            GateResult containing final decision, metrics, and traceable audit reasons.
        """
        if not isinstance(check_results, list):
            raise InvalidGateInputError("check_results must be a list of CheckResult instances.")

        if raise_on_empty and len(check_results) == 0:
            raise EmptyGateEvaluationError("Cannot evaluate an empty check results list when raise_on_empty=True.")

        for item in check_results:
            if not isinstance(item, CheckResult):
                raise InvalidGateInputError(
                    f"All items in check_results must be CheckResult instances, got {type(item).__name__}."
                )

        # 1. Partition results by criticality
        critical_results: List[CheckResult] = [r for r in check_results if r.critical is True]
        non_critical_results: List[CheckResult] = [r for r in check_results if r.critical is False]

        # 2. Count non-critical failures (informative only, strictly non-blocking)
        non_crit_failed = [r for r in non_critical_results if r.status == CheckStatus.FAIL]
        non_critical_failures_count = len(non_crit_failed)

        # 3. Categorize critical results
        critical_failed: List[CheckResult] = []
        critical_review: List[CheckResult] = []
        critical_review_reasons: List[str] = []
        critical_passed: List[CheckResult] = []

        for r in critical_results:
            if r.status == CheckStatus.FAIL:
                critical_failed.append(r)
            elif r.status in (CheckStatus.AMBIGUOUS, CheckStatus.LOW_CONFIDENCE, CheckStatus.UNSUPPORTED_CHECK):
                critical_review.append(r)
                critical_review_reasons.append(
                    f"QA_REVIEW: Critical check '{r.check_id}' ({r.check_type.value}) has status "
                    f"{r.status.value}: {r.reason}"
                )
            elif not cls._is_valid_evidence(r.evidence):
                # Critical PASS or other status with invalid/missing evidence
                critical_review.append(r)
                critical_review_reasons.append(
                    f"QA_REVIEW: Critical check '{r.check_id}' ({r.check_type.value}) lacks verified backend evidence."
                )
            elif r.confidence < min_confidence_threshold:
                # Critical PASS with insufficient confidence
                critical_review.append(r)
                critical_review_reasons.append(
                    f"QA_REVIEW: Critical check '{r.check_id}' ({r.check_type.value}) has insufficient confidence "
                    f"({r.confidence:.2f} < {min_confidence_threshold:.2f}): {r.reason}"
                )
            elif r.status == CheckStatus.PASS:
                critical_passed.append(r)
            else:
                # Any other unknown or unhandled status on a critical check forces review
                critical_review.append(r)
                critical_review_reasons.append(
                    f"QA_REVIEW: Critical check '{r.check_id}' ({r.check_type.value}) has unhandled status "
                    f"'{r.status}': {r.reason}"
                )

        # 4. Check for missing required critical check results
        missing_critical_ids: List[str] = []
        if required_critical_check_ids:
            evaluated_ids = {r.check_id for r in check_results}
            for req_id in required_critical_check_ids:
                if req_id not in evaluated_ids:
                    missing_critical_ids.append(req_id)
                    critical_review_reasons.append(
                        f"QA_REVIEW: Required critical check '{req_id}' is missing from evaluation results."
                    )

        total_critical = len(critical_results) + len(missing_critical_ids)
        blocking_check_ids = [r.check_id for r in critical_failed]
        review_check_ids = [r.check_id for r in critical_review] + missing_critical_ids
        reasons: List[str] = []

        # ---------------------------------------------------------------------
        # Gate Decision Priority Rules
        # ---------------------------------------------------------------------

        # Priority A: Zero critical checks evaluated -> Fail-closed to QA_REVIEW
        if total_critical == 0:
            decision = GateDecision.QA_REVIEW
            reasons.append(
                "FAIL-CLOSED CONFIGURATION ALERT: No critical checks were evaluated for this call. "
                "Requires manual QA review to confirm check configuration."
            )
            if non_critical_failures_count > 0:
                reasons.append(
                    f"Notice: {non_critical_failures_count} non-critical check(s) failed."
                )

        # Priority B: Any critical check failed -> HOLD
        elif len(critical_failed) > 0:
            decision = GateDecision.HOLD
            for r in critical_failed:
                reasons.append(
                    f"HOLD: Critical check '{r.check_id}' ({r.check_type.value}) FAILED: {r.reason}"
                )
            if len(review_check_ids) > 0:
                reasons.append(
                    f"Additional notice: {len(review_check_ids)} critical check(s) also require review "
                    f"({', '.join(review_check_ids)})."
                )
            if non_critical_failures_count > 0:
                reasons.append(
                    f"Notice: {non_critical_failures_count} non-critical check(s) failed (non-blocking)."
                )

        # Priority C: Any critical check inconclusive, unsupported, missing, or lacking evidence -> QA_REVIEW
        elif len(review_check_ids) > 0:
            decision = GateDecision.QA_REVIEW
            reasons.extend(critical_review_reasons)
            if non_critical_failures_count > 0:
                reasons.append(
                    f"Notice: {non_critical_failures_count} non-critical check(s) failed (non-blocking)."
                )

        # Priority D: All critical checks passed with valid evidence and confidence -> AUTO_SUBMIT
        else:
            decision = GateDecision.AUTO_SUBMIT
            if non_critical_failures_count > 0:
                failed_non_crit_ids = [r.check_id for r in non_crit_failed]
                reasons.append(
                    f"AUTO_SUBMIT: All {total_critical} critical checks passed with verified backend evidence. "
                    f"{non_critical_failures_count} non-critical failure(s) detected ({', '.join(failed_non_crit_ids)}) "
                    f"which are non-blocking."
                )
            else:
                reasons.append(
                    f"AUTO_SUBMIT: All {total_critical} critical checks passed with verified backend evidence."
                )

        return GateResult(
            lead_id=lead_id,
            retailer=retailer,
            call_date=call_date,
            decision=decision,
            critical_checks_total=total_critical,
            critical_checks_passed=len(critical_passed),
            critical_checks_failed=len(critical_failed),
            critical_checks_ambiguous=len(review_check_ids),
            non_critical_failures=non_critical_failures_count,
            blocking_check_ids=blocking_check_ids,
            review_check_ids=review_check_ids,
            reasons=reasons,
            check_results=check_results,
        )
