#!/usr/bin/env python3
"""
Verification script for real Anthropic runtime path.

Verifies:
1. Ingests uploaded transcript via POST /api/v1/ingest/transcript
2. Runs live QA evaluation via POST /api/v1/qa/run with ingestion_id
3. Tracks AnthropicClient vs MockLLMClient invocations
4. Confirms exactly zero MockLLMClient calls occurred
5. Confirms AnthropicClient made the live API call
6. Confirms API response does not expose ANTHROPIC_API_KEY
7. Prints only safe diagnostics:
   provider=anthropic
   model=<configured model>
   number of Anthropic calls
   final decision
   critical pass/fail/review counts
"""

import json
import os
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

# Ensure .env is loaded
from app.config import load_dotenv_if_present
load_dotenv_if_present()

from fastapi.testclient import TestClient
from app.api.app import app
from app.factual.anthropic_client import AnthropicClient, DEFAULT_ANTHROPIC_MODEL
from app.factual.llm import MockLLMClient


def run_verification():
    # 1. Check environment
    provider = os.environ.get("FACTUAL_LLM_PROVIDER", "").strip().lower()
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    model = os.environ.get("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)

    assert provider == "anthropic", f"FACTUAL_LLM_PROVIDER must be 'anthropic', got '{provider}'"
    assert api_key, "ANTHROPIC_API_KEY must be configured in .env"

    # 2. Track invocations on AnthropicClient and MockLLMClient
    anthropic_call_count = 0
    mock_call_count = 0

    orig_anthropic_extract = AnthropicClient.extract_claim
    orig_mock_extract = MockLLMClient.extract_claim

    def tracked_anthropic_extract(self, check, transcript):
        nonlocal anthropic_call_count
        anthropic_call_count += 1
        return orig_anthropic_extract(self, check, transcript)

    def tracked_mock_extract(self, *args, **kwargs):
        nonlocal mock_call_count
        mock_call_count += 1
        return orig_mock_extract(self, *args, **kwargs)

    AnthropicClient.extract_claim = tracked_anthropic_extract
    MockLLMClient.extract_claim = tracked_mock_extract

    try:
        client = TestClient(app)

        # 3. Ingest transcript file via multipart/form-data
        transcript_path = PROJECT_ROOT / "data" / "broadband_transcript.json"
        with open(transcript_path, "rb") as f:
            files = {"file": ("broadband_transcript.json", f, "application/json")}
            data = {"retailer": "TANGENT_BROADBAND", "call_date": "2026-09-19"}
            ingest_resp = client.post("/api/v1/ingest/transcript", files=files, data=data)

        assert ingest_resp.status_code == 201, f"Ingest failed: {ingest_resp.text}"
        ingestion_id = ingest_resp.json()["ingestion_id"]

        # 4. Execute QA run using ingestion_id
        # Target minimum factual checks to prove live path without burning tokens
        target_checks = [
            "CHK_FACT_BB_006_PROMOTIONAL_PRICE",
            "CHK_VERB_BB_001_GREETING_BRAND",
            "CHK_BEHAV_BB_001_DEAD_AIR",
        ]
        qa_resp = client.post(
            "/api/v1/qa/run",
            json={
                "ingestion_id": ingestion_id,
                "target_check_ids": target_checks,
            },
        )
        assert qa_resp.status_code == 200, f"QA run failed: {qa_resp.text}"
        gate_result = qa_resp.json()

        # 5. Verify security: ensure API key is nowhere in the response
        resp_str = json.dumps(gate_result)
        assert api_key not in resp_str, "CRITICAL: API key found in API response!"
        ingest_str = json.dumps(ingest_resp.json())
        assert api_key not in ingest_str, "CRITICAL: API key found in ingestion response!"

        # 6. Verify client invocation counts
        assert anthropic_call_count >= 1, f"AnthropicClient was not called! Count: {anthropic_call_count}"
        assert mock_call_count == 0, f"MockLLMClient was invoked during live run! Count: {mock_call_count}"

        # 7. Print safe diagnostics (never API key or raw prompt text)
        print(f"provider={provider}")
        print(f"model={model}")
        print(f"number of Anthropic calls={anthropic_call_count}")
        print(f"number of MockLLM calls={mock_call_count}")
        print(f"final decision={gate_result['decision']}")
        print(f"critical passed={gate_result['critical_checks_passed']}")
        print(f"critical failed={gate_result['critical_checks_failed']}")
        print(f"critical review={gate_result['critical_checks_ambiguous']}")
        print(f"non-critical warnings={gate_result['non_critical_failures']}")
        print("security check: API key not exposed in response=PASSED")
        print("mock client isolation check: MockLLM calls=0=PASSED")

    finally:
        # Restore original methods
        AnthropicClient.extract_claim = orig_anthropic_extract
        MockLLMClient.extract_claim = orig_mock_extract


if __name__ == "__main__":
    run_verification()
