"""
Factual Match Engine package.

Exposes core models, exceptions, comparator, extractor, LLM client, and engine.
"""

from app.factual.anthropic_client import AnthropicClient
from app.factual.comparator import DeterministicComparator
from app.factual.engine import FactualEngine
from app.factual.exceptions import (
    ComparisonError,
    ExtractionError,
    FactualEngineError,
    InvalidEvidenceError,
    MissingExpectedValueError,
)
from app.factual.extractor import ClaimExtractor
from app.factual.llm import (
    BaseLLMClient,
    MockLLMClient,
    get_llm_client,
)
from app.factual.models import CheckResult, CheckStatus, ExtractedClaim

__all__ = [
    "CheckResult",
    "CheckStatus",
    "ExtractedClaim",
    "FactualEngine",
    "ClaimExtractor",
    "DeterministicComparator",
    "BaseLLMClient",
    "MockLLMClient",
    "AnthropicClient",
    "get_llm_client",
    "FactualEngineError",
    "ExtractionError",
    "ComparisonError",
    "InvalidEvidenceError",
    "MissingExpectedValueError",
]
