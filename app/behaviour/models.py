"""
Behaviour QA Engine Models.

CRITICAL ARCHITECTURAL INVARIANTS:
- Behaviour checks are NON-BLOCKING by definition (critical=False).
- CheckResult contract is shared across all QA Gate engines.
- Dead air and interruptions are computed deterministically from timestamps.
- Rapport and objection handling use structured semantic evaluation.
"""

from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.factual.models import CheckResult, CheckStatus


class BehaviourCategory(str, Enum):
    """Permitted behaviour check categories."""
    DEAD_AIR = "DEAD_AIR"
    INTERRUPTIONS = "INTERRUPTIONS"
    RAPPORT = "RAPPORT"
    OBJECTION_HANDLING = "OBJECTION_HANDLING"


class DeadAirIncident(BaseModel):
    """Deterministic record of an observed silence gap between utterances."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    preceding_utterance_id: str = Field(..., description="ID of utterance before the silence")
    following_utterance_id: str = Field(..., description="ID of utterance after the silence")
    gap_seconds: float = Field(..., ge=0.0, description="Duration of dead air gap in seconds")
    start_time: float = Field(..., ge=0.0, description="Timestamp when gap started")
    end_time: float = Field(..., ge=0.0, description="Timestamp when gap ended")
    duration: Optional[float] = Field(default=None, description="Duration of dead air gap in seconds")

    @model_validator(mode="after")
    def _compute_duration(self) -> "DeadAirIncident":
        if self.duration is None:
            object.__setattr__(self, "duration", self.gap_seconds)
        return self

    @property
    def gap_duration(self) -> float:
        return self.gap_seconds

    @property
    def gap_start(self) -> float:
        return self.start_time

    @property
    def gap_end(self) -> float:
        return self.end_time

    @property
    def start(self) -> float:
        return self.start_time

    @property
    def end(self) -> float:
        return self.end_time


class InterruptionIncident(BaseModel):
    """Deterministic record of an observed speech collision or interruption."""
    model_config = ConfigDict(frozen=True, extra="forbid")

    interrupter_speaker: str = Field(..., description="Speaker who interrupted")
    interrupted_speaker: str = Field(..., description="Speaker who was interrupted")
    overlap_seconds: float = Field(..., ge=0.0, description="Duration of overlapping speech")
    utterance_id_a: str = Field(..., description="First colliding utterance ID")
    utterance_id_b: str = Field(..., description="Second colliding utterance ID")
    start_time: float = Field(..., ge=0.0, description="Overlap start timestamp")
    end_time: float = Field(..., ge=0.0, description="Overlap end timestamp")


__all__ = [
    "BehaviourCategory",
    "DeadAirIncident",
    "InterruptionIncident",
    "CheckResult",
    "CheckStatus",
]
