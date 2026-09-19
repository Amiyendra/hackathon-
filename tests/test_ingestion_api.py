"""
Unit and Integration tests for Transcript Ingestion API and Ingestion-Driven QA.

Verifies:
1. Valid transcript upload via multipart/form-data.
2. Valid transcript upload via application/json.
3. Ingestion with explicit metadata overrides.
4. Missing file in multipart upload (400).
5. Malformed JSON upload (400).
6. Non-monotonic utterance timing (400).
7. Missing utterances / empty list (400).
8. QA run from valid ingestion_id through existing pipeline.
9. QA run with unknown ingestion_id returns 404.
10. Dynamic transcript retrieval via GET /api/v1/transcript?ingestion_id=...
11. Retailers list endpoint GET /api/v1/retailers.
12. Anthropic LLM configuration: fails explicitly (503) without silent fallback.
"""

import io
import json
import os
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient

from app.api.app import app
from app.api.ingestion_store import ingestion_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def clean_store():
    """Clear ingestion store between test runs."""
    ingestion_store.clear()
    yield
    ingestion_store.clear()


@pytest.fixture
def valid_transcript_data():
    return {
        "transcript_id": "test_call_001",
        "call_metadata": {
            "lead_id": "LEAD_TEST_999",
            "retailer": "TANGENT_BROADBAND",
            "call_date": "2026-09-19",
        },
        "utterances": [
            {
                "utterance_id": "utt_001",
                "speaker": "AGENT",
                "start_time": 0.0,
                "end_time": 4.5,
                "text": "Thanks for calling Tangent Broadband sales. My name is Alex.",
            },
            {
                "utterance_id": "utt_002",
                "speaker": "CUSTOMER",
                "start_time": 4.8,
                "end_time": 8.0,
                "text": "Hi, I am looking for a fast NBN plan.",
            },
        ],
    }


def test_multipart_upload_success(valid_transcript_data):
    """Test successful transcript file upload via multipart/form-data."""
    json_bytes = json.dumps(valid_transcript_data).encode("utf-8")
    files = {"file": ("transcript.json", io.BytesIO(json_bytes), "application/json")}
    data = {"retailer": "TANGENT_BROADBAND", "call_date": "2026-09-19"}

    response = client.post("/api/v1/ingest/transcript", files=files, data=data)
    assert response.status_code == 201
    payload = response.json()

    assert "ingestion_id" in payload
    assert payload["ingestion_id"].startswith("ingest_")
    assert payload["lead_id"] == "LEAD_TEST_999"
    assert payload["retailer"] == "TANGENT_BROADBAND"
    assert payload["call_date"] == "2026-09-19"
    assert payload["utterance_count"] == 2
    assert payload["status"] == "READY_FOR_QA"


def test_json_body_upload_success(valid_transcript_data):
    """Test successful transcript ingestion via direct JSON body."""
    response = client.post(
        "/api/v1/ingest/transcript",
        json=valid_transcript_data,
        headers={"Content-Type": "application/json"},
    )
    assert response.status_code == 201
    payload = response.json()

    assert payload["ingestion_id"].startswith("ingest_")
    assert payload["lead_id"] == "LEAD_TEST_999"
    assert payload["retailer"] == "TANGENT_BROADBAND"
    assert payload["utterance_count"] == 2


def test_multipart_missing_file():
    """Multipart upload without file field returns 400."""
    response = client.post(
        "/api/v1/ingest/transcript",
        data={"lead_id": "123"},
        headers={"Content-Type": "multipart/form-data"},
    )
    assert response.status_code == 400


def test_malformed_json_upload():
    """Malformed JSON upload returns 400."""
    files = {"file": ("broken.json", io.BytesIO(b"{not valid json!"), "application/json")}
    response = client.post("/api/v1/ingest/transcript", files=files)
    assert response.status_code == 400
    assert "Malformed JSON" in response.json()["detail"]


def test_empty_utterances_upload():
    """Uploading transcript with no utterances returns 400."""
    payload = {"transcript_id": "empty", "utterances": []}
    response = client.post("/api/v1/ingest/transcript", json=payload)
    assert response.status_code == 400
    assert "no utterances" in response.json()["detail"]


def test_non_monotonic_timing_rejected():
    """Utterances with non-monotonic timestamps are strictly rejected."""
    bad_data = {
        "utterances": [
            {"speaker": "AGENT", "start_time": 5.0, "end_time": 8.0, "text": "First"},
            {"speaker": "CUSTOMER", "start_time": 3.0, "end_time": 4.0, "text": "Earlier than first!"},
        ]
    }
    response = client.post("/api/v1/ingest/transcript", json=bad_data)
    assert response.status_code == 400
    assert "monotonically" in response.json()["detail"]


def test_negative_timestamp_rejected():
    """Utterance with negative timestamp is rejected."""
    bad_data = {
        "utterances": [
            {"speaker": "AGENT", "start_time": -1.0, "end_time": 2.0, "text": "Hello"},
        ]
    }
    response = client.post("/api/v1/ingest/transcript", json=bad_data)
    assert response.status_code == 400
    assert "negative" in response.json()["detail"]


def test_qa_run_from_ingestion_id(valid_transcript_data):
    """Test full QA evaluation executed from an ingested transcript ID."""
    # 1. Ingest transcript
    ingest_resp = client.post("/api/v1/ingest/transcript", json=valid_transcript_data)
    assert ingest_resp.status_code == 201
    ingestion_id = ingest_resp.json()["ingestion_id"]

    # 2. Run QA using ingestion_id
    qa_resp = client.post("/api/v1/qa/run", json={"ingestion_id": ingestion_id})
    assert qa_resp.status_code == 200
    gate_result = qa_resp.json()

    assert gate_result["lead_id"] == "LEAD_TEST_999"
    assert gate_result["retailer"] == "TANGENT_BROADBAND"
    assert "decision" in gate_result
    assert gate_result["decision"] in ["AUTO_SUBMIT", "HOLD", "QA_REVIEW"]
    assert len(gate_result["check_results"]) > 0


def test_qa_run_invalid_ingestion_id():
    """Running QA with non-existent ingestion_id returns 404."""
    response = client.post("/api/v1/qa/run", json={"ingestion_id": "ingest_does_not_exist"})
    assert response.status_code == 404
    assert "not found" in response.json()["detail"]


def test_get_transcript_by_ingestion_id(valid_transcript_data):
    """Test retrieving canonical transcript using ingestion_id."""
    ingest_resp = client.post("/api/v1/ingest/transcript", json=valid_transcript_data)
    ingestion_id = ingest_resp.json()["ingestion_id"]

    resp = client.get(f"/api/v1/transcript?ingestion_id={ingestion_id}")
    assert resp.status_code == 200
    payload = resp.json()

    assert payload["lead_id"] == "LEAD_TEST_999"
    assert len(payload["utterances"]) == 2
    assert payload["utterances"][0]["text"] == valid_transcript_data["utterances"][0]["text"]


def test_list_retailers_endpoint():
    """GET /api/v1/retailers returns list of configured retailers."""
    resp = client.get("/api/v1/retailers")
    assert resp.status_code == 200
    retailers = resp.json()
    assert isinstance(retailers, list)
    assert "TANGENT_BROADBAND" in retailers


def test_anthropic_missing_credentials_fails_with_503(valid_transcript_data):
    """When FACTUAL_LLM_PROVIDER=anthropic without API key, returns explicit 503 error."""
    # Ensure ANTHROPIC_API_KEY is not set
    env = dict(os.environ)
    env["FACTUAL_LLM_PROVIDER"] = "anthropic"
    env.pop("ANTHROPIC_API_KEY", None)

    with patch.dict(os.environ, env, clear=True):
        resp = client.post(
            "/api/v1/qa/run",
            json={"transcript": valid_transcript_data},
        )
        assert resp.status_code == 503
        detail = resp.json()["detail"]
        assert "Anthropic API credentials" in detail


def test_anthropic_use_real_anthropic_flag_without_key_fails(valid_transcript_data):
    """Requesting use_real_anthropic=True without API key returns 503."""
    env = dict(os.environ)
    env.pop("ANTHROPIC_API_KEY", None)

    with patch.dict(os.environ, env, clear=True):
        resp = client.post(
            "/api/v1/qa/run",
            json={"transcript": valid_transcript_data, "use_real_anthropic": True},
        )
        assert resp.status_code == 503
        assert "Anthropic API credentials" in resp.json()["detail"]
