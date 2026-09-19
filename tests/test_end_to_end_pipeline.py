"""
Integration tests for Phase 7: End-to-End Pipeline & Real Lead Demo.

Verifies end-to-end orchestration:
A. All critical checks PASS → AUTO_SUBMIT
B. One critical factual mismatch → HOLD
C. One critical ambiguous result → QA_REVIEW
D. Behaviour FAIL + all critical PASS → AUTO_SUBMIT
E. Invalid evidence → QA_REVIEW
F. Check-library version mismatch → fail closed / QA_REVIEW
G. Compact evidence trace & PII / PCI redaction
H. Preservation of every individual CheckResult
"""

from datetime import date
import json
from pathlib import Path
import pytest

from app.checks.models import CheckDefinition, CheckLibrary, CheckType
from app.factual.models import CheckResult, CheckStatus
from app.gate.models import GateDecision
from app.models import EvidenceReference
from app.pipeline import (
    QAPipeline,
    format_compact_evidence_trace,
    format_pipeline_summary,
    load_default_broadband_ground_truth,
    load_default_broadband_library,
    redact_pii_and_pci,
    run_pipeline,
)


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def broadband_transcript_data(project_root):
    path = project_root / "data" / "broadband_transcript.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


@pytest.fixture
def broadband_library():
    return load_default_broadband_library()


@pytest.fixture
def broadband_ground_truth():
    return load_default_broadband_ground_truth()


class TestEndToEndPipeline:
    """Test full integration from raw transcript to GateDecision."""

    def test_e2e_01_all_critical_pass_produces_auto_submit(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Integration Test A: All critical checks PASS → AUTO_SUBMIT.
        Select passing subset of broadband checks across Factual, Verbatim, and Behaviour.
        """
        passing_critical_ids = [
            # Critical Factual checks known to pass
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
            # Critical Verbatim checks known to pass
            "CHK_VERB_BB_001_GREETING_BRAND",
            "CHK_VERB_BB_002_STATUTORY_MIN_COST",
            # Non-critical Behaviour check known to pass
            "CHK_BEHAV_BB_001_DEAD_AIR",
            "CHK_BEHAV_BB_003_INTERRUPTIONS",
        ]

        pipeline = QAPipeline(
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
        )

        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            target_check_ids=passing_critical_ids,
        )

        assert result.decision == GateDecision.AUTO_SUBMIT
        assert result.critical_checks_failed == 0
        assert result.critical_checks_ambiguous == 0
        assert result.critical_checks_passed == 11
        assert len(result.blocking_check_ids) == 0
        assert len(result.review_check_ids) == 0
        assert result.retailer == "TANGENT_BROADBAND"
        assert result.call_date == "2026-09-19"
        assert any("AUTO_SUBMIT" in r for r in result.reasons)

    def test_e2e_02_critical_factual_mismatch_produces_hold(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Integration Test B: Exactly one critical factual mismatch → HOLD.
        Inject a rate-card mismatch where expected promotional price is $55.00 instead of $69.00.
        """
        target_ids = [
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
            "CHK_VERB_BB_001_GREETING_BRAND",
            "CHK_BEHAV_BB_001_DEAD_AIR",
        ]

        pipeline = QAPipeline(
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
        )

        # Agent quoted $69.00; override expected value to $55.00 to force mismatch
        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            target_check_ids=target_ids,
            expected_values_override={"CHK_FACT_BB_006_PROMOTIONAL_PRICE": 55.0},
        )

        assert result.decision == GateDecision.HOLD
        assert result.critical_checks_failed == 1
        assert "CHK_FACT_BB_006_PROMOTIONAL_PRICE" in result.blocking_check_ids
        assert any("HOLD" in r and "CHK_FACT_BB_006_PROMOTIONAL_PRICE" in r for r in result.reasons)

    def test_e2e_03_critical_ambiguous_result_produces_qa_review(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Integration Test C: Critical check with ambiguous/missing information → QA_REVIEW.
        """
        # Create a critical check that is completely unmentioned in transcript
        unmentioned_critical_check = CheckDefinition(
            check_id="CHK_FACT_BB_CRIT_UNMENTIONED",
            retailer="TANGENT_BROADBAND",
            name="Critical Unmentioned Feature Check",
            type=CheckType.FACTUAL,
            version="1.0.0",
            critical=True,
            effective_from=date(2026, 1, 1),
            description="Mandatory feature unmentioned in audio",
            criteria={"field": "unmentioned_mandatory_field", "comparison_method": "string_exact"},
        )

        custom_library = CheckLibrary(
            version="1.0.0",
            description="Custom test library",
            checks=list(broadband_library.checks) + [unmentioned_critical_check],
        )

        pipeline = QAPipeline(
            check_library=custom_library,
            ground_truth=broadband_ground_truth,
        )

        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            target_check_ids=[
                "CHK_FACT_BB_001_CURRENT_PROVIDER",
                "CHK_FACT_BB_CRIT_UNMENTIONED",
            ],
            expected_values_override={"CHK_FACT_BB_CRIT_UNMENTIONED": "REQUIRED_FEATURE"},
        )

        assert result.decision == GateDecision.QA_REVIEW
        assert "CHK_FACT_BB_CRIT_UNMENTIONED" in result.review_check_ids
        assert len(result.blocking_check_ids) == 0

    def test_e2e_04_behaviour_fail_with_all_critical_pass_produces_auto_submit(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Integration Test D: Behaviour FAIL + all critical PASS → AUTO_SUBMIT.
        Verifies that non-functional behaviour failures are strictly non-blocking.
        """
        target_ids = [
            "CHK_FACT_BB_001_CURRENT_PROVIDER",  # Critical PASS
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",  # Critical PASS
            "CHK_VERB_BB_001_GREETING_BRAND",     # Critical PASS
            "CHK_BEHAV_BB_002_DEAD_AIR_STRICT",   # Non-critical Behaviour FAIL
        ]

        pipeline = QAPipeline(
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
        )

        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            target_check_ids=target_ids,
        )

        assert result.decision == GateDecision.AUTO_SUBMIT
        assert result.critical_checks_passed == 2
        assert result.critical_checks_failed == 0
        assert result.non_critical_failures == 1
        assert len(result.blocking_check_ids) == 0
        assert any("non-blocking" in r for r in result.reasons)

    def test_e2e_05_invalid_evidence_produces_qa_review(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth, monkeypatch
    ):
        """
        Integration Test E: Critical check that passes but returns invalid/missing evidence → QA_REVIEW.
        """
        pipeline = QAPipeline(
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
        )

        # Mock verbatim engine to return a PASS check with evidence=None
        def mock_eval_check(*args, **kwargs):
            return CheckResult(
                check_id="CHK_VERB_BB_001_GREETING_BRAND",
                check_type=CheckType.VERBATIM,
                critical=True,
                status=CheckStatus.PASS,
                confidence=0.99,
                expected="greeting",
                observed="greeting",
                evidence=None,  # Missing evidence!
                reason="Corrupted evidence reference",
                check_version="1.0.0",
            )

        monkeypatch.setattr(pipeline.verbatim_engine, "evaluate_check", mock_eval_check)

        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            target_check_ids=["CHK_VERB_BB_001_GREETING_BRAND"],
        )

        assert result.decision == GateDecision.QA_REVIEW
        assert "CHK_VERB_BB_001_GREETING_BRAND" in result.review_check_ids
        assert any("lacks verified backend evidence" in r for r in result.reasons)

    def test_e2e_06_version_mismatch_fails_closed_to_qa_review(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Integration Test F: Check-library version mismatch → fail closed to QA_REVIEW.
        """
        pipeline = QAPipeline(
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
        )

        # Query a non-existent retailer
        result = pipeline.evaluate_lead(
            raw_transcript=broadband_transcript_data,
            retailer="UNKNOWN_RETAILER_CORP",
            call_date="2026-09-19",
        )

        assert result.decision == GateDecision.QA_REVIEW
        assert "VERSION_RESOLUTION_ERROR" in result.review_check_ids
        assert any("FAIL-CLOSED" in r for r in result.reasons)

    def test_e2e_07_pii_redaction_in_traces_and_reasons(self):
        """
        Verification: Guarantee no raw credit cards, CVVs, emails, or phone numbers leak in traces.
        """
        sample_dirty_text = (
            "Agent recorded credit card 4532 1234 5678 9012 with cvv: 123, email customer@gmail.com "
            "and phone 0412345678."
        )
        cleaned = redact_pii_and_pci(sample_dirty_text)
        assert "4532 1234 5678 9012" not in cleaned
        assert "[REDACTED_PAYMENT_CARD]" in cleaned
        assert "customer@gmail.com" not in cleaned
        assert "[REDACTED_EMAIL]" in cleaned
        assert "0412345678" not in cleaned
        assert "[REDACTED_PHONE]" in cleaned

    def test_e2e_08_preserves_every_check_result(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Rule: Every single CheckResult evaluated by engines must be preserved in GateResult.
        """
        target_ids = [
            "CHK_FACT_BB_001_CURRENT_PROVIDER",
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
            "CHK_VERB_BB_001_GREETING_BRAND",
            "CHK_BEHAV_BB_001_DEAD_AIR",
        ]

        result = run_pipeline(
            raw_transcript=broadband_transcript_data,
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
            target_check_ids=target_ids,
        )

        assert len(result.check_results) == 4
        evaluated_ids = {r.check_id for r in result.check_results}
        assert evaluated_ids == set(target_ids)
        assert result.all_check_results == result.check_results

    def test_e2e_09_compact_evidence_trace_formatting(
        self, broadband_transcript_data, broadband_library, broadband_ground_truth
    ):
        """
        Verification: Compact evidence trace accurately lists failed/reviewed checks.
        """
        # Run with deliberate fail fixture CHK_FACT_BB_014_DELIVERY_FEE
        target_ids = [
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",  # PASS
            "CHK_FACT_BB_014_DELIVERY_FEE",       # FAIL ($0 vs $15)
            "CHK_BEHAV_BB_002_DEAD_AIR_STRICT",   # Non-critical FAIL
        ]

        result = run_pipeline(
            raw_transcript=broadband_transcript_data,
            check_library=broadband_library,
            ground_truth=broadband_ground_truth,
            target_check_ids=target_ids,
        )

        trace = format_compact_evidence_trace(result)
        summary = format_pipeline_summary(result)

        assert "CHECK ID:" in trace
        assert "CATEGORY:" in trace
        assert "STATUS:" in trace
        assert "CRITICAL:" in trace
        assert "EVIDENCE UTTERANCE ID:" in trace
        assert "ACTUAL TIMESTAMP:" in trace
        assert "REASON:" in trace
        assert "CHK_FACT_BB_014_DELIVERY_FEE" in trace
        assert "CHK_BEHAV_BB_002_DEAD_AIR_STRICT" in trace
        assert "CHK_FACT_BB_006_PROMOTIONAL_PRICE" not in trace  # PASS is omitted from failed/reviewed trace
        assert "END-TO-END DETERMINISTIC QA GATE EVALUATION RESULT" in summary
