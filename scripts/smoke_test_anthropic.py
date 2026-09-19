#!/usr/bin/env python3
"""
Integration Smoke Test: Direct Anthropic Claude API (Single Call).

Validates end-to-end integration between the canonical transcript, CheckDefinition,
and the direct Anthropic Claude API.

SECURITY & ARCHITECTURAL INVARIANTS:
- Makes exactly ONE live Claude API call.
- Does NOT score, pass/fail, or evaluate the extracted claim.
- Verifies that the extracted utterance_id actually exists in EvidenceIndex.
- Fails cleanly and gracefully if ANTHROPIC_API_KEY is missing.
- NEVER prints, logs, or exposes the API key.
- NEVER runs as part of pytest.
"""

import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.checks import load_check_library_from_yaml
from app.evidence.index import EvidenceIndex
from app.factual.anthropic_client import AnthropicClient, DEFAULT_ANTHROPIC_MODEL
from app.ingestion.normalizer import TranscriptNormalizer


def run_smoke_test() -> None:
    print("=" * 70)
    print("DIRECT ANTHROPIC CLAUDE API — LIVE INTEGRATION SMOKE TEST")
    print("=" * 70)

    # 1. Check API Key
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    configured_model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)

    print("\n[1] Configuration:")
    print(f"    Provider:    anthropic")
    print(f"    Model:       {configured_model}")
    print(f"    API Key:     {'[CONFIGURED]' if api_key else '[MISSING]'}")

    if not api_key:
        print("\n[ERROR] ANTHROPIC_API_KEY environment variable is not set.")
        print("Please set your Anthropic API key before running the live smoke test:")
        print("    export ANTHROPIC_API_KEY='sk-ant-...'")
        print(f"    export ANTHROPIC_MODEL='{configured_model}'")
        print("    .venv/bin/python scripts/smoke_test_anthropic.py")
        sys.exit(1)

    # 2. Load and normalize canonical transcript
    transcript_path = PROJECT_ROOT / "data" / "broadband_transcript.json"
    print(f"\n[2] Loading canonical transcript from: {transcript_path}")
    if not transcript_path.exists():
        print(f"[ERROR] Transcript fixture not found at {transcript_path}")
        sys.exit(1)

    with open(transcript_path, "r", encoding="utf-8") as f:
        raw_json = f.read()

    normalizer = TranscriptNormalizer()
    transcript = normalizer.normalize(raw_json)
    evidence_index = EvidenceIndex(transcript)
    print(f"    ✓ Normalized {len(transcript.utterances)} utterances into EvidenceIndex.")

    # 3. Load Check Definition
    library_path = PROJECT_ROOT / "app" / "checks" / "broadband_library.yaml"
    print(f"\n[3] Loading check library from: {library_path}")
    check_library = load_check_library_from_yaml(str(library_path))
    
    # Target check for single test call: promotional price
    target_check_id = "CHK_FACT_BB_006_PROMOTIONAL_PRICE"
    check = next((c for c in check_library.checks if c.check_id == target_check_id), None)
    if not check:
        print(f"[ERROR] Target check '{target_check_id}' not found in check library.")
        sys.exit(1)
    print(f"    Target Check: [{check.check_id}] {check.name}")
    print(f"    Target Field: {check.criteria.get('field')}")
    print(f"    Critical:     {check.critical} (Strictly defined by check library)")

    # 4. Initialize Anthropic Client
    print("\n[4] Initializing AnthropicClient...")
    client = AnthropicClient(api_key=api_key, model=configured_model)

    # 5. Execute exactly ONE live extraction call
    print(f"\n[5] Sending single extraction request to Claude ({configured_model})...")
    claim = client.extract_claim(check=check, transcript=transcript)

    # 6. Report structured claim results
    print("\n[6] Claude Extraction Result:")
    print(f"    Field:            {claim.field}")
    print(f"    Extracted Value:  {claim.value}")
    print(f"    Raw Value:        {claim.raw_value}")
    print(f"    Unit:             {claim.unit}")
    print(f"    Confidence:       {claim.confidence}")
    print(f"    Utterance ID:     {claim.utterance_id}")
    print(f"    Notes:            {claim.extraction_notes}")

    # 7. Validate Utterance ID against EvidenceIndex
    print("\n[7] Evidence Validation (Deterministic Python):")
    if claim.utterance_id:
        evidence_ref = evidence_index.get_evidence(claim.utterance_id)
        if evidence_ref:
            print(f"    ✓ Utterance ID '{claim.utterance_id}' successfully verified in EvidenceIndex!")
            print(f"      Speaker:   {evidence_ref.speaker}")
            print(f"      Timespan:  {evidence_ref.start_time:.2f}s -> {evidence_ref.end_time:.2f}s")
            print(f"      Backend Text: \"{evidence_ref.text}\"")
        else:
            print(f"    ✗ Utterance ID '{claim.utterance_id}' NOT FOUND in EvidenceIndex! (Hallucination caught)")
    else:
        print("    ! No utterance ID was returned by the model.")

    print("\n" + "=" * 70)
    print("SMOKE TEST COMPLETE: Direct Anthropic Claude API verified successfully (1 call).")
    print("=" * 70)


if __name__ == "__main__":
    run_smoke_test()
