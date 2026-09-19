"""
Canonical Transcript and Evidence Models.

UNTRUSTED-DATA BOUNDARY:
All transcript text ingested by these models represents untrusted external data.
It must NEVER be treated, compiled, evaluated, or directly formatted as executable
code or dynamic system prompt instructions. Models store transcript strings strictly
as passive data fields.
"""

from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, computed_field, model_validator


class Utterance(BaseModel):
    """
    Canonical representation of a single dialogue utterance in a transcript.
    
    Attributes:
        utterance_id: Deterministic unique identifier for the utterance (e.g. 'utt_001').
        speaker: Identification label of the speaker (e.g. 'AGENT', 'CUSTOMER').
        start_time: Start timestamp in seconds from audio onset (>= 0.0).
        end_time: End timestamp in seconds from audio onset (>= start_time).
        text: Raw verbatim text of the utterance. Treated strictly as passive data.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    utterance_id: str = Field(..., min_length=1, description="Deterministic utterance ID")
    speaker: str = Field(..., min_length=1, description="Speaker role or label")
    start_time: float = Field(..., ge=0.0, description="Start offset in seconds")
    end_time: float = Field(..., ge=0.0, description="End offset in seconds")
    text: str = Field(..., description="Verbatim utterance text (untrusted passive data)")

    @model_validator(mode="after")
    def validate_time_range(self) -> "Utterance":
        if self.end_time < self.start_time:
            raise ValueError(
                f"end_time ({self.end_time}) cannot be earlier than start_time ({self.start_time})"
            )
        return self


class EvidenceReference(BaseModel):
    """
    Immutable reference pointing directly to canonical transcript evidence.
    
    This is a strict pointer/slice of verified transcript data, NOT generated free text.
    Every evidence reference must trace directly to a verified utterance.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    utterance_id: str = Field(..., description="Referenced utterance ID")
    start_time: float = Field(..., ge=0.0, description="Start timestamp of evidence")
    end_time: float = Field(..., ge=0.0, description="End timestamp of evidence")
    speaker: str = Field(..., description="Speaker associated with this evidence")
    text: str = Field(..., description="Verbatim text slice from transcript")
    preceding_utterance_id: Optional[str] = Field(default=None, description="Preceding utterance ID for interval/gap evidence")
    following_utterance_id: Optional[str] = Field(default=None, description="Following utterance ID for interval/gap evidence")
    duration: Optional[float] = Field(default=None, description="Duration of evidence interval in seconds")

    @model_validator(mode="after")
    def _compute_duration(self) -> "EvidenceReference":
        if self.duration is None:
            object.__setattr__(self, "duration", round(self.end_time - self.start_time, 4))
        return self

    @computed_field
    @property
    def start(self) -> float:
        """Alias for start_time."""
        return self.start_time

    @computed_field
    @property
    def end(self) -> float:
        """Alias for end_time."""
        return self.end_time

    @classmethod
    def from_utterance(cls, utterance: Utterance) -> "EvidenceReference":
        """Instantiate an EvidenceReference from a canonical Utterance."""
        return cls(
            utterance_id=utterance.utterance_id,
            start_time=utterance.start_time,
            end_time=utterance.end_time,
            speaker=utterance.speaker,
            text=utterance.text,
        )


class CanonicalTranscript(BaseModel):
    """
    Normalized, canonical representation of a multi-turn dialogue transcript.
    """
    model_config = ConfigDict(frozen=True, extra="forbid")

    transcript_id: Optional[str] = Field(default=None, description="Optional call or transcript identifier")
    utterances: List[Utterance] = Field(default_factory=list, description="Ordered canonical utterances")

    @property
    def total_utterances(self) -> int:
        return len(self.utterances)

    @property
    def duration(self) -> float:
        if not self.utterances:
            return 0.0
        return max(u.end_time for u in self.utterances)
