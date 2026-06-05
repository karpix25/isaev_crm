from __future__ import annotations

import asyncio
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
            from src.bot import bot

            manager_id = getattr(settings, "manager_telegram_id", None)
            if not manager_id or not bot:
                logger.warning(
                    "Evolution monitor alert skipped: manager_id_present=%s bot_present=%s state=%s",
                    bool(manager_id),
                    bool(bot),
                    state,
                )
                return

            if recovered:
                text = (
                    "✅ WhatsApp Evolution снова подключен\n\n"
                    f"Инстанс: {settings.evolution_instance}\n"
                    f"Состояние: {state}"
                )
            else:
                text = (
                    "⚠️ WhatsApp Evolution отключен\n\n"
                    f"Инстанс: {settings.evolution_instance}\n"
                    f"Состояние: {state}\n"
                    f"Ошибка: {error[:700] if error else 'нет'}\n\n"
                    "Переподключите WhatsApp в Evolution API Manager через QR. "
                    "Пока статус не станет open/connected, автоответы WhatsApp не уйдут."
                )
            await bot.send_message(chat_id=manager_id, text=text)
        except Exception:
            logger.warning("Failed to send Evolution monitor alert", exc_info=True)


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
