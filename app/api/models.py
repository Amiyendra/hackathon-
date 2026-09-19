"""
API Request and Response Models for QA Gate Layer.

Reuses existing domain models (GateResult, CheckResult, EvidenceReference)
to enforce zero duplication of business models or validation rules.
"""

from typing import Any, Dict, List, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

from app.gate.models import GateResult
from app.models import CanonicalTranscript


class IngestionResponse(BaseModel):
    """Response payload for transcript ingestion."""
    ingestion_id: str = Field(..., description="Unique ID for the ingested transcript session")
    lead_id: Optional[str] = Field(default=None, description="Lead ID extracted or provided")
    retailer: Optional[str] = Field(default=None, description="Retailer extracted or provided")
    call_date: Optional[str] = Field(default=None, description="Call date in YYYY-MM-DD format")
    utterance_count: int = Field(..., description="Number of canonical utterances in the transcript")
    status: str = Field(default="READY_FOR_QA", description="Ingestion readiness status")
    transcript: Optional[CanonicalTranscript] = Field(default=None, description="Normalized canonical transcript")


class QARunRequest(BaseModel):
    """Request payload for executing the QA Gate evaluation pipeline."""
    model_config = ConfigDict(extra="forbid")

    scenario: Optional[str] = Field(
        default=None,
        description="Deterministic demo scenario name ('default', 'auto_submit', 'hold', 'qa_review').",
    )
    ingestion_id: Optional[str] = Field(
        default=None,
        description="Ingestion ID from a prior uploaded transcript.",
    )
    transcript: Optional[Union[Dict[str, Any], CanonicalTranscript, str]] = Field(
        default=None,
        description="Raw transcript dict, CanonicalTranscript, or JSON string. If omitted, uses default broadband lead.",
    )
    lead_id: Optional[str] = Field(
        default=None,
        description="Optional lead ID override.",
    )
    retailer: Optional[str] = Field(
        default=None,
        description="Retailer or provider identifier (e.g. 'TANGENT_BROADBAND').",
    )
    call_date: Optional[str] = Field(
        default=None,
        description="Call date in YYYY-MM-DD format.",
    )
    expected_values_override: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Optional expected value overrides for testing rate-card variations.",
    )
    target_check_ids: Optional[List[str]] = Field(
        default=None,
        description="Optional subset of check IDs to evaluate.",
    )
    use_real_anthropic: bool = Field(
        default=False,
        description="Whether to invoke live Anthropic Claude API. Defaults to False (offline MockLLMClient).",
    )


class HealthResponse(BaseModel):
    """System health and operational status response."""
    status: str = Field(default="ok", description="Service health status")
    service: str = Field(default="qa-gate-backend", description="Service name")
    version: str = Field(default="1.0.0", description="API version")
    checks_loaded: int = Field(..., description="Number of active checks in check library")
    default_provider: str = Field(default="MockLLMClient (Offline)", description="Default LLM client provider")


class ScenarioInfo(BaseModel):
    """Metadata describing a pre-configured deterministic demo scenario."""
    scenario_id: str = Field(..., description="Scenario identifier")
    name: str = Field(..., description="Human-readable scenario name")
    description: str = Field(..., description="Description of scenario logic")
    expected_decision: str = Field(..., description="Expected Gate decision ('AUTO_SUBMIT', 'HOLD', 'QA_REVIEW')")


__all__ = [
    "IngestionResponse",
    "QARunRequest",
    "HealthResponse",
    "ScenarioInfo",
    "GateResult",
]
