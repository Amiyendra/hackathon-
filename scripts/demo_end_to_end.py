"""
End-to-End Real Lead Demonstration Script (Phase 7).

Demonstrates the complete pipeline:
input transcript
→ canonical transcript normalization
→ EvidenceIndex
→ versioned check-library resolution (retailer + call date)
→ Verbatim QA
→ Factual QA
→ Behaviour QA
→ aggregate CheckResults
→ DeterministicGate
→ final AUTO_SUBMIT / HOLD / QA_REVIEW

Includes:
- Offline deterministic execution by default (using MockLLMClient)
- Optional --live-anthropic flag to run against Claude Sonnet 5 via direct Anthropic API
- Compact evidence traces for all failed/reviewed checks
- Strict PII / PCI redaction
"""

import argparse
from pathlib import Path
import sys

# Ensure root directory is in sys.path
project_root = Path(__file__).resolve().parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.pipeline import (
    QAPipeline,
    format_compact_evidence_trace,
    format_pipeline_summary,
    load_default_broadband_ground_truth,
    load_default_broadband_library,
)


def main():
    parser = argparse.ArgumentParser(description="End-to-End QA Gate Lead Evaluation Demo")
    parser.add_argument(
        "--live-anthropic",
        action="store_true",
        default=False,
        help="Execute real Anthropic Claude API calls (requires ANTHROPIC_API_KEY environment variable).",
    )
    parser.add_argument(
        "--scenario",
        choices=["default", "auto_submit", "hold", "qa_review"],
        default="default",
        help="Demonstration scenario to run (default: full broadband lead evaluation).",
    )
    args = parser.parse_args()

    transcript_path = project_root / "data" / "broadband_transcript.json"

    print("=" * 75)
    print("PHASE 7 DEMONSTRATION: DETERMINISTIC END-TO-END PIPELINE")
    print("=" * 75)
    print(f"Transcript:             {transcript_path.name}")
    print(f"Provider / LLM:         {'LIVE Direct Anthropic Claude' if args.live_anthropic else 'Deterministic MockLLMClient (Offline)'}")
    print(f"Scenario:               {args.scenario.upper()}")
    print("=" * 75)

    library = load_default_broadband_library()
    ground_truth = load_default_broadband_ground_truth()

    pipeline = QAPipeline(
        check_library=library,
        ground_truth=ground_truth,
        use_real_anthropic=args.live_anthropic,
    )

    # Scenarios for demonstration:
    # 1. 'default': Full broadband lead (evaluates all active checks)
    # 2. 'auto_submit': Verified passing checks + non-blocking behaviour failure
    # 3. 'hold': Rate-card mismatch
    # 4. 'qa_review': Ambiguous / missing check
    if args.scenario == "auto_submit":
        target_ids = [
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
        gate_result = pipeline.evaluate_lead(
            raw_transcript=transcript_path,
            target_check_ids=target_ids,
        )
    elif args.scenario == "hold":
        gate_result = pipeline.evaluate_lead(
            raw_transcript=transcript_path,
            expected_values_override={"CHK_FACT_BB_006_PROMOTIONAL_PRICE": 55.0},
        )
    elif args.scenario == "qa_review":
        gate_result = pipeline.evaluate_lead(
            raw_transcript=transcript_path,
            target_check_ids=["CHK_VERB_BB_003_RECORDING_DISCLOSURE"],
        )
    else:
        # Default full broadband run
        gate_result = pipeline.evaluate_lead(raw_transcript=transcript_path)

    # 1. Print full evaluation summary
    print("\n" + format_pipeline_summary(gate_result))

    # 2. Print compact evidence trace for failed/reviewed checks
    print("\n" + format_compact_evidence_trace(gate_result))


if __name__ == "__main__":
    main()
