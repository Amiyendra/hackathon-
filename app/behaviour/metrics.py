"""
Deterministic Timing Metrics for Behaviour QA Checks.

Computes exact silence gaps (Dead Air) and conversational collisions (Interruptions)
directly from canonical utterance timestamps in pure Python.
"""

from typing import List, Optional, Tuple

from app.behaviour.models import DeadAirIncident, InterruptionIncident
from app.models import CanonicalTranscript


class BehaviourMetrics:
    """
    Pure Python deterministic calculation of conversational timing metrics.
    """

    @classmethod
    def calculate_dead_air(
        cls,
        transcript: CanonicalTranscript,
        threshold_seconds: float,
    ) -> Tuple[List[DeadAirIncident], float, Optional[DeadAirIncident]]:
        """
        Scan consecutive utterances to identify silence gaps exceeding the threshold.
        
        Args:
            transcript: Validated CanonicalTranscript.
            threshold_seconds: Configured maximum permitted silence duration.
            
        Returns:
            Tuple of:
            - List of DeadAirIncident objects exceeding threshold
            - Maximum observed gap across the call
            - The largest DeadAirIncident object (or None if no gaps)
        """
        incidents: List[DeadAirIncident] = []
        max_gap: float = 0.0
        largest_incident: Optional[DeadAirIncident] = None

        utterances = transcript.utterances
        for i in range(len(utterances) - 1):
            prev_utt = utterances[i]
            curr_utt = utterances[i + 1]

            # Dead air occurs when the next utterance starts after the previous ends
            gap = round(curr_utt.start_time - prev_utt.end_time, 4)
            if gap > 0:
                incident = DeadAirIncident(
                    preceding_utterance_id=prev_utt.utterance_id,
                    following_utterance_id=curr_utt.utterance_id,
                    gap_seconds=gap,
                    start_time=prev_utt.end_time,
                    end_time=curr_utt.start_time,
                )
                if gap > max_gap:
                    max_gap = gap
                    largest_incident = incident

                if gap >= threshold_seconds:
                    incidents.append(incident)

        return incidents, max_gap, largest_incident

    @classmethod
    def detect_interruptions(
        cls,
        transcript: CanonicalTranscript,
    ) -> List[InterruptionIncident]:
        """
        Detect speech collisions where a speaker begins speaking before
        the previous speaker has finished.
        
        Args:
            transcript: Validated CanonicalTranscript.
            
        Returns:
            List of InterruptionIncident objects representing speech overlaps.
        """
        incidents: List[InterruptionIncident] = []
        utterances = transcript.utterances

        for i in range(len(utterances) - 1):
            prev_utt = utterances[i]
            curr_utt = utterances[i + 1]

            # Interruption requires different speakers and an overlapping timestamp
            if prev_utt.speaker.upper() != curr_utt.speaker.upper():
                if curr_utt.start_time < prev_utt.end_time:
                    overlap = round(prev_utt.end_time - curr_utt.start_time, 4)
                    incidents.append(
                        InterruptionIncident(
                            interrupter_speaker=curr_utt.speaker.upper(),
                            interrupted_speaker=prev_utt.speaker.upper(),
                            overlap_seconds=overlap,
                            utterance_id_a=prev_utt.utterance_id,
                            utterance_id_b=curr_utt.utterance_id,
                            start_time=curr_utt.start_time,
                            end_time=prev_utt.end_time,
                        )
                    )

        return incidents
