"""
Verbatim Engine Data Models.

CRITICAL ARCHITECTURAL INVARIANTS:
- CheckResult contract is shared and identical to Factual QA Gate standards.
- Criticality and check_version are strictly inherited from CheckDefinition.
- Evidence references are strictly grounded in EvidenceIndex.
- The LLM is NEVER the final authority.
"""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, ConfigDict, Field

from app.factual.models import CheckResult, CheckStatus


class MatchType(str, Enum):
    """Classification of how verbatim wording was matched."""
    EXACT = "EXACT"
    ALLOWED_VARIATION = "ALLOWED_VARIATION"
    SEMANTIC = "SEMANTIC"
    NONE = "NONE"


class VerbatimMatchResult(BaseModel):
    """
    Internal structured result of verbatim matching prior to evidence index resolution.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    matched: bool = Field(..., description="Whether required wording was detected")
    match_type: MatchType = Field(default=MatchType.NONE, description="Classification of match")
    utterance_id: Optional[str] = Field(default=None, description="Utterance ID where wording was found")
    confidence: float = Field(default=1.0, ge=0.0, le=1.0, description="Match confidence score")
    observed_text: Optional[str] = Field(default=None, description="Exact text spoken by the candidate speaker")
    matched_phrase: Optional[str] = Field(default=None, description="The approved text or variation matched")
    reason: str = Field(..., description="Deterministic explanation of match evaluation")


__all__ = [
    "CheckResult",
    "CheckStatus",
    "MatchType",
    "VerbatimMatchResult",
]
