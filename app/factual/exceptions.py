"""Exceptions for the Factual Match Engine."""


class FactualEngineError(Exception):
    """Base exception for all factual engine errors."""
    pass


class ExtractionError(FactualEngineError):
    """Raised when claim extraction fails structurally or critically."""
    pass


class ComparisonError(FactualEngineError):
    """Raised when deterministic comparison fails unexpectedly."""
    pass


class InvalidEvidenceError(FactualEngineError):
    """Raised when evidence reference fails validation against EvidenceIndex."""
    pass


class MissingExpectedValueError(FactualEngineError):
    """Raised when expected ground-truth value is missing or undefined."""
    pass
