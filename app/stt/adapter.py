"""
Deepgram Response to Canonical Transcript Adapter.

Transforms raw Deepgram prerecorded transcription JSON payloads into
Aurethis CanonicalTranscript instances with speaker diarization, deterministic utterance IDs,
and word-level timestamps.
"""

from typing import Any, Dict, List, Optional, Union

from app.models import CanonicalTranscript, Utterance, WordTiming
from app.stt.exceptions import DeepgramError


class DeepgramAdapter:
    """
    Transforms Deepgram JSON API responses into validated CanonicalTranscript models.
    """

    def __init__(self, id_prefix: str = "utt_", id_padding: int = 3):
        self.id_prefix = id_prefix
        self.id_padding = id_padding

    def to_canonical_transcript(
        self,
        deepgram_response: Dict[str, Any],
        transcript_id: Optional[str] = None,
        speaker_0_role: str = "AGENT",
        speaker_1_role: str = "CUSTOMER",
        speaker_role_map: Optional[Dict[Union[int, str], str]] = None,
    ) -> CanonicalTranscript:
        """
        Convert Deepgram prerecorded JSON response to CanonicalTranscript.

        Args:
            deepgram_response: Parsed JSON response from Deepgram API.
            transcript_id: Optional transcript / call identifier.
            speaker_0_role: Role to assign to Deepgram speaker 0 (default: 'AGENT').
            speaker_1_role: Role to assign to Deepgram speaker 1 (default: 'CUSTOMER').
            speaker_role_map: Optional complete custom mapping dictionary.

        Returns:
            Validated CanonicalTranscript instance.

        Raises:
            DeepgramError: If response payload format is invalid or cannot be converted.
        """
        if not isinstance(deepgram_response, dict):
            raise DeepgramError(
                f"Invalid Deepgram response: expected dict, got {type(deepgram_response).__name__}"
            )

        # Build speaker role lookup
        role_map: Dict[Union[int, str], str] = {}
        if speaker_role_map:
            for k, v in speaker_role_map.items():
                role_map[k] = str(v).strip().upper()
                # Also index as both int and str if numeric
                try:
                    role_map[int(k)] = str(v).strip().upper()
                    role_map[str(k)] = str(v).strip().upper()
                except (ValueError, TypeError):
                    pass
        else:
            role_map[0] = speaker_0_role.strip().upper()
            role_map["0"] = speaker_0_role.strip().upper()
            role_map[1] = speaker_1_role.strip().upper()
            role_map["1"] = speaker_1_role.strip().upper()

        results = deepgram_response.get("results")
        if not results or not isinstance(results, dict):
            # Check if utterances are at top level
            results = deepgram_response

        raw_utterances = results.get("utterances")

        canonical_utterances: List[Utterance] = []

        if raw_utterances and isinstance(raw_utterances, list):
            # Sort utterances chronologically by start timestamp
            sorted_utterances = sorted(
                raw_utterances,
                key=lambda u: float(u.get("start", 0.0)) if isinstance(u, dict) else 0.0,
            )

            for index, u in enumerate(sorted_utterances, start=1):
                if not isinstance(u, dict):
                    continue

                utterance = self._convert_single_utterance(u, index, role_map)
                if utterance:
                    canonical_utterances.append(utterance)

        elif "channels" in results and isinstance(results["channels"], list) and results["channels"]:
            # Fallback: Group words by speaker from channel alternatives
            canonical_utterances = self._group_words_into_utterances(
                results["channels"][0],
                role_map,
            )

        return CanonicalTranscript(
            transcript_id=transcript_id,
            utterances=canonical_utterances,
        )

    def _convert_single_utterance(
        self,
        u_dict: Dict[str, Any],
        index: int,
        role_map: Dict[Union[int, str], str],
    ) -> Optional[Utterance]:
        start_time_raw = u_dict.get("start", 0.0)
        end_time_raw = u_dict.get("end", start_time_raw)
        transcript_text = u_dict.get("transcript", "") or ""

        try:
            start_time = max(0.0, float(start_time_raw))
            end_time = max(start_time, float(end_time_raw))
        except (ValueError, TypeError) as exc:
            raise DeepgramError(f"Invalid timestamp in Deepgram utterance index {index}: {exc}") from exc

        speaker_raw = u_dict.get("speaker", 0)
        speaker = self._resolve_speaker_role(speaker_raw, role_map)

        # Word-level timestamps
        raw_words = u_dict.get("words", [])
        words: List[WordTiming] = []
        if isinstance(raw_words, list):
            for w in raw_words:
                if not isinstance(w, dict):
                    continue
                w_text = w.get("punctuated_word") or w.get("word") or ""
                w_start_raw = w.get("start", start_time)
                w_end_raw = w.get("end", w_start_raw)
                w_conf = w.get("confidence")

                try:
                    w_start = max(0.0, float(w_start_raw))
                    w_end = max(w_start, float(w_end_raw))
                    confidence = float(w_conf) if w_conf is not None else None
                    words.append(
                        WordTiming(
                            word=str(w_text),
                            start_time=w_start,
                            end_time=w_end,
                            confidence=confidence,
                        )
                    )
                except Exception:
                    continue

        utterance_id = f"{self.id_prefix}{index:0{self.id_padding}d}"

        # Clean text
        text = str(transcript_text).strip()
        if not text and words:
            text = " ".join(w.word for w in words).strip()
        if not text:
            text = "..."

        return Utterance(
            utterance_id=utterance_id,
            speaker=speaker,
            start_time=start_time,
            end_time=end_time,
            text=text,
            words=words if words else None,
        )

    def _group_words_into_utterances(
        self,
        channel_data: Dict[str, Any],
        role_map: Dict[Union[int, str], str],
    ) -> List[Utterance]:
        alternatives = channel_data.get("alternatives", [])
        if not alternatives or not isinstance(alternatives, list):
            return []

        words_data = alternatives[0].get("words", [])
        if not words_data or not isinstance(words_data, list):
            # Check for plain transcript
            transcript = alternatives[0].get("transcript", "").strip()
            if transcript:
                speaker = self._resolve_speaker_role(0, role_map)
                return [
                    Utterance(
                        utterance_id=f"{self.id_prefix}001",
                        speaker=speaker,
                        start_time=0.0,
                        end_time=1.0,
                        text=transcript,
                    )
                ]
            return []

        # Group consecutive words by speaker
        utterances: List[Utterance] = []
        current_words: List[Dict[str, Any]] = []
        current_speaker: Optional[Any] = None

        for w in words_data:
            if not isinstance(w, dict):
                continue
            spk = w.get("speaker", 0)
            if current_speaker is None:
                current_speaker = spk
                current_words.append(w)
            elif spk == current_speaker:
                current_words.append(w)
            else:
                # Flush current group
                u = self._build_utterance_from_word_group(
                    current_words,
                    len(utterances) + 1,
                    current_speaker,
                    role_map,
                )
                if u:
                    utterances.append(u)
                current_speaker = spk
                current_words = [w]

        if current_words:
            u = self._build_utterance_from_word_group(
                current_words,
                len(utterances) + 1,
                current_speaker,
                role_map,
            )
            if u:
                utterances.append(u)

        return utterances

    def _build_utterance_from_word_group(
        self,
        word_dicts: List[Dict[str, Any]],
        index: int,
        speaker_raw: Any,
        role_map: Dict[Union[int, str], str],
    ) -> Optional[Utterance]:
        if not word_dicts:
            return None

        words: List[WordTiming] = []
        text_parts: List[str] = []

        start_time = float(word_dicts[0].get("start", 0.0))
        end_time = float(word_dicts[-1].get("end", start_time))

        for w in word_dicts:
            w_text = w.get("punctuated_word") or w.get("word") or ""
            text_parts.append(str(w_text))
            w_start = float(w.get("start", start_time))
            w_end = float(w.get("end", w_start))
            w_conf = w.get("confidence")
            words.append(
                WordTiming(
                    word=str(w_text),
                    start_time=w_start,
                    end_time=max(w_start, w_end),
                    confidence=float(w_conf) if w_conf is not None else None,
                )
            )

        speaker = self._resolve_speaker_role(speaker_raw, role_map)
        utterance_id = f"{self.id_prefix}{index:0{self.id_padding}d}"

        return Utterance(
            utterance_id=utterance_id,
            speaker=speaker,
            start_time=start_time,
            end_time=max(start_time, end_time),
            text=" ".join(text_parts).strip(),
            words=words if words else None,
        )

    def _resolve_speaker_role(
        self,
        speaker_raw: Any,
        role_map: Dict[Union[int, str], str],
    ) -> str:
        if speaker_raw in role_map:
            return role_map[speaker_raw]
        try:
            spk_int = int(speaker_raw)
            if spk_int in role_map:
                return role_map[spk_int]
        except (ValueError, TypeError):
            pass
        return f"SPEAKER_{speaker_raw}".upper()


__all__ = ["DeepgramAdapter"]
