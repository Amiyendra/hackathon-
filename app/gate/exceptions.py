"""
Deterministic QA Gate Exceptions.
"""


class GateError(Exception):
    """Base exception for QA Gate errors."""
    pass


class EmptyGateEvaluationError(GateError):
    """Raised when gate evaluation is attempted with an empty list of check results."""
    pass


class InvalidGateInputError(GateError):
    """Raised when invalid check result objects are supplied to the gate."""
    pass
