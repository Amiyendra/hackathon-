"""
Ground Truth Accuracy Evaluator.

Evaluates system CheckResult accuracy against the ground truth dataset:
- Filters for eligible transcript-grounded facts
- Excludes synthetic test variations (rate-card perturbations, artificial omissions)
- Runs deterministic end-to-end pipeline
- Compares expected ground truth status vs system CheckResult status
- Computes agreement percentage, correct, incorrect, and ambiguous counts
- Formats reports and per-check tables
"""

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from app.factual.models import CheckResult, CheckStatus
from app.pipeline import (
    QAPipeline,
    load_default_broadband_ground_truth,
    load_default_broadband_library,
)


@dataclass(frozen=True)
class GroundTruthComparison:
    """Per-check comparison record between Ground Truth and System evaluation."""
    check_id: str
    field: str
    basis: str
    ground_truth_status: str
    system_status: str
    is_match: bool
    reason: str


@dataclass(frozen=True)
class GroundTruthEvaluationReport:
    """Comprehensive accuracy metrics and audit comparison records."""
    total_eligible: int
    correct: int
    incorrect: int
    ambiguous: int
    agreement_percentage: float
    comparisons: List[GroundTruthComparison] = field(default_factory=list)
    excluded_cases: List[str] = field(default_factory=list)

    def format_report(self) -> str:
        """Format the summary report specified in requirements."""
        lines = [
            "GROUND TRUTH EVALUATION",
            "=======================",
            f"Eligible cases: {self.total_eligible}",
            f"Correct: {self.correct}",
            f"Incorrect: {self.incorrect}",
            f"Ambiguous: {self.ambiguous}",
            "",
            f"Agreement: {self.agreement_percentage:.2f}%",
            "",
            "NOTICE: Ground truth records represent transcript-grounded factual claims",
            "from synthetic benchmark fixtures, NOT external human auditor decisions.",
        ]
        return "\n".join(lines)

    def format_table(self) -> str:
        """Format the per-check table: Check ID | Ground Truth | System | Match."""
        lines = [
            f"{'Check ID':<35} | {'Ground Truth':<12} | {'System':<12} | {'Match':<6}",
            f"{'-' * 35}-|-{'-' * 12}-|-{'-' * 12}-|-{'-' * 6}",
        ]
        for c in self.comparisons:
            match_str = "YES" if c.is_match else "NO"
            lines.append(f"{c.check_id:<35} | {c.ground_truth_status:<12} | {c.system_status:<12} | {match_str:<6}")
        return "\n".join(lines)


class GroundTruthEvaluator:
    """
    Evaluates system fidelity against verified ground truth records.
    """

    ELIGIBLE_BASIS = "explicitly_stated_in_transcript"
    SYNTHETIC_BASIS = "synthetic_test_variation"

    @classmethod
    def is_eligible(cls, record: Dict[str, Any]) -> bool:
        """
        Check if a ground-truth record is genuinely eligible for evaluation.
        
        Eligible records represent actual transcript-grounded statements.
        Synthetic rate-card perturbations and deliberate negative test variations
        are strictly excluded.
        """
        basis = record.get("basis", "")
        return basis == cls.ELIGIBLE_BASIS

    @classmethod
    def evaluate(
        cls,
        transcript_path: Optional[Union[str, Path]] = None,
        ground_truth_data: Optional[Dict[str, Any]] = None,
        pipeline: Optional[QAPipeline] = None,
        include_synthetic_variations: bool = False,
    ) -> GroundTruthEvaluationReport:
        """
        Execute deterministic evaluation of eligible ground-truth records.
        
        Args:
            transcript_path: Path to broadband transcript JSON.
            ground_truth_data: Raw dictionary of ground truth data.
            pipeline: Pre-configured QAPipeline instance (defaults to offline MockLLMClient).
            include_synthetic_variations: If True, evaluates all records including synthetic variations.
            
        Returns:
            GroundTruthEvaluationReport containing metrics and per-check comparison table.
        """
        project_root = Path(__file__).resolve().parent.parent.parent
        t_path = transcript_path or (project_root / "data" / "broadband_transcript.json")
        gt = ground_truth_data or load_default_broadband_ground_truth(project_root)
        pipe = pipeline or QAPipeline(
            check_library=load_default_broadband_library(project_root),
            ground_truth=gt,
            use_real_anthropic=False,  # Strict offline deterministic evaluation
        )

        all_records = gt.get("ground_truth_records", [])

        # Filter eligible vs excluded records
        if include_synthetic_variations:
            eval_records = all_records
            excluded_check_ids = []
        else:
            eval_records = [r for r in all_records if cls.is_eligible(r)]
            excluded_check_ids = [r.get("check_id") for r in all_records if not cls.is_eligible(r)]

        target_ids = [r["check_id"] for r in eval_records]

        # Execute pipeline
        gate_result = pipe.evaluate_lead(
            raw_transcript=t_path,
            target_check_ids=target_ids,
        )

        system_results_map: Dict[str, CheckResult] = {
            res.check_id: res for res in gate_result.check_results
        }

        comparisons: List[GroundTruthComparison] = []
        correct_count = 0
        incorrect_count = 0
        ambiguous_count = 0

        for r in eval_records:
            cid = r["check_id"]
            expected_status = r.get("test_case_category", "UNKNOWN").upper().strip()
            field_name = r.get("field", "")
            basis = r.get("basis", "")

            sys_result = system_results_map.get(cid)
            if sys_result is not None:
                actual_status = sys_result.status.value
                reason = sys_result.reason
            else:
                actual_status = "MISSING"
                reason = "CheckResult not produced by pipeline"

            is_match = (expected_status == actual_status)

            if is_match:
                correct_count += 1
            else:
                if actual_status == CheckStatus.AMBIGUOUS.value:
                    ambiguous_count += 1
                else:
                    incorrect_count += 1

            comparisons.append(
                GroundTruthComparison(
                    check_id=cid,
                    field=field_name,
                    basis=basis,
                    ground_truth_status=expected_status,
                    system_status=actual_status,
                    is_match=is_match,
                    reason=reason,
                )
            )

        total_eligible = len(eval_records)
        agreement_pct = (correct_count / total_eligible * 100.0) if total_eligible > 0 else 0.0

        return GroundTruthEvaluationReport(
            total_eligible=total_eligible,
            correct=correct_count,
            incorrect=incorrect_count,
            ambiguous=ambiguous_count,
            agreement_percentage=round(agreement_pct, 2),
            comparisons=comparisons,
            excluded_cases=excluded_check_ids,
        )
