"""
STT Provider and Audio Models.

Data structures representing audio formats, speaker role mappings, and Deepgram results.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class AudioFormat(str, Enum):
    """Supported prerecorded audio formats."""
    MP3 = "mp3"
    WAV = "wav"


class SpeakerRole(str, Enum):
    """Canonical speaker roles."""
    AGENT = "AGENT"
    CUSTOMER = "CUSTOMER"


class DeepgramWord(BaseModel):
    """Word-level timing information returned by Deepgram."""
    model_config = ConfigDict(extra="ignore")

    word: str = Field(..., description="Verbatim word string")
    start: float = Field(..., ge=0.0, description="Start offset in seconds")
    end: float = Field(..., ge=0.0, description="End offset in seconds")
    confidence: Optional[float] = Field(default=None, description="Confidence score")
    speaker: Optional[int] = Field(default=None, description="Integer speaker channel / diarization index")
    punctuated_word: Optional[str] = Field(default=None, description="Word including trailing punctuation")


class DeepgramUtterance(BaseModel):
    """Utterance segment returned by Deepgram when utterances=true."""
    model_config = ConfigDict(extra="ignore")

    start: float = Field(..., ge=0.0, description="Start timestamp of utterance")
    end: float = Field(..., ge=0.0, description="End timestamp of utterance")
    transcript: str = Field(..., description="Verbatim text of utterance")
    confidence: Optional[float] = Field(default=None, description="Utterance confidence score")
    speaker: Optional[int] = Field(default=None, description="Integer speaker index")
    words: List[DeepgramWord] = Field(default_factory=list, description="Word timings within utterance")


__all__ = [
    "AudioFormat",
    "SpeakerRole",
    "DeepgramWord",
    "DeepgramUtterance",
]
