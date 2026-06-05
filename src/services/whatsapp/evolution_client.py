from __future__ import annotations

import logging
from typing import Any

import httpx

from src.config import settings
from src.services.whatsapp.phone import normalize_phone_digits
from src.services.whatsapp.types import WhatsAppAttachment, WhatsAppIncomingMessage, WhatsAppSendResult

logger = logging.getLogger(__name__)


class EvolutionError(Exception):
    pass


class EvolutionClient:
    provider = "evolution"

    def is_configured(self) -> bool:
        return bool(
            settings.evolution_enabled
            and settings.evolution_api_base_url.strip()
            and settings.evolution_api_key.strip()
            and settings.evolution_instance.strip()
        )

    def is_valid_webhook_token(self, token: str | None) -> bool:
        expected = (settings.evolution_webhook_token or "").strip()
        if not expected:
            return True
        return (token or "").strip() == expected

    async def send_text(self, chat_id: str, text: str) -> WhatsAppSendResult:
        if not self.is_configured():
            raise EvolutionError("Evolution API is not configured")
        number = normalize_phone_digits(chat_id)
        if not number:
            raise EvolutionError("Invalid WhatsApp phone/chat id")

        data = await self._post(
            f"/message/sendText/{settings.evolution_instance.strip()}",
            {"number": number, "text": text},
        )
        return self._send_result(data, chat_id=number)

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
        if not self.is_configured():
            raise EvolutionError("Evolution API is not configured")
        number = normalize_phone_digits(chat_id)
        if not number:
            raise EvolutionError("Invalid WhatsApp phone/chat id")

        payload = {
            "number": number,
            "mediatype": mediatype,
            "media": media_url,
        }
        if mimetype:
            payload["mimetype"] = mimetype
        if filename:
            payload["fileName"] = filename
        if caption:
            payload["caption"] = caption

        data = await self._post(f"/message/sendMedia/{settings.evolution_instance.strip()}", payload)
        return self._send_result(data, chat_id=number)

    async def get_connection_state(self) -> dict[str, Any]:
        if not self.is_configured():
            raise EvolutionError("Evolution API is not configured")
        return await self._get(f"/instance/connectionState/{settings.evolution_instance.strip()}")

    def extract_incoming_messages(self, payload: Any) -> list[WhatsAppIncomingMessage]:
        items = self._payload_items(payload)
        result: list[WhatsAppIncomingMessage] = []
        for item in items:
            if not isinstance(item, dict):
                continue
            if self._is_outbound(item):
                continue

            chat_id = self._chat_id(item)
            if not chat_id:
                continue

            text = self._message_text(item)
            attachment = self._attachment(item)
            if not text and not attachment:
                continue

            result.append(
                WhatsAppIncomingMessage(
                    provider=self.provider,
                    instance=str(payload.get("instance") or payload.get("instanceName") or "") if isinstance(payload, dict) else None,
                    chat_id=chat_id,
                    message_id=self._message_id(item),
                    text=text,
                    sender_name=self._sender_name(item),
                    raw=item,
                    attachment=attachment,
                )
            )
        return result

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return await self._request("POST", path, payload=payload)

    async def _get(self, path: str) -> dict[str, Any]:
        return await self._request("GET", path)

    async def _request(self, method: str, path: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"{settings.evolution_api_base_url.rstrip('/')}{path}"
        headers = {
            "apikey": settings.evolution_api_key.strip(),
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        timeout = max(3, int(settings.evolution_timeout_seconds))
        try:
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.request(method, url, json=payload, headers=headers)
            if response.status_code >= 400:
                raise EvolutionError(f"Evolution API request failed ({response.status_code}): {response.text}")
            data = response.json() if response.content else {}
            return data if isinstance(data, dict) else {"raw": data}
        except httpx.TimeoutException as exc:
            raise EvolutionError("Evolution API request timeout") from exc
        except httpx.HTTPError as exc:
            raise EvolutionError(f"Evolution API HTTP error: {exc}") from exc

    def _payload_items(self, payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return [item for item in payload if isinstance(item, dict)]
        if not isinstance(payload, dict):
            return []

        data = payload.get("data")
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            if isinstance(data.get("messages"), list):
                return [item for item in data["messages"] if isinstance(item, dict)]
            return [data]

        for key in ("messages", "message", "events"):
            value = payload.get(key)
            if isinstance(value, list):
                return [item for item in value if isinstance(item, dict)]
            if isinstance(value, dict):
                return [value]
        return [payload]

    def _is_outbound(self, item: dict[str, Any]) -> bool:
        key = item.get("key") if isinstance(item.get("key"), dict) else {}
        if key.get("fromMe") is True:
            return True
        direction = str(item.get("direction") or item.get("type") or "").lower()
        return direction in {"outbound", "out", "sent"}

    def _chat_id(self, item: dict[str, Any]) -> str | None:
        key = item.get("key") if isinstance(item.get("key"), dict) else {}
        remote_jid = key.get("remoteJid") or item.get("remoteJid") or item.get("chatId") or item.get("from")
        digits = normalize_phone_digits(str(remote_jid) if remote_jid else None)
        return digits

    def _message_id(self, item: dict[str, Any]) -> str | None:
        key = item.get("key") if isinstance(item.get("key"), dict) else {}
        value = key.get("id") or item.get("id") or item.get("messageId")
        return str(value) if value else None

    def _sender_name(self, item: dict[str, Any]) -> str | None:
        value = item.get("pushName") or item.get("senderName") or item.get("contactName")
        return str(value) if value else None

    def _message_text(self, item: dict[str, Any]) -> str:
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        extended = message.get("extendedTextMessage") if isinstance(message.get("extendedTextMessage"), dict) else {}
        conversation = message.get("conversation")
        captions = [
            message.get("imageMessage", {}).get("caption") if isinstance(message.get("imageMessage"), dict) else None,
            message.get("videoMessage", {}).get("caption") if isinstance(message.get("videoMessage"), dict) else None,
            message.get("documentMessage", {}).get("caption") if isinstance(message.get("documentMessage"), dict) else None,
        ]
        text = item.get("text") or item.get("messageText") or conversation or extended.get("text") or next((c for c in captions if c), "")
        return str(text or "").strip()

    def _attachment(self, item: dict[str, Any]) -> WhatsAppAttachment | None:
        message = item.get("message") if isinstance(item.get("message"), dict) else {}
        for key in ("imageMessage", "videoMessage", "audioMessage", "documentMessage"):
            media = message.get(key)
            if not isinstance(media, dict):
                continue
            return WhatsAppAttachment(
                url=media.get("url") or item.get("mediaUrl"),
                data_base64=item.get("base64") or media.get("base64"),
                filename=media.get("fileName") or item.get("fileName"),
                mimetype=media.get("mimetype") or item.get("mimetype"),
                size=self._int_or_none(media.get("fileLength") or item.get("fileSize")),
            )

        if item.get("mediaUrl") or item.get("base64"):
            return WhatsAppAttachment(
                url=item.get("mediaUrl"),
                data_base64=item.get("base64"),
                filename=item.get("fileName"),
                mimetype=item.get("mimetype"),
                size=self._int_or_none(item.get("fileSize")),
            )
        return None

    def _send_result(self, data: dict[str, Any], chat_id: str) -> WhatsAppSendResult:
        key = data.get("key") if isinstance(data.get("key"), dict) else {}
        message_id = (
            key.get("id")
            or data.get("messageId")
            or data.get("id")
            or (data.get("data", {}).get("key", {}).get("id") if isinstance(data.get("data"), dict) else None)
        )
        return WhatsAppSendResult(provider=self.provider, message_id=str(message_id) if message_id else None, chat_id=chat_id, raw=data)

    def _int_or_none(self, value: Any) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None


evolution_client = EvolutionClient()
