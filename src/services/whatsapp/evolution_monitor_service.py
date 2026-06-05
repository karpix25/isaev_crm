from __future__ import annotations

import asyncio
import base64
import io
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

from src.config import settings
from src.services.whatsapp.evolution_client import EvolutionError, evolution_client

logger = logging.getLogger(__name__)


BAD_STATES = {"close", "closed", "disconnected", "disconnect", "offline", "error"}
GOOD_STATES = {"open", "connected", "online"}


class EvolutionMonitorService:
    def __init__(self) -> None:
        self._last_state: str | None = None
        self._last_alert_at: datetime | None = None

    async def check_once(self) -> str | None:
        if not self._should_check():
            return None

        try:
            payload = await evolution_client.get_connection_state()
            state = self._extract_state(payload)
        except EvolutionError as exc:
            state = "error"
            await self._notify_if_needed(state=state, error=str(exc))
            self._last_state = state
            return state

        if self._is_bad_state(state):
            await self._notify_if_needed(state=state)
        elif self._is_good_state(state) and self._last_state and self._is_bad_state(self._last_state):
            await self._notify_recovered(state=state)
            self._last_alert_at = None

        self._last_state = state
        return state

    def _should_check(self) -> bool:
        return bool(
            settings.evolution_monitor_enabled
            and settings.whatsapp_provider.strip().lower() == "evolution"
            and evolution_client.is_configured()
        )

    def _extract_state(self, payload: dict[str, Any]) -> str:
        instance = payload.get("instance") if isinstance(payload.get("instance"), dict) else {}
        values = [
            payload.get("state"),
            payload.get("connectionState"),
            payload.get("status"),
            instance.get("state"),
            instance.get("connectionStatus"),
        ]
        for value in values:
            if value:
                return str(value).strip().lower()
        return "unknown"

    def _is_bad_state(self, state: str | None) -> bool:
        return (state or "").strip().lower() in BAD_STATES

    def _is_good_state(self, state: str | None) -> bool:
        return (state or "").strip().lower() in GOOD_STATES

    async def _notify_if_needed(self, *, state: str, error: str | None = None) -> None:
        now = datetime.now(timezone.utc)
        cooldown = timedelta(minutes=max(1, int(settings.evolution_monitor_alert_cooldown_minutes)))
        if self._last_alert_at and now - self._last_alert_at < cooldown and state == self._last_state:
            return

        self._last_alert_at = now
        await self._send_manager_alert(state=state, error=error)

    async def _notify_recovered(self, *, state: str) -> None:
        await self._send_manager_alert(state=state, recovered=True)

    async def _send_manager_alert(self, *, state: str, error: str | None = None, recovered: bool = False) -> None:
        try:
            from src.services.telegram_notification_service import telegram_notification_service

            if recovered:
                text = (
                    "✅ WhatsApp Evolution снова подключен\n\n"
                    f"Инстанс: {settings.evolution_instance}\n"
                    f"Состояние: {state}"
                )
            else:
                qr_payload = await self._build_auth_qr_payload()
                pairing_code = qr_payload.get("pairingCode") if qr_payload else None
                text = (
                    "⚠️ WhatsApp Evolution отключен\n\n"
                    f"Инстанс: {settings.evolution_instance}\n"
                    f"Состояние: {state}\n"
                    f"Ошибка: {error[:700] if error else 'нет'}\n"
                    f"Код сопряжения: {pairing_code or 'не получен'}\n\n"
                    "Переподключите WhatsApp: отсканируйте QR в следующем сообщении. "
                    "Пока статус не станет open/connected, автоответы WhatsApp не уйдут."
                )
            await telegram_notification_service.send_to_managers(text, topic="system_alert")
            if not recovered and qr_payload and qr_payload.get("qr_png"):
                await telegram_notification_service.send_photo_to_managers(
                    qr_payload["qr_png"],
                    filename="evolution-whatsapp-login.png",
                    caption="QR для авторизации WhatsApp Evolution. Если не сработал, дождитесь следующего уведомления или обновите QR в Evolution Manager.",
                    topic="system_alert",
                )
        except Exception:
            logger.warning("Failed to send Evolution monitor alert", exc_info=True)

    async def _build_auth_qr_payload(self) -> dict[str, Any] | None:
        try:
            payload = await evolution_client.connect_instance()
        except EvolutionError:
            logger.warning("Failed to get Evolution auth QR payload", exc_info=True)
            return None

        qr_png = self._extract_qr_image(payload)
        if qr_png:
            return {**payload, "qr_png": qr_png}

        code = self._extract_qr_code(payload)
        if not code:
            logger.warning("Evolution auth QR payload has no code: %s", payload)
            return payload

        qr_png = self._render_qr_png(code)
        if not qr_png:
            return payload
        return {**payload, "qr_png": qr_png}

    def _extract_qr_image(self, payload: dict[str, Any]) -> bytes | None:
        candidates: list[Any] = [
            payload.get("base64"),
            payload.get("qrcode"),
            payload.get("qrCode"),
        ]
        base64_payload = payload.get("base64") if isinstance(payload.get("base64"), dict) else {}
        candidates.extend([base64_payload.get("base64"), base64_payload.get("qrcode"), base64_payload.get("qrCode")])
        for value in candidates:
            if not isinstance(value, str):
                continue
            marker = "base64,"
            raw_value = value.split(marker, 1)[1] if marker in value else value
            try:
                decoded = base64.b64decode(raw_value, validate=True)
            except Exception:
                continue
            if decoded.startswith(b"\x89PNG") or decoded.startswith(b"\xff\xd8"):
                return decoded
        return None

    def _extract_qr_code(self, payload: dict[str, Any]) -> str | None:
        for key in ("code", "qrcode", "qrCode"):
            value = payload.get(key)
            if value:
                return str(value)
        base64_payload = payload.get("base64") if isinstance(payload.get("base64"), dict) else {}
        for key in ("code", "qrcode", "qrCode"):
            value = base64_payload.get(key)
            if value:
                return str(value)
        return None

    def _render_qr_png(self, code: str) -> bytes | None:
        try:
            import qrcode

            image = qrcode.make(code)
            output = io.BytesIO()
            image.save(output, format="PNG")
            return output.getvalue()
        except Exception:
            logger.warning("Failed to render Evolution auth QR", exc_info=True)
            return None


evolution_monitor_service = EvolutionMonitorService()


async def start_evolution_monitor_loop(stop_event: asyncio.Event | None = None) -> None:
    stop_event = stop_event or asyncio.Event()
    logger.info(
        "Evolution monitor loop started (enabled=%s interval=%ss)",
        settings.evolution_monitor_enabled,
        settings.evolution_monitor_interval_seconds,
    )

    while not stop_event.is_set():
        try:
            await evolution_monitor_service.check_once()
        except Exception:
            logger.error("Evolution monitor loop failed", exc_info=True)

        try:
            await asyncio.wait_for(
                stop_event.wait(),
                timeout=max(15, int(settings.evolution_monitor_interval_seconds)),
            )
        except asyncio.TimeoutError:
            continue
