"""
Unit tests for Phase 6: Deterministic QA Gate Engine.

Verifies strict routing logic:
1. all critical PASS → AUTO_SUBMIT
2. one critical FAIL → HOLD
3. multiple critical FAIL → HOLD
4. critical AMBIGUOUS → QA_REVIEW
5. critical invalid evidence → QA_REVIEW
6. critical missing result → QA_REVIEW
7. non-critical FAIL + all critical PASS → AUTO_SUBMIT
8. behaviour FAIL → never HOLD
9. unsupported critical check → QA_REVIEW
10. no critical checks → reject configuration / fail closed
11. mixed PASS + FAIL + behaviour FAIL → HOLD
12. mixed PASS + AMBIGUOUS + behaviour FAIL → QA_REVIEW
13. deterministic repeated evaluation gives identical result
14. all final reasons are traceable to check IDs
"""

import copy
import pytest

from app.checks.models import CheckType
from app.factual.models import CheckResult, CheckStatus
from app.gate.engine import DeterministicGate
from app.gate.exceptions import EmptyGateEvaluationError, InvalidGateInputError
from app.gate.models import GateDecision, GateResult
from app.models import EvidenceReference


def _make_evidence(utterance_id: str = "utt_001", text: str = "Evidence text") -> EvidenceReference:
    return EvidenceReference(
        utterance_id=utterance_id,
        start_time=1.0,
        end_time=5.0,
        speaker="AGENT",
        text=text,
    )


_DEFAULT_EVIDENCE = object()


def _make_result(
    check_id: str,
    check_type: CheckType = CheckType.FACTUAL,
    critical: bool = True,
    status: CheckStatus = CheckStatus.PASS,
    confidence: float = 0.95,
    evidence: Any = _DEFAULT_EVIDENCE,
    reason: str = "Passed deterministic verification",
    check_version: str = "1.0.0",
) -> CheckResult:
    if evidence is _DEFAULT_EVIDENCE:
        evidence = _make_evidence() if status == CheckStatus.PASS else None

    return CheckResult(
        check_id=check_id,
        check_type=check_type,
        critical=critical,
        status=status,
        confidence=confidence,
        expected="expected_val",
        observed="expected_val" if status == CheckStatus.PASS else "diff_val",
        evidence=evidence,
        reason=reason,
        check_version=check_version,
    )


class TestDeterministicGate:
    """Tests covering all deterministic gate routing decisions and invariants."""

    def test_01_all_critical_pass_produces_auto_submit(self):
        """Rule 1: All critical checks PASS with valid evidence and confidence → AUTO_SUBMIT."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_VERB_001", CheckType.VERBATIM, critical=True, status=CheckStatus.PASS),
        ]
        gate_result = DeterministicGate.evaluate(results, lead_id="lead_123")
        assert gate_result.decision == GateDecision.AUTO_SUBMIT
        assert gate_result.critical_checks_total == 3
        assert gate_result.critical_checks_passed == 3
        assert gate_result.critical_checks_failed == 0
        assert gate_result.critical_checks_ambiguous == 0
        assert len(gate_result.blocking_check_ids) == 0
        assert len(gate_result.review_check_ids) == 0
        assert any("AUTO_SUBMIT" in r for r in gate_result.reasons)

    def test_02_one_critical_fail_produces_hold(self):
        """Rule 2: Exactly one critical FAIL → HOLD."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Price mismatch"),
            _make_result("CHK_VERB_001", CheckType.VERBATIM, critical=True, status=CheckStatus.PASS),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.HOLD
        assert gate_result.critical_checks_failed == 1
        assert "CHK_FACT_002" in gate_result.blocking_check_ids
        assert any("CHK_FACT_002" in r and "HOLD" in r for r in gate_result.reasons)

    def test_03_multiple_critical_fail_produces_hold(self):
        """Rule 3: Multiple critical FAIL → HOLD with all failing check IDs recorded."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Price mismatch"),
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Speed mismatch"),
            _make_result("CHK_VERB_001", CheckType.VERBATIM, critical=True, status=CheckStatus.PASS),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.HOLD
        assert gate_result.critical_checks_failed == 2
        assert set(gate_result.blocking_check_ids) == {"CHK_FACT_001", "CHK_FACT_002"}
        assert any("CHK_FACT_001" in r for r in gate_result.reasons)
        assert any("CHK_FACT_002" in r for r in gate_result.reasons)

    def test_04_critical_ambiguous_produces_qa_review(self):
        """Rule 4: Critical AMBIGUOUS → QA_REVIEW (not AUTO_SUBMIT, not HOLD)."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.AMBIGUOUS, reason="Inconclusive"),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert gate_result.critical_checks_ambiguous == 1
        assert "CHK_FACT_002" in gate_result.review_check_ids
        assert len(gate_result.blocking_check_ids) == 0
        assert any("CHK_FACT_002" in r and "QA_REVIEW" in r for r in gate_result.reasons)

    def test_05_critical_invalid_or_missing_evidence_produces_qa_review(self):
        """Rule 5: Critical check with status PASS but missing or invalid evidence → QA_REVIEW."""
        # 5a: None evidence
        results_none = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS, evidence=None),
        ]
        res_none = DeterministicGate.evaluate(results_none)
        assert res_none.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_001" in res_none.review_check_ids
        assert any("lacks verified backend evidence" in r for r in res_none.reasons)

        # 5b: Empty utterance_id in evidence
        bad_evidence = EvidenceReference(
            utterance_id="",
            start_time=1.0,
            end_time=2.0,
            speaker="AGENT",
            text="some text",
        )
        results_bad = [
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS, evidence=bad_evidence),
        ]
        res_bad = DeterministicGate.evaluate(results_bad)
        assert res_bad.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_002" in res_bad.review_check_ids

        # 5c: Empty text in evidence
        empty_text_ev = EvidenceReference(
            utterance_id="utt_1",
            start_time=1.0,
            end_time=2.0,
            speaker="AGENT",
            text="   ",
        )
        results_empty = [
            _make_result("CHK_FACT_003", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS, evidence=empty_text_ev),
        ]
        res_empty = DeterministicGate.evaluate(results_empty)
        assert res_empty.decision == GateDecision.QA_REVIEW

    def test_06_critical_missing_result_produces_qa_review(self):
        """Rule 6: Required critical check missing from evaluation results → QA_REVIEW."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
        ]
        required = ["CHK_FACT_001", "CHK_FACT_002_MISSING"]
        gate_result = DeterministicGate.evaluate(results, required_critical_check_ids=required)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_002_MISSING" in gate_result.review_check_ids
        assert any("CHK_FACT_002_MISSING" in r and "missing" in r for r in gate_result.reasons)

    def test_07_non_critical_fail_plus_all_critical_pass_produces_auto_submit(self):
        """Rule 7: Non-critical check failure does not block AUTO_SUBMIT when all critical checks PASS."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_BEHAV_001", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Dead air 15s"),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.AUTO_SUBMIT
        assert gate_result.non_critical_failures == 1
        assert gate_result.critical_checks_passed == 1
        assert len(gate_result.blocking_check_ids) == 0
        assert any("non-blocking" in r for r in gate_result.reasons)

    def test_08_behaviour_fail_never_produces_hold(self):
        """Rule 8: Behaviour checks are non-blocking by definition and can NEVER produce HOLD."""
        # Only behaviour checks, all failing
        results = [
            _make_result("CHK_BEHAV_001", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Rapport failed"),
            _make_result("CHK_BEHAV_002", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Excessive dead air"),
            _make_result("CHK_BEHAV_003", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Interruption detected"),
        ]
        # With zero critical checks, fail-closed configuration alert routes to QA_REVIEW, NEVER HOLD
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision != GateDecision.HOLD
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert len(gate_result.blocking_check_ids) == 0
        assert gate_result.non_critical_failures == 3

    def test_09_unsupported_critical_check_produces_qa_review(self):
        """Rule 9: Critical check with status UNSUPPORTED_CHECK → QA_REVIEW (never HOLD, never AUTO_SUBMIT)."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result(
                "CHK_VERB_003_RECORDING_DISCLOSURE",
                CheckType.VERBATIM,
                critical=True,
                status=CheckStatus.UNSUPPORTED_CHECK,
                reason="Unsupported check wording in specification",
            ),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert "CHK_VERB_003_RECORDING_DISCLOSURE" in gate_result.review_check_ids
        assert len(gate_result.blocking_check_ids) == 0
        assert any("CHK_VERB_003_RECORDING_DISCLOSURE" in r and "UNSUPPORTED_CHECK" in r for r in gate_result.reasons)

    def test_10_no_critical_checks_fails_closed(self):
        """Rule 10: Zero critical checks evaluated → fail-closed to QA_REVIEW or raise error."""
        # 10a: Fail-closed to QA_REVIEW by default
        results = [
            _make_result("CHK_NON_CRIT_001", CheckType.FACTUAL, critical=False, status=CheckStatus.PASS),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert gate_result.critical_checks_total == 0
        assert any("FAIL-CLOSED CONFIGURATION ALERT" in r for r in gate_result.reasons)

        # 10b: Empty results list fails closed to QA_REVIEW
        empty_res = DeterministicGate.evaluate([])
        assert empty_res.decision == GateDecision.QA_REVIEW

        # 10c: raise_on_empty=True raises EmptyGateEvaluationError
        with pytest.raises(EmptyGateEvaluationError):
            DeterministicGate.evaluate([], raise_on_empty=True)

    def test_11_mixed_pass_fail_and_behaviour_fail_produces_hold(self):
        """Rule 11: Critical FAIL overrides everything else and produces HOLD."""
        results = [
            _make_result("CHK_FACT_PASS", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_FAIL", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Critical price wrong"),
            _make_result("CHK_BEHAV_FAIL", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Dead air"),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.HOLD
        assert "CHK_FACT_FAIL" in gate_result.blocking_check_ids
        assert gate_result.non_critical_failures == 1
        assert any("CHK_FACT_FAIL" in r and "HOLD" in r for r in gate_result.reasons)

    def test_12_mixed_pass_ambiguous_and_behaviour_fail_produces_qa_review(self):
        """Rule 12: Mixed PASS + AMBIGUOUS + Behaviour FAIL produces QA_REVIEW."""
        results = [
            _make_result("CHK_FACT_PASS", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_AMBIG", CheckType.FACTUAL, critical=True, status=CheckStatus.AMBIGUOUS, reason="Unclear"),
            _make_result("CHK_BEHAV_FAIL", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Dead air"),
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert len(gate_result.blocking_check_ids) == 0
        assert "CHK_FACT_AMBIG" in gate_result.review_check_ids
        assert gate_result.non_critical_failures == 1

    def test_13_deterministic_repeated_evaluation_gives_identical_result(self):
        """Rule 13: Deterministic repeated evaluation produces byte-for-byte identical results."""
        results = [
            _make_result("CHK_FACT_001", CheckType.FACTUAL, critical=True, status=CheckStatus.PASS),
            _make_result("CHK_FACT_002", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Speed mismatch"),
            _make_result("CHK_VERB_001", CheckType.VERBATIM, critical=True, status=CheckStatus.AMBIGUOUS, reason="Paraphrase"),
            _make_result("CHK_BEHAV_001", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Dead air"),
        ]
        res1 = DeterministicGate.evaluate(results, lead_id="call_42")
        res2 = DeterministicGate.evaluate(copy.deepcopy(results), lead_id="call_42")
        assert res1.decision == res2.decision
        assert res1.critical_checks_total == res2.critical_checks_total
        assert res1.critical_checks_passed == res2.critical_checks_passed
        assert res1.critical_checks_failed == res2.critical_checks_failed
        assert res1.critical_checks_ambiguous == res2.critical_checks_ambiguous
        assert res1.non_critical_failures == res2.non_critical_failures
        assert res1.blocking_check_ids == res2.blocking_check_ids
        assert res1.review_check_ids == res2.review_check_ids
        assert res1.reasons == res2.reasons

    def test_14_all_final_reasons_are_traceable_to_check_ids(self):
        """Rule 14: All final explanations are traceable to specific check IDs."""
        results = [
            _make_result("CHK_CRIT_A", CheckType.FACTUAL, critical=True, status=CheckStatus.FAIL, reason="Failed A"),
            _make_result("CHK_CRIT_B", CheckType.FACTUAL, critical=True, status=CheckStatus.AMBIGUOUS, reason="Unclear B"),
            _make_result("CHK_NON_C", CheckType.BEHAVIOUR, critical=False, status=CheckStatus.FAIL, reason="Failed C"),
        ]
        gate_result = DeterministicGate.evaluate(results)
        combined_reasons = " ".join(gate_result.reasons)
        assert "CHK_CRIT_A" in combined_reasons
        assert "CHK_CRIT_B" in combined_reasons
        assert "CHK_NON_C" in combined_reasons or gate_result.non_critical_failures > 0

    def test_insufficient_confidence_triggers_qa_review(self):
        """Low extraction confidence on critical check must route to QA_REVIEW."""
        results = [
            _make_result(
                "CHK_FACT_001",
                CheckType.FACTUAL,
                critical=True,
                status=CheckStatus.PASS,
                confidence=0.55,  # Below 0.80 default threshold
                reason="Extraction was tentative",
            ),
        ]
        gate_result = DeterministicGate.evaluate(results, min_confidence_threshold=0.80)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_001" in gate_result.review_check_ids
        assert any("insufficient confidence" in r for r in gate_result.reasons)

    def test_invalid_input_type_raises_error(self):
        """Non-list or non-CheckResult items raise InvalidGateInputError."""
        with pytest.raises(InvalidGateInputError):
            DeterministicGate.evaluate("not a list")  # type: ignore

        with pytest.raises(InvalidGateInputError):
            DeterministicGate.evaluate(["not a check result"])  # type: ignore

    def test_low_confidence_status_triggers_qa_review(self):
        """CheckStatus.LOW_CONFIDENCE on critical check forces QA_REVIEW."""
        results = [
            _make_result(
                "CHK_FACT_001",
                CheckType.FACTUAL,
                critical=True,
                status=CheckStatus.LOW_CONFIDENCE,
                reason="Model extraction confidence 0.65 below minimum 0.80",
            )
        ]
        gate_result = DeterministicGate.evaluate(results)
        assert gate_result.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_001" in gate_result.review_check_ids
