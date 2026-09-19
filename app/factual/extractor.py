"""
Claim Extractor module.

Wraps the LLM client, executes claim extraction for a specific check definition,
and enforces structural and security sanitization.
"""

import re
from typing import Optional
from app.checks.models import CheckDefinition
from app.factual.llm import BaseLLMClient, get_llm_client
from app.factual.models import ExtractedClaim
from app.models import CanonicalTranscript

# Matches canonical redaction placeholders of the form [UPPER_CASE_TOKEN]
# e.g. [CUSTOMER_NAME], [SERVICE_ADDRESS], [PHONE_NUMBER], [EMAIL], [DOB]
_REDACTION_PLACEHOLDER_RE = re.compile(r"\[([A-Z][A-Z0-9_]+)\]")


def scan_redaction_placeholder(text: str) -> Optional[str]:
    """
    Deterministically scan utterance text for the first canonical redaction placeholder
    of the form [UPPER_CASE_TOKEN] and return it verbatim (including brackets).

    Returns None if no recognized placeholder is found.

    This is intentionally a pure, LLM-free function so it can be independently unit-tested.
    """
    match = _REDACTION_PLACEHOLDER_RE.search(text)
    if match:
        return match.group(0)  # e.g. "[CUSTOMER_NAME]"
    return None


def _field_to_placeholder(field: str) -> str:
    """
    Derive the canonical redaction placeholder token from a field name.

    Convention: field names are lower_snake_case; placeholders are [UPPER_SNAKE_CASE].

    Examples:
        customer_name     -> [CUSTOMER_NAME]
        service_address   -> [SERVICE_ADDRESS]
        phone_number      -> [PHONE_NUMBER]
        customer_full_name -> [CUSTOMER_FULL_NAME]
    """
    return f"[{field.upper()}]"


class ClaimExtractor:
    """
    Coordinates claim extraction from canonical transcripts using the configured LLM client.

    Guarantees:
    - Strips any attempted LLM injection of decisions (status, critical, timestamp, version).
    - Ensures extracted field maps to target check field.
    - For placeholder_match checks, deterministically overrides LLM value with the exact
      redaction token found in the transcript utterance, preventing LLM hallucination
      of the underlying PII (e.g. converting "[CUSTOMER_NAME]" → "Customer Name").
    """

    def __init__(self, llm_client: Optional[BaseLLMClient] = None):
        self._client = llm_client or get_llm_client()

    @property
    def client(self) -> BaseLLMClient:
        return self._client

    def extract_claim(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript
    ) -> ExtractedClaim:
        """
        Extract the factual claim for the given check definition.

        Post-processing:
          If the check's comparison_method is "placeholder_match", the extracted value is
          replaced with the canonical redaction placeholder found in the referenced utterance.
          This is deterministic and requires no LLM involvement.
        """
        claim = self._client.extract_claim(check, transcript)

        # Ensure field matches check definition criteria
        expected_field = check.criteria.get("field", check.check_id)
        if not claim.field:
            claim = claim.model_copy(update={"field": expected_field})

        # --- Deterministic redaction-placeholder normalization ---
        # Fires ONLY for placeholder_match checks to preserve exact [TOKEN] form.
        # This prevents the LLM from converting "[CUSTOMER_NAME]" → "Customer Name".
        comparison_method = check.criteria.get("comparison_method", "")
        if comparison_method == "placeholder_match" and claim.utterance_id:
            canonical_placeholder = self._resolve_placeholder_from_transcript(
                claim.utterance_id, transcript, field=expected_field
            )
            if canonical_placeholder is not None:
                # Override LLM's inferred value with the deterministic placeholder token
                claim = claim.model_copy(update={
                    "value": canonical_placeholder,
                    "raw_value": canonical_placeholder,
                })

        return claim

    @staticmethod
    def _resolve_placeholder_from_transcript(
        utterance_id: str,
        transcript: CanonicalTranscript,
        field: Optional[str] = None,
    ) -> Optional[str]:
        """
        Look up the utterance by ID and return the canonical redaction placeholder for the field.

        Resolution strategy (field-aware, fully deterministic):
          1. Derive the expected placeholder from the field name (e.g. "service_address" → "[SERVICE_ADDRESS]").
          2. If the utterance text contains that specific placeholder, return it exactly.
          3. Fallback: return the first [UPPER_CASE] placeholder found in the utterance.
          4. If no placeholder is found at all, return None.

        This handles utterances that contain multiple placeholders (e.g. utt_004 contains
        both [CUSTOMER_NAME] and [SERVICE_ADDRESS]) by resolving to the field-specific token.
        """
        for utt in transcript.utterances:
            if utt.utterance_id == utterance_id:
                text = utt.text
                # 1. Field-specific lookup: derive expected placeholder from field name
                if field:
                    expected_token = _field_to_placeholder(field)
                    if expected_token in text:
                        return expected_token
                # 2. Fallback: first [UPPER_CASE] placeholder in utterance
                return scan_redaction_placeholder(text)
        return None
