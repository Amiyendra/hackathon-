"""
STT Exceptions module.

Defines the error hierarchy for speech-to-text audio ingestion and Deepgram provider integration.
Crucially: Credentials and API keys must NEVER be exposed in any exception string or representation.
"""

from typing import Optional


class STTError(Exception):
    """Base exception for all speech-to-text operations."""
    pass


class AudioValidationError(STTError):
    """Raised when an uploaded audio file fails validation (format, size, content)."""
    pass


class DeepgramError(STTError):
    """Base exception for Deepgram API or adapter failures."""
    pass


class DeepgramAuthError(DeepgramError):
    """Raised when Deepgram authentication fails or credentials are not configured."""
    pass


class DeepgramAPIError(DeepgramError):
    """Raised when Deepgram returns an error status code or communication fails."""

    def __init__(self, message: str, status_code: Optional[int] = None):
        super().__init__(message)
        self.status_code = status_code


__all__ = [
    "STTError",
    "AudioValidationError",
    "DeepgramError",
    "DeepgramAuthError",
    "DeepgramAPIError",
]
