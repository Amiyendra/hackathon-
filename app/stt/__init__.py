"""
Speech-to-Text (STT) Module for Aurethis QA Control Center.

Provides provider-specific audio transcription adapters (Deepgram) converting
prerecorded audio files into canonical dialogue transcripts.
"""

from app.stt.adapter import DeepgramAdapter
from app.stt.base import BaseSTTClient
from app.stt.deepgram_client import DEFAULT_DEEPGRAM_ENDPOINT, DeepgramSTTClient
from app.stt.exceptions import (
    AudioValidationError,
    DeepgramAPIError,
    DeepgramAuthError,
    DeepgramError,
    STTError,
)
from app.stt.models import AudioFormat, DeepgramUtterance, DeepgramWord, SpeakerRole

__all__ = [
    "BaseSTTClient",
    "DeepgramSTTClient",
    "DeepgramAdapter",
    "DEFAULT_DEEPGRAM_ENDPOINT",
    "STTError",
    "AudioValidationError",
    "DeepgramError",
    "DeepgramAuthError",
    "DeepgramAPIError",
    "AudioFormat",
    "SpeakerRole",
    "DeepgramWord",
    "DeepgramUtterance",
]
