from __future__ import annotations

import logging

from src.config import settings

logger = logging.getLogger(__name__)


class TelegramNotificationService:
    def manager_chat_ids(self) -> list[int]:
        ids: list[int] = []

        raw_ids = (settings.manager_telegram_ids or "").strip()
        for chunk in raw_ids.replace(";", ",").split(","):
            value = chunk.strip()
            if not value:
                continue
            try:
                ids.append(int(value))
            except ValueError:
                logger.warning("Invalid MANAGER_TELEGRAM_IDS value skipped: %s", value)

        legacy_id = getattr(settings, "manager_telegram_id", None)
        if legacy_id:
            try:
                ids.append(int(legacy_id))
            except (TypeError, ValueError):
                logger.warning("Invalid MANAGER_TELEGRAM_ID value skipped: %s", legacy_id)

        seen: set[int] = set()
        unique_ids: list[int] = []
        for chat_id in ids:
            if chat_id in seen:
                continue
            seen.add(chat_id)
            unique_ids.append(chat_id)
        return unique_ids

    async def send_to_managers(self, text: str, *, parse_mode: str | None = None) -> int:
        try:
            from src.bot import bot
        except Exception:
            bot = None

        chat_ids = self.manager_chat_ids()
        if not bot or not chat_ids:
            logger.warning(
                "Manager Telegram notification skipped: bot_present=%s recipients=%s",
                bool(bot),
                len(chat_ids),
            )
            return 0

        sent = 0
        for chat_id in chat_ids:
            try:
                await bot.send_message(chat_id=chat_id, text=text, parse_mode=parse_mode)
                sent += 1
            except Exception:
                logger.warning("Failed to send manager Telegram notification to %s", chat_id, exc_info=True)
        return sent

    async def send_photo_to_managers(
        self,
        photo: bytes,
        *,
        filename: str = "notification.png",
        caption: str | None = None,
        parse_mode: str | None = None,
    ) -> int:
        try:
            from aiogram.types import BufferedInputFile
            from src.bot import bot
        except Exception:
            bot = None
            BufferedInputFile = None

        chat_ids = self.manager_chat_ids()
        if not bot or not BufferedInputFile or not chat_ids:
            logger.warning(
                "Manager Telegram photo notification skipped: bot_present=%s recipients=%s",
                bool(bot),
                len(chat_ids),
            )
            return 0

        sent = 0
        for chat_id in chat_ids:
            try:
                photo_file = BufferedInputFile(photo, filename=filename)
                await bot.send_photo(chat_id=chat_id, photo=photo_file, caption=caption, parse_mode=parse_mode)
                sent += 1
            except Exception:
                logger.warning("Failed to send manager Telegram photo notification to %s", chat_id, exc_info=True)
        return sent


telegram_notification_service = TelegramNotificationService()
