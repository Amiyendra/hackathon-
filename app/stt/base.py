"""
Base Speech-to-Text (STT) Client interface.

Defines the contract for speech-to-text service providers.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseSTTClient(ABC):
    """Abstract base class for STT provider clients."""

    @abstractmethod
    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Transcribe prerecorded audio synchronously or asynchronously.

        Args:
            audio_bytes: Raw binary bytes of the audio file.
            mime_type: MIME content-type of the audio (e.g. 'audio/wav', 'audio/mp3').
            **kwargs: Provider-specific query parameters or options.

        Returns:
            Provider-specific JSON response dictionary.

        Raises:
            DeepgramAuthError: If authentication or credentials fail.
            DeepgramAPIError: If the provider API rejects the request or fails.
        """
        pass


__all__ = ["BaseSTTClient"]
