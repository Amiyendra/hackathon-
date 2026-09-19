"""
End-to-End QA Pipeline Module.

Exports:
- QAPipeline: Orchestration class
- run_pipeline: Functional orchestration entry point
- load_default_broadband_library: Loads combined broadband check library
- load_default_broadband_ground_truth: Loads default broadband ground truth
- format_compact_evidence_trace: Compact trace of failed/reviewed checks
- format_pipeline_summary: Full audit summary formatter
- redact_pii_and_pci: PII / PCI sanitization function
"""

from app.pipeline.formatter import (
    format_compact_evidence_trace,
    format_pipeline_summary,
    redact_pii_and_pci,
)
from app.pipeline.orchestrator import (
    QAPipeline,
    load_default_broadband_ground_truth,
    load_default_broadband_library,
    run_pipeline,
)

__all__ = [
    "QAPipeline",
    "run_pipeline",
    "load_default_broadband_library",
    "load_default_broadband_ground_truth",
    "format_compact_evidence_trace",
    "format_pipeline_summary",
    "redact_pii_and_pci",
]
