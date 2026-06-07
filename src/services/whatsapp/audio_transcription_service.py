from __future__ import annotations

import logging
import os
import tempfile
from urllib.parse import urlparse

import httpx

from src.services.voice_service import voice_service
from src.services.whatsapp.types import WhatsAppIncomingMessage

logger = logging.getLogger(__name__)


class WhatsAppAudioTranscriptionService:
    async def transcribe(self, *, item: WhatsAppIncomingMessage, media_url: str | None) -> str | None:
        if not item.attachment:
            return None
        mimetype = (item.attachment.mimetype or "").lower()
        if not mimetype.startswith("audio/"):
            return None

        temp_path, cleanup = await self._audio_temp_path(item=item, media_url=media_url)
        if not temp_path:
            logger.warning("WhatsApp audio transcription skipped: no downloadable audio message_id=%s", item.message_id)
            return None

        try:
            return await voice_service.transcribe_audio(temp_path)
        finally:
            if cleanup:
                try:
                    os.remove(temp_path)
                except OSError:
                    pass

    async def _audio_temp_path(self, *, item: WhatsAppIncomingMessage, media_url: str | None) -> tuple[str | None, bool]:
        local_path = self._local_media_path(media_url)
        if local_path:
            return local_path, False

        if media_url and self._is_public_url(media_url):
            return await self._download_temp_audio(media_url), True
        if item.attachment and item.attachment.url and self._is_public_url(item.attachment.url):
            return await self._download_temp_audio(item.attachment.url), True
        return None, False

    def _local_media_path(self, media_url: str | None) -> str | None:
        if not media_url or self._is_public_url(media_url):
            return None
        relative = media_url.lstrip("/")
        path = os.path.join(os.getcwd(), relative)
        return path if os.path.exists(path) else None

    def _is_public_url(self, value: str | None) -> bool:
        if not value:
            return False
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.netloc)

    async def _download_temp_audio(self, url: str) -> str | None:
        try:
            async with httpx.AsyncClient(timeout=30) as client:
                response = await client.get(url)
                response.raise_for_status()
        except Exception:
            logger.warning("Failed to download WhatsApp audio for transcription: %s", url, exc_info=True)
            return None

        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_file.write(response.content)
            return temp_file.name


whatsapp_audio_transcription_service = WhatsAppAudioTranscriptionService()
