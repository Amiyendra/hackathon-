"""
Deterministic QA Gate Models.

CRITICAL ARCHITECTURAL INVARIANTS:
1. Python is the sole authority for routing. The LLM never decides AUTO_SUBMIT, HOLD, or QA_REVIEW.
2. Behaviour checks are strictly non-blocking and can never cause HOLD.
3. Every individual CheckResult is preserved for auditability.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.factual.models import CheckResult, CheckStatus


class GateDecision(str, Enum):
    """Permitted final routing decisions for a call evaluation."""
    AUTO_SUBMIT = "AUTO_SUBMIT"
    HOLD = "HOLD"
    QA_REVIEW = "QA_REVIEW"


class GateResult(BaseModel):
    """
    Final deterministic evaluation summary and routing disposition.
    
    Contains all metrics, blocking IDs, review IDs, reasons, and the complete
    collection of underlying CheckResult objects.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    lead_id: Optional[str] = Field(default=None, description="Transcript or lead identifier")
    retailer: Optional[str] = Field(default=None, description="Retailer or provider identifier")
    call_date: Optional[str] = Field(default=None, description="Call date evaluated (YYYY-MM-DD)")
    decision: GateDecision = Field(..., description="Final deterministic gate decision")
    critical_checks_total: int = Field(..., ge=0, description="Total critical checks evaluated")
    critical_checks_passed: int = Field(..., ge=0, description="Total critical checks that passed")
    critical_checks_failed: int = Field(..., ge=0, description="Total critical checks that failed")
    critical_checks_ambiguous: int = Field(..., ge=0, description="Total critical checks requiring review")
    non_critical_failures: int = Field(..., ge=0, description="Total non-critical checks that failed")
    blocking_check_ids: List[str] = Field(default_factory=list, description="IDs of critical checks causing HOLD")
    review_check_ids: List[str] = Field(default_factory=list, description="IDs of critical checks causing QA_REVIEW")
    reasons: List[str] = Field(..., description="Traceable explanations justifying the gate decision")
    check_results: List[CheckResult] = Field(..., description="Complete collection of individual CheckResult records")

    @property
    def all_check_results(self) -> List[CheckResult]:
        """Convenience property alias for check_results."""
        return self.check_results

    @computed_field
    @property
    def gate_explanation(self) -> str:
        """Consolidated string explanation of gate disposition and reasoning."""
        return "\n".join(self.reasons)



__all__ = [
    "GateDecision",
    "GateResult",
    "CheckResult",
    "CheckStatus",
]
