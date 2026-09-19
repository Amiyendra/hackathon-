"""
Verbatim / Script QA Engine Package.

Exposes models, matcher, engine, and exceptions for deterministic and
evidence-backed script evaluation.
"""

from app.verbatim.engine import VerbatimEngine
from app.verbatim.exceptions import (
    InvalidCheckTypeError,
    InvalidEvidenceError,
    MatchingError,
    MissingApprovedTextError,
    VerbatimEngineError,
)
from app.verbatim.matcher import VerbatimMatcher
from app.verbatim.models import (
    CheckResult,
    CheckStatus,
    MatchType,
    VerbatimMatchResult,
)

__all__ = [
    "VerbatimEngine",
    "VerbatimMatcher",
    "VerbatimMatchResult",
    "MatchType",
    "CheckResult",
    "CheckStatus",
    "VerbatimEngineError",
    "InvalidCheckTypeError",
    "MissingApprovedTextError",
    "InvalidEvidenceError",
    "MatchingError",
]
