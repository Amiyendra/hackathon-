"""
Evidence Index module.

Provides deterministic, indexed retrieval of verified transcript evidence
by utterance ID and timestamp intervals.
"""

from typing import Dict, List, Optional
from app.models import CanonicalTranscript, EvidenceReference, Utterance


class EvidenceIndex:
    """
    EvidenceIndex constructed from a verified CanonicalTranscript.
    
    Guarantees:
    - Every retrieved evidence item traces directly back to a verified Canonical Utterance.
    - No generated, fabricated, or ungrounded free text is ever returned as evidence.
    """

    def __init__(self, transcript: CanonicalTranscript):
        self._transcript = transcript
        self._by_id: Dict[str, Utterance] = {}
        self._utterances: List[Utterance] = list(transcript.utterances)

        for utterance in self._utterances:
            if utterance.utterance_id in self._by_id:
                raise ValueError(f"Duplicate utterance_id found in transcript: {utterance.utterance_id}")
            self._by_id[utterance.utterance_id] = utterance

    @property
    def transcript(self) -> CanonicalTranscript:
        """The underlying canonical transcript."""
        return self._transcript

    def get_utterance(self, utterance_id: str) -> Optional[Utterance]:
        """
        Lookup a canonical Utterance by its deterministic ID.
        
        Args:
            utterance_id: ID of the utterance (e.g. 'utt_001').
            
        Returns:
            Utterance if found, None otherwise.
        """
        return self._by_id.get(utterance_id)

    def get_evidence(self, utterance_id: str) -> Optional[EvidenceReference]:
        """
        Lookup an EvidenceReference by utterance ID.
        
        Args:
            utterance_id: ID of the utterance.
            
        Returns:
            EvidenceReference if found, None otherwise.
        """
        utt = self.get_utterance(utterance_id)
        if utt is None:
            return None
        return EvidenceReference.from_utterance(utt)

    def find_by_time(
        self,
        start_time: float,
        end_time: float,
        enclosed_only: bool = False
    ) -> List[EvidenceReference]:
        """
        Find evidence references matching a timestamp range.
        
        Args:
            start_time: Start of query time window in seconds.
            end_time: End of query time window in seconds.
            enclosed_only: If True, only utterances strictly contained within [start_time, end_time]
                          are returned. If False (default), all overlapping utterances are returned.
                          
        Returns:
            List of EvidenceReference objects ordered chronologically.
        """
        if end_time < start_time:
            raise ValueError(f"end_time ({end_time}) cannot be earlier than start_time ({start_time})")

        matches: List[EvidenceReference] = []
        for utt in self._utterances:
            if enclosed_only:
                # Fully within [start_time, end_time]
                if utt.start_time >= start_time and utt.end_time <= end_time:
                    matches.append(EvidenceReference.from_utterance(utt))
            else:
                # Overlaps [start_time, end_time]
                if utt.start_time <= end_time and utt.end_time >= start_time:
                    matches.append(EvidenceReference.from_utterance(utt))

        return matches

    def find_by_speaker(self, speaker: str) -> List[EvidenceReference]:
        """Find all evidence references belonging to a specific speaker."""
        target_speaker = speaker.strip().upper()
        return [
            EvidenceReference.from_utterance(u)
            for u in self._utterances
            if u.speaker.upper() == target_speaker
        ]

    def __len__(self) -> int:
        return len(self._utterances)

    def __iter__(self):
        return iter(self._utterances)
