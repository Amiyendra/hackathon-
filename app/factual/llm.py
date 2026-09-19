"""
LLM Client Abstraction for Factual Claim Extraction.

Provides a unified interface with:
- MockLLMClient (used for automated testing and offline deterministic runs)
- AnthropicClient (production integration with Anthropic Claude direct API)

SECURITY & ARCHITECTURAL INVARIANTS:
- The LLM is used EXCLUSIVELY for claim extraction, never for scoring, gating, or deciding PASS/FAIL.
- All transcript text is treated as passive UNTRUSTED DATA.
- No secrets or credentials are hardcoded.
"""

from abc import ABC, abstractmethod
import json
import os
from typing import Any, Dict, Optional
from app.checks.models import CheckDefinition
from app.factual.models import ExtractedClaim
from app.models import CanonicalTranscript


class BaseLLMClient(ABC):
    """Abstract interface for LLM claim extraction clients."""

    @abstractmethod
    def extract_claim(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript
    ) -> ExtractedClaim:
        """
        Extract the agent's factual claim for a specific check from the canonical transcript.
        
        Args:
            check: The resolved CheckDefinition containing the target field and criteria.
            transcript: The verified CanonicalTranscript.
            
        Returns:
            ExtractedClaim containing structured value, utterance_id, and confidence.
        """
        pass


class MockLLMClient(BaseLLMClient):
    """
    Deterministic mock client for testing.
    
    Allows test suites to pre-register expected extractions or fall back
    to deterministic rule-based extractions without making any external API calls.
    """

    def __init__(self, canned_claims: Optional[Dict[str, ExtractedClaim]] = None):
        self._canned_claims: Dict[str, ExtractedClaim] = dict(canned_claims or {})
        self._raw_responses: Dict[str, str] = {}

    def register_claim(self, check_id: str, claim: ExtractedClaim) -> None:
        """Register a canned claim for a specific check ID."""
        self._canned_claims[check_id] = claim

    def register_raw_response(self, check_id: str, raw_json: str) -> None:
        """Register a raw JSON string to simulate LLM response formatting."""
        self._raw_responses[check_id] = raw_json

    def extract_claim(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript
    ) -> ExtractedClaim:
        # 1. Check if raw JSON response was registered (to test JSON parsing & error handling)
        if check.check_id in self._raw_responses:
            raw = self._raw_responses[check.check_id]
            try:
                data = json.loads(raw)
                return ExtractedClaim.model_validate(data)
            except Exception as e:
                return ExtractedClaim(
                    field=check.criteria.get("field", check.check_id),
                    value=None,
                    utterance_id=None,
                    confidence=0.0,
                    extraction_notes=f"Malformed LLM JSON: {e}"
                )

        # 2. Check if a pre-configured ExtractedClaim exists
        if check.check_id in self._canned_claims:
            return self._canned_claims[check.check_id]

        target_field = check.criteria.get("field", check.check_id)
        if target_field in self._canned_claims:
            return self._canned_claims[target_field]

        # 3. Default fallback: search transcript text for known field indicators
        return self._heuristic_fallback_extract(check, transcript)

    def _heuristic_fallback_extract(
        self,
        check: CheckDefinition,
        transcript: CanonicalTranscript
    ) -> ExtractedClaim:
        """
        Lightweight heuristic fallback for synthetic broadband transcript fixtures.
        Allows tests to run end-to-end without manually populating every single check fixture.
        """
        field = check.criteria.get("field", check.check_id)

        # Map fields to transcript utterances in data/broadband_transcript.json
        for utt in transcript.utterances:
            text = utt.text.lower()
            if field == "promotional_price_aud" and "$42.90" in utt.text:
                return ExtractedClaim(
                    field=field,
                    value=42.90,
                    raw_value="$42.90",
                    unit="AUD/month",
                    utterance_id=utt.utterance_id,
                    confidence=0.98
                )
            if field == "regular_price_aud" and "$72.90" in utt.text:
                return ExtractedClaim(
                    field=field,
                    value=72.90,
                    raw_value="$72.90",
                    unit="AUD/month",
                    utterance_id=utt.utterance_id,
                    confidence=0.98
                )
            if field == "promotional_period_months" and "first 6 months" in text:
                return ExtractedClaim(
                    field=field,
                    value=6,
                    raw_value="first 6 months",
                    unit="months",
                    utterance_id=utt.utterance_id,
                    confidence=0.96
                )
            if field == "download_speed_mbps" and "25 mbps" in text:
                return ExtractedClaim(
                    field=field,
                    value=25.0,
                    raw_value="25 Mbps",
                    unit="Mbps",
                    utterance_id=utt.utterance_id,
                    confidence=0.97
                )
            if field == "upload_speed_mbps" and "8.5 mbps" in text:
                return ExtractedClaim(
                    field=field,
                    value=8.5,
                    raw_value="8.5 Mbps",
                    unit="Mbps",
                    utterance_id=utt.utterance_id,
                    confidence=0.97
                )
            if field == "modem_model" and "netcom cf40" in text:
                return ExtractedClaim(
                    field=field,
                    value="Netcom CF40 Wi-Fi 6",
                    raw_value="Netcom CF40 Wi-Fi 6 modem",
                    utterance_id=utt.utterance_id,
                    confidence=0.95
                )
            if field == "modem_hardware_cost_aud" and "modem cost is $0" in text:
                return ExtractedClaim(
                    field=field,
                    value=0.00,
                    raw_value="$0, completely free",
                    unit="AUD",
                    utterance_id=utt.utterance_id,
                    confidence=0.98
                )
            if field == "modem_delivery_timeline" and "3 to 5 business days" in text:
                return ExtractedClaim(
                    field=field,
                    value="3-5 business days",
                    raw_value="between 3 to 5 business days",
                    utterance_id=utt.utterance_id,
                    confidence=0.92
                )
            if field == "connection_timing" and "as soon as possible" in text:
                return ExtractedClaim(
                    field=field,
                    value="as soon as possible",
                    raw_value="as soon as possible",
                    utterance_id=utt.utterance_id,
                    confidence=0.90
                )
            if field == "minimum_total_cost_aud" and "$317" in utt.text:
                return ExtractedClaim(
                    field=field,
                    value=317.00,
                    raw_value="$317",
                    unit="AUD",
                    utterance_id=utt.utterance_id,
                    confidence=0.98
                )
            if field == "current_provider" and "iprimus" in text:
                return ExtractedClaim(
                    field=field,
                    value="iPRIMUS",
                    raw_value="iPRIMUS",
                    utterance_id=utt.utterance_id,
                    confidence=0.95
                )
            if field == "customer_name" and "[customer_name]" in text:
                return ExtractedClaim(
                    field=field,
                    value="[CUSTOMER_NAME]",
                    raw_value="[CUSTOMER_NAME]",
                    utterance_id=utt.utterance_id,
                    confidence=0.99
                )
            if field == "service_address" and "[service_address]" in text:
                return ExtractedClaim(
                    field=field,
                    value="[SERVICE_ADDRESS]",
                    raw_value="[SERVICE_ADDRESS]",
                    utterance_id=utt.utterance_id,
                    confidence=0.99
                )
            if field == "nbn_technology_type" and "fttp" in text:
                return ExtractedClaim(
                    field=field,
                    value="FTTP",
                    raw_value="FTTP",
                    utterance_id=utt.utterance_id,
                    confidence=0.95
                )
            # Fail case fixtures
            if field == "modem_delivery_fee_aud" and "completely free" in text:
                return ExtractedClaim(
                    field=field,
                    value=0.00,
                    raw_value="$0 free",
                    unit="AUD",
                    utterance_id=utt.utterance_id,
                    confidence=0.95
                )
            if field == "plan_contract_term_months" and "first 6 months" in text:
                return ExtractedClaim(
                    field=field,
                    value=1,  # month to month implied
                    raw_value="month-to-month",
                    unit="months",
                    utterance_id=utt.utterance_id,
                    confidence=0.90
                )

        # Default when field is completely unmentioned (e.g. battery backup, static IP)
        return ExtractedClaim(
            field=field,
            value=None,
            utterance_id=None,
            confidence=0.0,
            extraction_notes=f"No factual claim for '{field}' detected in transcript."
        )


def get_llm_client(provider: Optional[str] = None) -> BaseLLMClient:
    """
    Factory function resolving LLM client based on configuration.
    
    Order of precedence:
    1. Explicit provider argument
    2. FACTUAL_LLM_PROVIDER environment variable ('mock' or 'anthropic')
    3. Default: 'mock' (guarantees tests and offline environments never make external calls)
    """
    selected_provider = (provider or os.environ.get("FACTUAL_LLM_PROVIDER", "mock")).lower().strip()

    if selected_provider == "anthropic":
        from app.factual.anthropic_client import AnthropicClient
        return AnthropicClient()
    elif selected_provider == "mock":
        return MockLLMClient()
    else:
        raise ValueError(
            f"Unknown FACTUAL_LLM_PROVIDER: '{selected_provider}'. Supported values: 'mock', 'anthropic'."
        )
