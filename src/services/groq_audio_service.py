from __future__ import annotations

import logging
import os
from typing import Any

import httpx

from src.config import settings

logger = logging.getLogger(__name__)


class GroqAudioError(Exception):
    """Raised when Groq speech-to-text cannot process audio."""


class GroqAudioService:
    async def transcribe_audio(self, file_path: str, *, language: str = "ru") -> str | None:
        if not settings.groq_api_key:
            logger.info("Groq audio transcription skipped: GROQ_API_KEY is not configured")
            return None
        if not os.path.exists(file_path):
            raise GroqAudioError(f"Audio file does not exist: {file_path}")

        url = f"{settings.groq_audio_base_url.rstrip('/')}/audio/transcriptions"
        timeout = max(5, int(settings.groq_audio_timeout_seconds or 60))
        filename = os.path.basename(file_path) or "audio.ogg"

        try:
            with open(file_path, "rb") as audio_file:
                async with httpx.AsyncClient(timeout=timeout) as client:
                    response = await client.post(
                        url,
                        headers={"Authorization": f"Bearer {settings.groq_api_key}"},
                        data={
                            "model": settings.groq_audio_model,
                            "language": language,
                            "response_format": "json",
                        },
                        files={"file": (filename, audio_file, "application/octet-stream")},
                    )
            if response.status_code >= 400:
                raise GroqAudioError(f"Groq transcription failed ({response.status_code}): {response.text[:1000]}")

            payload: dict[str, Any] = response.json()
            text = str(payload.get("text") or "").strip()
            if text:
                logger.info("Groq transcription successful: %s...", text[:60])
            return text or None
        except httpx.TimeoutException as exc:
            raise GroqAudioError("Groq transcription timeout") from exc
        except httpx.HTTPError as exc:
            raise GroqAudioError(f"Groq transcription HTTP error: {exc}") from exc


groq_audio_service = GroqAudioService()
