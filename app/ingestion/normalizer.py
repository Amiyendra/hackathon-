"""
Transcript Normalizer module.

Transforms raw input transcript data into a strictly validated CanonicalTranscript.

UNTRUSTED-DATA BOUNDARY:
Input transcript data originates from external clients, third-party telephony,
or automated speech-to-text engines. All text fields are treated exclusively as
passive data. They are never interpreted, parsed as instructions, or executed.
"""

import json
from typing import Any, Dict, List, Union
from pydantic import ValidationError

from app.config import config
from app.models import CanonicalTranscript, Utterance, WordTiming


class TranscriptNormalizationError(ValueError):
    """Raised when transcript payload fails structural or validation rules."""
    pass


class TranscriptNormalizer:
    """
    Deterministic normalizer that ingests raw transcript inputs and constructs
    a validated CanonicalTranscript.
    """

    def __init__(self, id_prefix: str = config.default_id_prefix, id_padding: int = config.default_id_padding):
        self.id_prefix = id_prefix
        self.id_padding = id_padding

    def normalize(self, raw_data: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> CanonicalTranscript:
        """
        Normalize raw transcript input into CanonicalTranscript.
        
        Args:
            raw_data: JSON string, dictionary (with 'utterances' list), or list of utterance dicts.
            
        Returns:
            CanonicalTranscript instance with validated utterances and deterministic IDs.
            
        Raises:
            TranscriptNormalizationError: If input format or any utterance fails validation.
        """
        parsed_data = self._parse_input(raw_data)
        transcript_id, raw_utterances = self._extract_transcript_payload(parsed_data)

        canonical_utterances: List[Utterance] = []
        for index, item in enumerate(raw_utterances, start=1):
            utterance = self._normalize_single_utterance(item, index)
            canonical_utterances.append(utterance)

        return CanonicalTranscript(
            transcript_id=transcript_id,
            utterances=canonical_utterances
        )

    def _parse_input(self, raw_data: Union[str, Dict[str, Any], List[Dict[str, Any]]]) -> Union[Dict[str, Any], List[Dict[str, Any]]]:
        if isinstance(raw_data, str):
            try:
                parsed = json.loads(raw_data)
                return parsed
            except Exception as e:
                raise TranscriptNormalizationError(f"Failed to parse transcript JSON: {e}") from e
        elif isinstance(raw_data, (dict, list)):
            return raw_data
        else:
            raise TranscriptNormalizationError(
                f"Unsupported raw data type: {type(raw_data).__name__}. Expected str, dict, or list."
            )

    def _extract_transcript_payload(self, data: Union[Dict[str, Any], List[Dict[str, Any]]]) -> tuple[Union[str, None], List[Any]]:
        if isinstance(data, list):
            return None, data
        elif isinstance(data, dict):
            transcript_id = data.get("transcript_id") or data.get("call_id")
            if "utterances" in data:
                utterances = data["utterances"]
                if not isinstance(utterances, list):
                    raise TranscriptNormalizationError("The 'utterances' field must be a list.")
                return str(transcript_id) if transcript_id is not None else None, utterances
            else:
                raise TranscriptNormalizationError("Transcript dictionary must contain an 'utterances' key.")
        else:
            raise TranscriptNormalizationError("Payload must be a dictionary or list of utterances.")

    def _normalize_single_utterance(self, item: Any, index: int) -> Utterance:
        if not isinstance(item, dict):
            raise TranscriptNormalizationError(f"Utterance at index {index} must be a dictionary.")

        # 1. Deterministic utterance ID
        existing_id = item.get("utterance_id")
        if existing_id is not None and str(existing_id).strip():
            utterance_id = str(existing_id).strip()
        else:
            utterance_id = f"{self.id_prefix}{index:0{self.id_padding}d}"

        # 2. Speaker validation
        speaker = item.get("speaker")
        if speaker is None or not str(speaker).strip():
            raise TranscriptNormalizationError(f"Utterance {utterance_id} (index {index}) is missing speaker label.")
        speaker = str(speaker).strip()

        # 3. Text preservation (passive data)
        text = item.get("text")
        if text is None:
            raise TranscriptNormalizationError(f"Utterance {utterance_id} (index {index}) is missing text.")
        if not isinstance(text, str):
            # Convert non-string representations faithfully without modifying semantic content
            text = str(text)

        # 4. Timestamps validation
        start_time_raw = item.get("start_time")
        end_time_raw = item.get("end_time")

        if start_time_raw is None or end_time_raw is None:
            raise TranscriptNormalizationError(
                f"Utterance {utterance_id} (index {index}) must have both start_time and end_time."
            )

        # Reject bools (since bool is a subclass of int in Python)
        if isinstance(start_time_raw, bool) or isinstance(end_time_raw, bool):
            raise TranscriptNormalizationError(
                f"Utterance {utterance_id} (index {index}) timestamps cannot be boolean."
            )

        try:
            start_time = float(start_time_raw)
            end_time = float(end_time_raw)
        except (ValueError, TypeError) as e:
            raise TranscriptNormalizationError(
                f"Utterance {utterance_id} (index {index}) has invalid non-numeric timestamp: {e}"
            ) from e

        if start_time < 0.0:
            raise TranscriptNormalizationError(
                f"Utterance {utterance_id} (index {index}) start_time cannot be negative ({start_time})."
            )

        if end_time < start_time:
            raise TranscriptNormalizationError(
                f"Utterance {utterance_id} (index {index}) end_time ({end_time}) cannot be earlier than start_time ({start_time})."
            )

        # 5. Optional word-level timestamps
        words: Optional[List[WordTiming]] = None
        raw_words = item.get("words")
        if raw_words is not None:
            if not isinstance(raw_words, list):
                raise TranscriptNormalizationError(f"Utterance {utterance_id} 'words' field must be a list.")
            normalized_words: List[WordTiming] = []
            for w in raw_words:
                if not isinstance(w, dict):
                    continue
                w_word = str(w.get("word", "")).strip()
                w_start = w.get("start_time") if w.get("start_time") is not None else w.get("start")
                w_end = w.get("end_time") if w.get("end_time") is not None else w.get("end")
                w_conf = w.get("confidence")
                if w_start is not None and w_end is not None:
                    try:
                        normalized_words.append(
                            WordTiming(
                                word=w_word,
                                start_time=float(w_start),
                                end_time=float(w_end),
                                confidence=float(w_conf) if w_conf is not None else None,
                            )
                        )
                    except Exception:
                        pass
            if normalized_words:
                words = normalized_words

        try:
            return Utterance(
                utterance_id=utterance_id,
                speaker=speaker,
                start_time=start_time,
                end_time=end_time,
                text=text,
                words=words,
            )
        except ValidationError as e:
            raise TranscriptNormalizationError(
                f"Validation error for utterance {utterance_id}: {e}"
            ) from e
