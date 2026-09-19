"""
Unit and Integration Tests for FastAPI QA Gate API Layer.

Tests all required API capabilities:
- Health endpoint
- Successful QA evaluation run
- HOLD decision scenario
- QA_REVIEW decision scenario
- AUTO_SUBMIT decision scenario
- Custom transcript submission
- Malformed inputs and validation error handling
- Scenario and check definition listing
"""

import pytest
from fastapi.testclient import TestClient

from app.api import app


@pytest.fixture
def client() -> TestClient:
    """Create a FastAPI test client for offline API evaluation."""
    return TestClient(app)


# -----------------------------------------------------------------------------
# 1. Health Endpoint
# -----------------------------------------------------------------------------
def test_health_endpoint(client: TestClient):
    """GET /health must return operational status, service name, and loaded checks."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["service"] == "qa-gate-backend"
    assert data["version"] == "1.0.0"
    assert data["checks_loaded"] >= 20
    assert "MockLLMClient" in data["default_provider"]


# -----------------------------------------------------------------------------
# 2. Successful QA Run (Default Broadband Lead)
# -----------------------------------------------------------------------------
def test_qa_run_successful_default(client: TestClient):
    """POST /api/v1/qa/run with empty body or default scenario returns structured GateResult."""
    response = client.post("/api/v1/qa/run", json={})
    assert response.status_code == 200
    data = response.json()

    # Core GateResult fields
    assert data["lead_id"] == "broadband_call_20260919_001"
    assert data["retailer"] == "TANGENT_BROADBAND"
    assert data["call_date"] == "2026-09-19"
    assert data["decision"] in ("AUTO_SUBMIT", "HOLD", "QA_REVIEW")
    assert isinstance(data["critical_checks_total"], int)
    assert isinstance(data["critical_checks_passed"], int)
    assert isinstance(data["critical_checks_failed"], int)
    assert isinstance(data["reasons"], list)
    assert isinstance(data["gate_explanation"], str)
    assert len(data["gate_explanation"]) > 0

    # Underlying check results
    check_results = data["check_results"]
    assert len(check_results) >= 20

    first_check = check_results[0]
    assert "check_id" in first_check
    assert "check_type" in first_check
    assert "critical" in first_check
    assert "status" in first_check
    assert "confidence" in first_check
    assert "expected" in first_check
    assert "observed" in first_check
    assert "reason" in first_check


# -----------------------------------------------------------------------------
# 3. AUTO_SUBMIT Result Scenario
# -----------------------------------------------------------------------------
def test_qa_run_auto_submit_scenario(client: TestClient):
    """POST /api/v1/qa/run with scenario='auto_submit' returns AUTO_SUBMIT decision."""
    response = client.post("/api/v1/qa/run", json={"scenario": "auto_submit"})
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "AUTO_SUBMIT"
    assert data["critical_checks_failed"] == 0
    assert data["critical_checks_ambiguous"] == 0
    assert data["blocking_check_ids"] == []
    assert data["review_check_ids"] == []
    assert "AUTO_SUBMIT" in data["gate_explanation"]

    # Dead air check is non-blocking and flagged as a non-critical failure
    dead_air_result = next(c for c in data["check_results"] if c["check_id"] == "CHK_BEHAV_BB_002_DEAD_AIR_STRICT")
    assert dead_air_result["status"] == "FAIL"
    assert dead_air_result["critical"] is False
    assert dead_air_result["evidence"] is not None
    assert dead_air_result["evidence"]["start_time"] == 4.50
    assert dead_air_result["evidence"]["end_time"] == 4.80
    assert dead_air_result["evidence"]["duration"] == 0.30


# -----------------------------------------------------------------------------
# 4. HOLD Result Scenario
# -----------------------------------------------------------------------------
def test_qa_run_hold_scenario(client: TestClient):
    """POST /api/v1/qa/run with scenario='hold' returns HOLD due to rate-card mismatch."""
    response = client.post("/api/v1/qa/run", json={"scenario": "hold"})
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "HOLD"
    assert data["critical_checks_failed"] >= 1
    assert "CHK_FACT_BB_006_PROMOTIONAL_PRICE" in data["blocking_check_ids"]
    assert "HOLD" in data["gate_explanation"]


# -----------------------------------------------------------------------------
# 5. QA_REVIEW Result Scenario
# -----------------------------------------------------------------------------
def test_qa_run_qa_review_scenario(client: TestClient):
    """POST /api/v1/qa/run with scenario='qa_review' returns QA_REVIEW disposition."""
    response = client.post("/api/v1/qa/run", json={"scenario": "qa_review"})
    assert response.status_code == 200
    data = response.json()

    assert data["decision"] == "QA_REVIEW"
    assert "qa review" in data["gate_explanation"].lower()
    assert len(data["check_results"]) >= 1
    assert any(c["check_id"] == "CHK_VERB_BB_003_RECORDING_DISCLOSURE" for c in data["check_results"])


# -----------------------------------------------------------------------------
# 6. Custom Transcript Input
# -----------------------------------------------------------------------------
def test_qa_run_custom_transcript_input(client: TestClient):
    """POST /api/v1/qa/run accepts an explicit custom transcript dict."""
    custom_transcript = {
        "call_metadata": {
            "call_id": "custom_call_999",
            "retailer": "TANGENT_BROADBAND",
            "call_date": "2026-09-19",
        },
        "utterances": [
            {
                "utterance_id": "utt_001",
                "speaker": "AGENT",
                "start_time": 0.0,
                "end_time": 3.0,
                "text": "Thanks for calling Tangent Broadband sales. My name is Alex.",
            },
            {
                "utterance_id": "utt_002",
                "speaker": "CUSTOMER",
                "start_time": 3.5,
                "end_time": 6.0,
                "text": "Hi Alex, I want to inquire about home internet.",
            },
        ],
    }

    response = client.post(
        "/api/v1/qa/run",
        json={
            "transcript": custom_transcript,
            "target_check_ids": ["CHK_VERB_BB_001_GREETING_BRAND"],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["lead_id"] == "custom_call_999"
    assert len(data["check_results"]) == 1
    check = data["check_results"][0]
    assert check["check_id"] == "CHK_VERB_BB_001_GREETING_BRAND"
    assert check["status"] == "PASS"
    assert check["evidence"]["utterance_id"] == "utt_001"


def test_qa_run_critical_ambiguous_causes_qa_review_with_review_check_ids(client: TestClient):
    """Submitting custom transcript without customer name claim triggers QA_REVIEW with review_check_ids."""
    custom_transcript = {
        "call_metadata": {
            "call_id": "review_call_888",
            "retailer": "TANGENT_BROADBAND",
            "call_date": "2026-09-19",
        },
        "utterances": [
            {
                "utterance_id": "utt_001",
                "speaker": "AGENT",
                "start_time": 0.0,
                "end_time": 3.0,
                "text": "Thanks for calling Tangent Broadband sales.",
            },
        ],
    }
    response = client.post(
        "/api/v1/qa/run",
        json={
            "transcript": custom_transcript,
            "target_check_ids": ["CHK_FACT_BB_002_CUSTOMER_NAME"],
            "expected_values_override": {"CHK_FACT_BB_002_CUSTOMER_NAME": "Sarah"},
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["decision"] == "QA_REVIEW"
    assert "CHK_FACT_BB_002_CUSTOMER_NAME" in data["review_check_ids"]
    assert data["critical_checks_ambiguous"] == 1


# -----------------------------------------------------------------------------
# 7. Malformed Inputs
# -----------------------------------------------------------------------------
def test_qa_run_malformed_unknown_scenario(client: TestClient):
    """POST /api/v1/qa/run with unknown scenario name returns HTTP 400."""
    response = client.post("/api/v1/qa/run", json={"scenario": "non_existent_scenario_123"})
    assert response.status_code == 400
    assert "Unsupported scenario" in response.json()["detail"]


def test_qa_run_malformed_transcript_string(client: TestClient):
    """POST /api/v1/qa/run with malformed transcript string returns HTTP 400."""
    response = client.post("/api/v1/qa/run", json={"transcript": "definitely_not_valid_json_or_filepath"})
    assert response.status_code == 400
    assert "Invalid or malformed transcript input" in response.json()["detail"]


def test_qa_run_malformed_payload_extra_field(client: TestClient):
    """POST /api/v1/qa/run with unpermitted extra field returns HTTP 422 (extra='forbid')."""
    response = client.post("/api/v1/qa/run", json={"unpermitted_extra_field": 123})
    assert response.status_code == 422


def test_qa_run_malformed_payload_invalid_type(client: TestClient):
    """POST /api/v1/qa/run with invalid field types returns HTTP 422."""
    response = client.post("/api/v1/qa/run", json={"use_real_anthropic": "not_a_bool"})
    assert response.status_code == 422


def test_frontend_cannot_override_gate_confidence_threshold(client: TestClient):
    """
    Gate Integrity Audit: Frontend must NOT be able to arbitrarily change
    the deterministic QA gate's confidence threshold via the request body.
    Any attempt must be rejected with HTTP 422.
    """
    response = client.post("/api/v1/qa/run", json={"min_confidence_threshold": 0.10})
    assert response.status_code == 422
    assert "extra_forbidden" in str(response.json())


def test_internal_test_confidence_header_and_schema_isolation(client: TestClient):
    """
    Internal test-only confidence header is supported for offline test harnesses
    without being exposed in the public OpenAPI schema.
    """
    # 1. Internal header works for testing
    response = client.post(
        "/api/v1/qa/run",
        json={"scenario": "auto_submit"},
        headers={"X-Test-Min-Confidence-Threshold": "0.80"},
    )
    assert response.status_code == 200
    assert response.json()["decision"] == "AUTO_SUBMIT"

    # 2. Public OpenAPI schema does NOT expose min_confidence_threshold in QARunRequest
    openapi_res = client.get("/openapi.json")
    assert openapi_res.status_code == 200
    schema = openapi_res.json()
    qa_request_properties = schema["components"]["schemas"]["QARunRequest"]["properties"]
    assert "min_confidence_threshold" not in qa_request_properties


# -----------------------------------------------------------------------------
# 8. Scenario and Check Definitions Endpoints
# -----------------------------------------------------------------------------
def test_scenarios_listing_endpoint(client: TestClient):
    """GET /api/v1/scenarios returns available deterministic scenarios."""
    response = client.get("/api/v1/scenarios")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 4
    scenario_ids = [s["scenario_id"] for s in data]
    assert "default" in scenario_ids
    assert "auto_submit" in scenario_ids
    assert "hold" in scenario_ids
    assert "qa_review" in scenario_ids


def test_checks_listing_endpoint(client: TestClient):
    """GET /api/v1/checks returns check definitions from check library."""
    response = client.get("/api/v1/checks")
    assert response.status_code == 200
    data = response.json()
    assert len(data) >= 20
    assert any(c["check_id"] == "CHK_VERB_BB_001_GREETING_BRAND" for c in data)
