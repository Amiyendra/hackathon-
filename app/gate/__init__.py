"""
Deterministic QA Gate Module.

Provides deterministic routing decisions (AUTO_SUBMIT, HOLD, QA_REVIEW)
by evaluating results from Factual, Verbatim, and Behaviour QA engines.
"""

from app.gate.engine import DeterministicGate
from app.gate.exceptions import (
    EmptyGateEvaluationError,
    GateError,
    InvalidGateInputError,
)
from app.gate.models import GateDecision, GateResult

__all__ = [
    "DeterministicGate",
    "GateDecision",
    "GateResult",
    "GateError",
    "EmptyGateEvaluationError",
    "InvalidGateInputError",
]
