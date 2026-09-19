"""
Deterministic Text Matcher for Verbatim QA Checks.

Executes case, whitespace, and punctuation normalization to evaluate exact phrase
adherence and configured allowed variations without LLM dependencies.
"""

import re
import string
from typing import List, Optional, Tuple

from app.models import CanonicalTranscript, Utterance
from app.verbatim.models import MatchType, VerbatimMatchResult


class VerbatimMatcher:
    """
    Deterministic textual matcher for verbatim scripts and statutory disclosures.
    """

    @staticmethod
    def normalize_text(text: str) -> str:
        """
        Normalize text by lowercasing, removing harmless punctuation,
        and collapsing consecutive whitespace.
        
        Args:
            text: Raw input string.
            
        Returns:
            Normalized clean string.
        """
        if not text:
            return ""

        # Lowercase
        normalized = text.lower()

        # Replace dashes/hyphens and slashes with space so "wi-fi" matches "wi fi" if spaced
        normalized = re.sub(r"[-_/]", " ", normalized)

        # Remove punctuation
        translator = str.maketrans("", "", string.punctuation)
        normalized = normalized.translate(translator)

        # Collapse whitespace
        normalized = " ".join(normalized.split())
        return normalized.strip()

    @classmethod
    def phrase_in_text(cls, phrase: str, text: str) -> bool:
        """
        Check if normalized phrase exists inside normalized text as an exact sequence of words.
        """
        norm_phrase = cls.normalize_text(phrase)
        norm_text = cls.normalize_text(text)
        if not norm_phrase or not norm_text:
            return False

        # Exact substring match on normalized word boundaries
        # Ensure whole word boundaries around the phrase match
        pattern = r"\b" + re.escape(norm_phrase) + r"\b"
        return bool(re.search(pattern, norm_text))

    @classmethod
    def find_deterministic_match(
        cls,
        approved_text: str,
        allowed_variations: Optional[List[str]],
        transcript: CanonicalTranscript,
        speaker_constraint: Optional[str] = "AGENT",
    ) -> VerbatimMatchResult:
        """
        Scan transcript utterances in chronological order for exact approved text
        or configured allowed variations.
        
        Args:
            approved_text: Primary mandatory approved wording.
            allowed_variations: List of explicitly approved textual variations.
            transcript: The canonical transcript to scan.
            speaker_constraint: Optional speaker filter (e.g. 'AGENT', 'CUSTOMER', or None for any).
            
        Returns:
            VerbatimMatchResult with match details.
        """
        target_speaker = speaker_constraint.upper().strip() if speaker_constraint else None
        variations = allowed_variations or []

        # 1. First pass: scan for exact approved text
        for utt in transcript.utterances:
            if target_speaker and utt.speaker.upper() != target_speaker:
                continue

            if cls.phrase_in_text(approved_text, utt.text):
                return VerbatimMatchResult(
                    matched=True,
                    match_type=MatchType.EXACT,
                    utterance_id=utt.utterance_id,
                    confidence=1.0,
                    observed_text=utt.text,
                    matched_phrase=approved_text,
                    reason=f"Approved wording found in utterance {utt.utterance_id} via normalized exact match."
                )

        # 2. Second pass: scan for configured allowed variations
        for variation in variations:
            if not variation:
                continue
            for utt in transcript.utterances:
                if target_speaker and utt.speaker.upper() != target_speaker:
                    continue

                if cls.phrase_in_text(variation, utt.text):
                    return VerbatimMatchResult(
                        matched=True,
                        match_type=MatchType.ALLOWED_VARIATION,
                        utterance_id=utt.utterance_id,
                        confidence=1.0,
                        observed_text=utt.text,
                        matched_phrase=variation,
                        reason=(
                            f"Configured allowed variation '{variation}' found in "
                            f"utterance {utt.utterance_id}."
                        )
                    )

        # 3. No deterministic match found
        return VerbatimMatchResult(
            matched=False,
            match_type=MatchType.NONE,
            utterance_id=None,
            confidence=0.0,
            observed_text=None,
            matched_phrase=None,
            reason="Required wording was not spoken in the transcript."
        )
