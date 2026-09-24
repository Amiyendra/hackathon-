"""
Deepgram Prerecorded Speech-to-Text Client.

Interacts with Deepgram's REST API (/v1/listen) to transcribe prerecorded audio
with speaker diarization, utterance segmentation, and word-level timestamps.
"""

import os
from typing import Any, Dict, Optional
import httpx

from app.config import get_deepgram_api_key
from app.stt.base import BaseSTTClient
from app.stt.exceptions import DeepgramAPIError, DeepgramAuthError


DEFAULT_DEEPGRAM_ENDPOINT = "https://api.deepgram.com/v1/listen"


class DeepgramSTTClient(BaseSTTClient):
    """
    HTTP client for Deepgram prerecorded audio transcription.

    Security: The API key is loaded strictly from environment or configuration
    and is never printed, logged, or included in outgoing error messages.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: str = DEFAULT_DEEPGRAM_ENDPOINT,
        http_client: Optional[httpx.Client] = None,
        timeout_seconds: float = 60.0,
    ):
        if api_key is not None:
            self._api_key = api_key.strip()
        else:
            if "DEEPGRAM_API_KEY" not in os.environ:
                self._api_key = None
            else:
                key = get_deepgram_api_key()
                self._api_key = key.strip() if key else None
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds
        self._http_client = http_client

    def _get_client(self) -> httpx.Client:
        if self._http_client is not None:
            return self._http_client
        return httpx.Client(timeout=self.timeout_seconds)

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/wav",
        model: str = "nova-2",
        language: str = "en",
        smart_format: bool = True,
        diarize: bool = True,
        utterances: bool = True,
        punctuate: bool = True,
        **extra_params: Any,
    ) -> Dict[str, Any]:
        """
        Transcribe prerecorded audio using Deepgram.

        Args:
            audio_bytes: Raw bytes of the MP3 or WAV audio file.
            mime_type: MIME type of the audio (e.g. 'audio/mp3', 'audio/wav').
            model: Deepgram model name (defaults to 'nova-2').
            language: Language code (defaults to 'en').
            smart_format: Enable smart formatting.
            diarize: Enable speaker diarization.
            utterances: Enable utterance segmentation.
            punctuate: Enable punctuation.

        Returns:
            Parsed JSON response from Deepgram.

        Raises:
            DeepgramAuthError: If API key is missing or authentication fails.
            DeepgramAPIError: If transcription fails or returns an error status.
        """
        if not self._api_key or not self._api_key.strip():
            raise DeepgramAuthError(
                "Deepgram API key not configured. Set the DEEPGRAM_API_KEY environment variable."
            )

        headers = {
            "Authorization": f"Token {self._api_key}",
            "Content-Type": mime_type,
        }

        params: Dict[str, Any] = {
            "model": model,
            "smart_format": "true" if smart_format else "false",
            "diarize": "true" if diarize else "false",
            "utterances": "true" if utterances else "false",
            "punctuate": "true" if punctuate else "false",
        }
        if language:
            params["language"] = language

        params.update(extra_params)

        client = self._get_client()
        try:
            # We close the client only if we created it locally
            should_close = self._http_client is None
            try:
                response = client.post(
                    self.endpoint,
                    params=params,
                    headers=headers,
                    content=audio_bytes,
                )
            finally:
                if should_close:
                    client.close()

        except httpx.HTTPError as exc:
            raise DeepgramAPIError(
                f"Network or connection error communicating with Deepgram STT service: {type(exc).__name__}"
            ) from exc
        except Exception as exc:
            raise DeepgramAPIError(
                f"Unexpected error communicating with Deepgram STT service: {type(exc).__name__}"
            ) from exc

        if response.status_code in (401, 403):
            raise DeepgramAuthError(
                f"Deepgram authentication failed (HTTP {response.status_code}). Please verify DEEPGRAM_API_KEY."
            )

        if response.status_code >= 400:
            error_detail = ""
            try:
                err_json = response.json()
                error_detail = err_json.get("err_msg") or err_json.get("message") or response.text
            except Exception:
                error_detail = response.text[:200]
            raise DeepgramAPIError(
                f"Deepgram transcription failed with HTTP {response.status_code}: {error_detail}",
                status_code=response.status_code,
            )

        try:
            return response.json()
        except Exception as exc:
            raise DeepgramAPIError(f"Failed to parse Deepgram response JSON: {exc}") from exc


__all__ = ["DeepgramSTTClient", "DEFAULT_DEEPGRAM_ENDPOINT"]
