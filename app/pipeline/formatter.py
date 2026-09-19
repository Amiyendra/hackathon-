"""
Pipeline Trace and Gate Result Formatter.

Formats compact evidence traces and audit summaries with strict PII / PCI redaction:
- Formats failed and reviewed check traces
- Redacts any raw payment information (credit cards, CVVs) and personal identifiers
"""

import re
from typing import List, Optional
from app.factual.models import CheckResult, CheckStatus
from app.gate.models import GateResult


# Regex patterns for accidental PII or PCI data
_CC_REGEX = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
_CVV_REGEX = re.compile(r"\b(?:cvv|cvc|security code)[:\s]+(\d{3,4})\b", re.IGNORECASE)
_EMAIL_REGEX = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b")
_PHONE_REGEX = re.compile(r"\b(?:\+?61|0)[2-478](?:[ -]?[0-9]){8}\b")


def redact_pii_and_pci(text: Optional[str]) -> str:
    """
    Sanitize text to guarantee no raw payment details or PII are printed in traces.
    """
    if not text:
        return "N/A"
    sanitized = str(text)
    # Mask card numbers
    sanitized = _CC_REGEX.sub("[REDACTED_PAYMENT_CARD]", sanitized)
    sanitized = _CVV_REGEX.sub("cvv: [REDACTED_CVV]", sanitized)
    sanitized = _EMAIL_REGEX.sub("[REDACTED_EMAIL]", sanitized)
    sanitized = _PHONE_REGEX.sub("[REDACTED_PHONE]", sanitized)
    return sanitized


def format_compact_evidence_trace(gate_result: GateResult) -> str:
    """
    Generate a compact evidence trace for every failed or reviewed check.
    
    Format:
    CHECK ID
    CATEGORY
    STATUS
    CRITICAL
    EVIDENCE UTTERANCE ID
    ACTUAL TIMESTAMP
    REASON
    """
    lines: List[str] = []
    lines.append("=" * 75)
    lines.append(f"COMPACT EVIDENCE TRACE: LEAD '{gate_result.lead_id or 'UNKNOWN'}'")
    lines.append(f"FINAL DECISION: {gate_result.decision.value}")
    lines.append("=" * 75)

    # Filter for checks that failed or require review
    flagged_results = [
        r for r in gate_result.check_results
        if r.status in (CheckStatus.FAIL, CheckStatus.AMBIGUOUS, CheckStatus.LOW_CONFIDENCE, CheckStatus.UNSUPPORTED_CHECK)
        or (r.critical and r.status == CheckStatus.PASS and r.evidence is None)
    ]

    if not flagged_results:
        lines.append("\n[NO FAILED OR REVIEWED CHECKS DETECTED — ALL EVALUATIONS PASSED]")
        lines.append("=" * 75)
        return "\n".join(lines)

    for idx, r in enumerate(flagged_results, 1):
        ev = r.evidence
        if r.preceding_utterance_id and r.following_utterance_id:
            utt_id = f"{r.preceding_utterance_id} -> {r.following_utterance_id}"
        elif ev and ev.preceding_utterance_id and ev.following_utterance_id:
            utt_id = f"{ev.preceding_utterance_id} -> {ev.following_utterance_id}"
        elif ev:
            utt_id = ev.utterance_id
        else:
            utt_id = "None"
        ts_str = f"[{ev.start_time:.2f}s -> {ev.end_time:.2f}s]" if ev else "N/A"
        sanitized_reason = redact_pii_and_pci(r.reason)

        lines.append(f"\n[{idx}] -----------------------------------------------------------")
        lines.append(f"CHECK ID:              {r.check_id}")
        lines.append(f"CATEGORY:              {r.check_type.value}")
        lines.append(f"STATUS:                {r.status.value}")
        lines.append(f"CRITICAL:              {r.critical}")
        lines.append(f"EVIDENCE UTTERANCE ID: {utt_id}")
        lines.append(f"ACTUAL TIMESTAMP:      {ts_str}")
        lines.append(f"REASON:                {sanitized_reason}")

    lines.append("\n" + "=" * 75)
    return "\n".join(lines)


def format_pipeline_summary(gate_result: GateResult) -> str:
    """Generate a clean human-readable audit summary of the full pipeline evaluation."""
    lines: List[str] = [
        "=" * 75,
        "END-TO-END DETERMINISTIC QA GATE EVALUATION RESULT",
        "=" * 75,
        f"  Lead ID:                   {gate_result.lead_id or 'N/A'}",
        f"  Retailer:                  {gate_result.retailer or 'N/A'}",
        f"  Call Date:                 {gate_result.call_date or 'N/A'}",
        f"  Final Decision:            {gate_result.decision.value}",
        f"  Critical Checks Total:     {gate_result.critical_checks_total}",
        f"  Critical Checks Passed:    {gate_result.critical_checks_passed}",
        f"  Critical Checks Failed:    {gate_result.critical_checks_failed}",
        f"  Critical Checks Ambiguous: {gate_result.critical_checks_ambiguous}",
        f"  Non-Critical Failures:     {gate_result.non_critical_failures} (Non-blocking)",
        f"  Blocking Check IDs (HOLD): {gate_result.blocking_check_ids}",
        f"  Review Check IDs (REVIEW): {gate_result.review_check_ids}",
        f"  Total Checks Preserved:    {len(gate_result.check_results)}",
        "  Human-Readable Reasons:",
    ]
    for r in gate_result.reasons:
        lines.append(f"    * {redact_pii_and_pci(r)}")
    lines.append("=" * 75)
    return "\n".join(lines)
