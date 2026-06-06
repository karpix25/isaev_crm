from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

from src.config import settings

logger = logging.getLogger(__name__)

TelegramNotificationTopic = Literal["hot_lead", "estimate_request", "measurement", "manual_help", "system_alert"]

TOPIC_SETTINGS: dict[TelegramNotificationTopic, str] = {
    "hot_lead": "hot_lead_telegram_ids",
    "estimate_request": "estimate_request_telegram_ids",
    "measurement": "measurement_telegram_ids",
    "manual_help": "manual_help_telegram_ids",
    "system_alert": "system_alert_telegram_ids",
}


@dataclass(frozen=True)
class TelegramRecipient:
    chat_id: int
    message_thread_id: int | None = None


@dataclass(frozen=True)
class TelegramRecipientResolution:
    topic: TelegramNotificationTopic | None
    setting_name: str | None
    raw_value: str
    recipients: tuple[TelegramRecipient, ...]
    source: str


class TelegramNotificationService:
    TOPIC_LABELS: dict[TelegramNotificationTopic, str] = {
        "hot_lead": "🔥 Горячий лид",
        "estimate_request": "🧮 Просчет сметы",
        "measurement": "📅 Замеры",
        "manual_help": "💬 Ручная помощь",
        "system_alert": "⚠️ Тех. уведомления",
    }

    def manager_recipients(self) -> list[TelegramRecipient]:
        recipients = self._parse_recipient_list(settings.manager_telegram_ids)

        legacy_id = getattr(settings, "manager_telegram_id", None)
        if legacy_id:
            try:
                recipients.append(TelegramRecipient(chat_id=int(legacy_id)))
            except (TypeError, ValueError):
                logger.warning("Invalid MANAGER_TELEGRAM_ID value skipped: %s", legacy_id)

        return self._unique_recipients(recipients)

    def recipients_for(self, topic: TelegramNotificationTopic | None = None) -> list[TelegramRecipient]:
        return list(self.resolve_recipients(topic).recipients)

    def resolve_recipients(self, topic: TelegramNotificationTopic | None = None) -> TelegramRecipientResolution:
        if not topic:
            recipients = tuple(self.manager_recipients())
            return TelegramRecipientResolution(
                topic=None,
                setting_name="manager_telegram_ids",
                raw_value=str(settings.manager_telegram_ids or ""),
                recipients=recipients,
                source="manager" if recipients else "empty",
            )

        setting_name = TOPIC_SETTINGS[topic]
        raw_value = str(getattr(settings, setting_name, "") or "")
        topic_recipients = self._parse_recipient_list(raw_value)
        if topic_recipients:
            return TelegramRecipientResolution(
                topic=topic,
                setting_name=setting_name,
                raw_value=raw_value,
                recipients=tuple(self._unique_recipients(topic_recipients)),
                source="topic",
            )

        fallback = tuple(self.manager_recipients())
        return TelegramRecipientResolution(
            topic=topic,
            setting_name=setting_name,
            raw_value=raw_value,
            recipients=fallback,
            source="fallback" if fallback else "empty",
        )

    def topic_diagnostics(self) -> list[TelegramRecipientResolution]:
        return [self.resolve_recipients(topic) for topic in TOPIC_SETTINGS]

    def manager_chat_ids(self) -> list[int]:
        return sorted({recipient.chat_id for recipient in self.manager_recipients()})

    def has_recipients(self, topic: TelegramNotificationTopic | None = None) -> bool:
        return bool(self.recipients_for(topic))

    def _parse_recipient_list(self, raw_ids: str | None) -> list[TelegramRecipient]:
        recipients: list[TelegramRecipient] = []
        for chunk in (raw_ids or "").strip().replace(";", ",").split(","):
            recipient = self._parse_recipient(chunk)
            if recipient:
                recipients.append(recipient)
        return recipients

    def _unique_recipients(self, recipients: list[TelegramRecipient]) -> list[TelegramRecipient]:
        seen: set[TelegramRecipient] = set()
        unique_recipients: list[TelegramRecipient] = []
        for recipient in recipients:
            if recipient in seen:
                continue
            seen.add(recipient)
            unique_recipients.append(recipient)
        return unique_recipients

    def _parse_recipient(self, raw_value: str) -> TelegramRecipient | None:
        value = raw_value.strip()
        if not value:
            return None
        if self._looks_like_telegram_link(value):
            return self._parse_telegram_link(value)

        chat_part = value
        thread_part: str | None = None
        if ":" in value:
            chat_part, thread_part = value.rsplit(":", 1)

        try:
            chat_id = int(chat_part.strip())
            message_thread_id = int(thread_part.strip()) if thread_part else None
        except ValueError:
            logger.warning("Invalid MANAGER_TELEGRAM_IDS value skipped: %s", value)
            return None
        return TelegramRecipient(chat_id=chat_id, message_thread_id=message_thread_id)

    def _looks_like_telegram_link(self, value: str) -> bool:
        normalized = value.lower()
        return normalized.startswith(("https://t.me/", "http://t.me/", "https://telegram.me/", "http://telegram.me/"))

    def _parse_telegram_link(self, value: str) -> TelegramRecipient | None:
        parsed = urlparse(value)
        parts = [part for part in parsed.path.strip("/").split("/") if part]
        if len(parts) < 3 or parts[0] != "c":
            logger.warning("Unsupported Telegram recipient link skipped: %s", value)
            return None

        try:
            internal_chat_id = int(parts[1])
            message_thread_id = int(parts[2])
        except ValueError:
            logger.warning("Invalid Telegram recipient link skipped: %s", value)
            return None

        chat_id = int(f"-100{internal_chat_id}")
        return TelegramRecipient(chat_id=chat_id, message_thread_id=message_thread_id)

    async def send_to_managers(
        self,
        text: str,
        *,
        parse_mode: str | None = None,
        topic: TelegramNotificationTopic | None = None,
    ) -> int:
        try:
            from src.bot import bot
        except Exception:
            bot = None

        recipients = self.recipients_for(topic)
        if not bot or not recipients:
            logger.warning(
                "Manager Telegram notification skipped: topic=%s bot_present=%s recipients=%s",
                topic or "default",
                bool(bot),
                len(recipients),
            )
            return 0

        logger.info(
            "Sending manager Telegram notification: topic=%s recipients=%s",
            topic or "default",
            recipients,
        )
        sent = 0
        for recipient in recipients:
            try:
                await bot.send_message(
                    chat_id=recipient.chat_id,
                    message_thread_id=recipient.message_thread_id,
                    text=text,
                    parse_mode=parse_mode,
                )
                sent += 1
                logger.info(
                    "Manager Telegram notification delivered: topic=%s chat_id=%s thread_id=%s",
                    topic or "default",
                    recipient.chat_id,
                    recipient.message_thread_id,
                )
            except Exception:
                logger.warning(
                    "Failed to send manager Telegram notification: topic=%s recipient=%s",
                    topic or "default",
                    recipient,
                    exc_info=True,
                )
        return sent

    async def send_photo_to_managers(
        self,
        photo: bytes,
        *,
        filename: str = "notification.png",
        caption: str | None = None,
        parse_mode: str | None = None,
        topic: TelegramNotificationTopic | None = None,
    ) -> int:
        try:
            from aiogram.types import BufferedInputFile
            from src.bot import bot
        except Exception:
            bot = None
            BufferedInputFile = None

        recipients = self.recipients_for(topic)
        if not bot or not BufferedInputFile or not recipients:
            logger.warning(
                "Manager Telegram photo notification skipped: bot_present=%s recipients=%s",
                bool(bot),
                len(recipients),
            )
            return 0

        sent = 0
        for recipient in recipients:
            try:
                photo_file = BufferedInputFile(photo, filename=filename)
                await bot.send_photo(
                    chat_id=recipient.chat_id,
                    message_thread_id=recipient.message_thread_id,
                    photo=photo_file,
                    caption=caption,
                    parse_mode=parse_mode,
                )
                sent += 1
            except Exception:
                logger.warning("Failed to send manager Telegram photo notification to %s", recipient, exc_info=True)
        return sent


telegram_notification_service = TelegramNotificationService()
