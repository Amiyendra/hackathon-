"""
Verbatim / Script QA Engine Exceptions.
"""


class VerbatimEngineError(Exception):
    """Base exception for all Verbatim Engine errors."""
    pass


class InvalidCheckTypeError(VerbatimEngineError):
    """Raised when a non-VERBATIM check definition is passed to the VerbatimEngine."""
    pass


class MissingApprovedTextError(VerbatimEngineError):
    """Raised when a VERBATIM check definition lacks approved_text or required_phrase."""
    pass


class InvalidEvidenceError(VerbatimEngineError):
    """Raised when evidence verification against EvidenceIndex fails."""
    pass


class MatchingError(VerbatimEngineError):
    """Raised when an internal error occurs during text or semantic matching."""
    pass
