"""
Factual Match Engine Data Models.

CRITICAL ARCHITECTURAL BOUNDARY:
- The LLM is NEVER the final authority.
- The LLM may only extract what was claimed, its utterance ID, and extraction confidence.
- The LLM MUST NOT decide PASS, FAIL, AMBIGUOUS, criticality, check version, or timestamps.
- Criticality, check_version, and expected values are strictly derived from the CheckDefinition and ground truth.
- Timestamps and evidence references are strictly derived from EvidenceIndex.
"""

from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field

from app.checks.models import CheckType
from app.models import EvidenceReference


class CheckStatus(str, Enum):
    """Permitted evaluation outcomes for a factual or verbatim QA check."""
    PASS = "PASS"
    FAIL = "FAIL"
    AMBIGUOUS = "AMBIGUOUS"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    UNSUPPORTED_CHECK = "UNSUPPORTED_CHECK"


class ExtractedClaim(BaseModel):
    """
    Structured claim extracted from a transcript by an LLM.
    
    Attributes:
        field: Name of the factual field (e.g. 'promotional_price_aud').
        value: Extracted structured value (numeric, string, bool, etc.).
        utterance_id: ID of the supporting utterance in the canonical transcript (e.g. 'utt_008').
        confidence: LLM extraction confidence between 0.0 and 1.0.
        raw_value: Verbatim text fragment representing the claim before normalization.
        normalized_value: Optionally normalized value.
        unit: Optional unit of measurement (e.g. 'AUD/month', 'Mbps').
        extraction_notes: Optional notes or context regarding extraction ambiguity.
    """
    # extra="ignore" guarantees that any injected keys like 'status', 'critical', 'timestamp'
    # from rogue or misbehaving LLM outputs are stripped and discarded.
    model_config = ConfigDict(frozen=True, extra="ignore")

    field: str = Field(..., min_length=1, description="Target factual field name")
    value: Any = Field(default=None, description="Extracted claim value")
    utterance_id: Optional[str] = Field(default=None, description="Referenced utterance ID")
    confidence: float = Field(default=0.0, ge=0.0, le=1.0, description="Extraction confidence score")
    raw_value: Optional[str] = Field(default=None, description="Verbatim raw text representation")
    normalized_value: Optional[Any] = Field(default=None, description="Normalized representation")
    unit: Optional[str] = Field(default=None, description="Measurement unit if applicable")
    extraction_notes: Optional[str] = Field(default=None, description="Extraction notes or reasoning")


class CheckResult(BaseModel):
    """
    Final deterministic result of a factual check evaluation.
    
    All critical metadata (critical, check_version, evidence) is guaranteed to originate
    from the CheckDefinition, ground truth, and EvidenceIndex — NEVER from the LLM.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    check_id: str = Field(..., description="Unique check identifier")
    check_type: CheckType = Field(..., description="Check type (e.g. FACTUAL)")
    critical: bool = Field(..., description="Criticality inherited from CheckDefinition")
    status: CheckStatus = Field(..., description="Final deterministic evaluation status")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Preserved extraction confidence")
    expected: Any = Field(..., description="Ground-truth expected value")
    observed: Any = Field(default=None, description="Observed value extracted from transcript")
    evidence: Optional[EvidenceReference] = Field(default=None, description="Verified backend evidence slice")
    reason: str = Field(..., min_length=1, description="Deterministic explanation of outcome")
    check_version: str = Field(..., description="Version of check from CheckDefinition")
    field: Optional[str] = Field(default=None, description="Target field evaluated")
    utterance_id: Optional[str] = Field(default=None, description="Referenced utterance ID")
    preceding_utterance_id: Optional[str] = Field(default=None, description="Preceding utterance ID for interval/gap checks")
    following_utterance_id: Optional[str] = Field(default=None, description="Following utterance ID for interval/gap checks")
    duration: Optional[float] = Field(default=None, description="Duration of gap or interval in seconds")

