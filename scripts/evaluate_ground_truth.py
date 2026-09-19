"""
Deterministic Ground Truth Accuracy Evaluation Script.

Evaluates system CheckResult outcomes against verified ground-truth records:
- Identifies genuinely eligible cases (explicitly stated in transcript)
- Excludes synthetic test variations (synthetic perturbations and omissions)
- Runs existing end-to-end pipeline deterministically (offline MockLLMClient)
- Compares expected ground-truth status vs system CheckResult status
- Prints evaluation report and per-check comparison table
"""

import argparse
from pathlib import Path
import sys

# Ensure root directory is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.evaluation import GroundTruthEvaluator


def main():
    parser = argparse.ArgumentParser(description="Deterministic Ground Truth Accuracy Evaluation")
    parser.add_argument(
        "--include-synthetic",
        action="store_true",
        default=False,
        help="Include synthetic test variations (rate-card perturbations) in addition to eligible transcript-grounded facts.",
    )
    args = parser.parse_args()

    report = GroundTruthEvaluator.evaluate(
        include_synthetic_variations=args.include_synthetic
    )

    print()
    print(report.format_report())
    print()
    print("PER-CHECK EVALUATION TABLE")
    print("--------------------------")
    print(report.format_table())
    print()

    if report.excluded_cases:
        print(f"Excluded synthetic test variations ({len(report.excluded_cases)}):")
        for cid in report.excluded_cases:
            print(f"  - {cid} (synthetic test variation: deliberate rate-card mismatch or omission)")
        print()


if __name__ == "__main__":
    main()
