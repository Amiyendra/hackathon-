"""
Unit tests for Ground Truth Accuracy Evaluator (Phase 8A).

Validates:
- eligibility filtering (transcript-grounded facts vs synthetic variations)
- metric calculations (correct, incorrect, ambiguous, agreement percentage)
- report and per-check table formatting
- offline deterministic execution (zero live API calls)
- simulated mismatch and ambiguity counting
"""

import json
from pathlib import Path
import pytest

from app.evaluation import (
    GroundTruthComparison,
    GroundTruthEvaluationReport,
    GroundTruthEvaluator,
)
from app.factual.models import CheckResult, CheckStatus
from app.pipeline import QAPipeline


@pytest.fixture
def project_root():
    return Path(__file__).resolve().parent.parent


@pytest.fixture
def ground_truth_data(project_root):
    path = project_root / "data" / "broadband_ground_truth.json"
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_is_eligible_filters_correctly():
    """Eligible records must have basis == explicitly_stated_in_transcript."""
    eligible_record = {
        "check_id": "CHK_FACT_001",
        "basis": "explicitly_stated_in_transcript",
    }
    synthetic_record = {
        "check_id": "CHK_FACT_014",
        "basis": "synthetic_test_variation",
    }
    other_record = {
        "check_id": "CHK_FACT_099",
        "basis": "unknown_origin",
    }

    assert GroundTruthEvaluator.is_eligible(eligible_record) is True
    assert GroundTruthEvaluator.is_eligible(synthetic_record) is False
    assert GroundTruthEvaluator.is_eligible(other_record) is False


def test_evaluator_metrics_calculation():
    """Verify accuracy metrics calculation in GroundTruthEvaluationReport."""
    comparisons = [
        GroundTruthComparison("CHK_1", "f1", "basis", "PASS", "PASS", True, "ok"),
        GroundTruthComparison("CHK_2", "f2", "basis", "PASS", "PASS", True, "ok"),
        GroundTruthComparison("CHK_3", "f3", "basis", "PASS", "FAIL", False, "mismatch"),
        GroundTruthComparison("CHK_4", "f4", "basis", "PASS", "AMBIGUOUS", False, "unclear"),
    ]
    report = GroundTruthEvaluationReport(
        total_eligible=4,
        correct=2,
        incorrect=1,
        ambiguous=1,
        agreement_percentage=50.0,
        comparisons=comparisons,
    )
    assert report.total_eligible == 4
    assert report.correct == 2
    assert report.incorrect == 1
    assert report.ambiguous == 1
    assert report.agreement_percentage == 50.0

    report_str = report.format_report()
    assert "Eligible cases: 4" in report_str
    assert "Correct: 2" in report_str
    assert "Incorrect: 1" in report_str
    assert "Ambiguous: 1" in report_str
    assert "Agreement: 50.00%" in report_str

    table_str = report.format_table()
    assert "Check ID" in table_str
    assert "Ground Truth" in table_str
    assert "System" in table_str
    assert "Match" in table_str
    assert "CHK_1" in table_str
    assert "YES" in table_str
    assert "NO" in table_str


def test_broadband_ground_truth_evaluator_live_run(project_root):
    """
    Run GroundTruthEvaluator on actual broadband dataset.
    Verifies that all 14 eligible transcript-grounded records match system evaluation.
    """
    report = GroundTruthEvaluator.evaluate()

    # 14 eligible cases (excluding 4 synthetic test variations)
    assert report.total_eligible == 14
    assert report.correct == 14
    assert report.incorrect == 0
    assert report.ambiguous == 0
    assert report.agreement_percentage == 100.00
    assert len(report.excluded_cases) == 4
    assert set(report.excluded_cases) == {
        "CHK_FACT_BB_014_DELIVERY_FEE",
        "CHK_FACT_BB_015_CONTRACT_TERM",
        "CHK_FACT_BB_017_BATTERY_BACKUP",
        "CHK_FACT_BB_018_STATIC_IP",
    }


def test_broadband_ground_truth_evaluator_with_synthetic_variations():
    """
    When include_synthetic_variations=True, all 18 cases are evaluated.
    """
    report = GroundTruthEvaluator.evaluate(include_synthetic_variations=True)

    assert report.total_eligible == 18
    assert report.correct == 18
    assert report.incorrect == 0
    assert report.ambiguous == 0
    assert report.agreement_percentage == 100.00
    assert len(report.excluded_cases) == 0


def test_evaluator_handles_pipeline_mismatch(monkeypatch, project_root):
    """Simulate a pipeline discrepancy to ensure mismatch metrics increment properly."""
    custom_gt = {
        "ground_truth_records": [
            {
                "check_id": "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
                "field": "promotional_price_aud",
                "basis": "explicitly_stated_in_transcript",
                "test_case_category": "PASS",
                "expected_value": 42.90,
            }
        ]
    }

    # Force the factual engine to return FAIL
    pipeline = QAPipeline()
    def mock_eval(*args, **kwargs):
        return CheckResult(
            check_id="CHK_FACT_BB_006_PROMOTIONAL_PRICE",
            check_type="FACTUAL",
            critical=True,
            status=CheckStatus.FAIL,
            confidence=0.99,
            expected=42.90,
            observed=99.00,
            evidence=None,
            reason="Deliberate simulated mismatch",
            check_version="1.0.0",
        )
    monkeypatch.setattr(pipeline.factual_engine, "evaluate_check", mock_eval)

    report = GroundTruthEvaluator.evaluate(
        ground_truth_data=custom_gt,
        pipeline=pipeline,
    )

    assert report.total_eligible == 1
    assert report.correct == 0
    assert report.incorrect == 1
    assert report.ambiguous == 0
    assert report.agreement_percentage == 0.00
    assert report.comparisons[0].is_match is False
