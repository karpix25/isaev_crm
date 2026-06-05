from __future__ import annotations

from src.config import settings
from src.services.wazzup_service import WazzupError, wazzup_service
from src.services.whatsapp.evolution_client import EvolutionError, evolution_client
from src.services.whatsapp.types import WhatsAppSendResult


class WhatsAppTransportError(Exception):
    pass


class WhatsAppTransportService:
    def active_provider(self) -> str:
        provider = (settings.whatsapp_provider or "").strip().lower()
        if provider in {"evolution", "wazzup"}:
            return provider
        if evolution_client.is_configured():
            return "evolution"
        return "wazzup"

    def is_configured(self) -> bool:
        if self.active_provider() == "evolution":
            return evolution_client.is_configured()
        return wazzup_service.is_configured()

    async def send_text(self, chat_id: str, text: str) -> WhatsAppSendResult:
        provider = self.active_provider()
        try:
            if provider == "evolution":
                return await evolution_client.send_text(chat_id, text)

            response = await wazzup_service.send_whatsapp_message(chat_id=chat_id, text=text)
            message_id = (
                response.get("messageId")
                or response.get("id")
                or (response.get("data", {}).get("messageId") if isinstance(response.get("data"), dict) else None)
            )
            return WhatsAppSendResult(provider="wazzup", message_id=str(message_id) if message_id else None, chat_id=chat_id, raw=response)
        except (EvolutionError, WazzupError) as exc:
            raise WhatsAppTransportError(str(exc)) from exc

    async def send_media(
        self,
        chat_id: str,
        *,
        media_url: str,
        mediatype: str,
        mimetype: str | None = None,
        filename: str | None = None,
        caption: str | None = None,
    ) -> WhatsAppSendResult:
        provider = self.active_provider()
        if provider != "evolution":
            raise WhatsAppTransportError("WhatsApp media sending is supported only by Evolution API provider")
        try:
            return await evolution_client.send_media(
                chat_id=chat_id,
                media_url=media_url,
                mediatype=mediatype,
                mimetype=mimetype,
                filename=filename,
                caption=caption,
            )
        except EvolutionError as exc:
            raise WhatsAppTransportError(str(exc)) from exc


whatsapp_transport_service = WhatsAppTransportService()
