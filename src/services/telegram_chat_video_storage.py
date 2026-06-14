from __future__ import annotations

import os
import tempfile
from pathlib import Path

from aiogram.types import Message

from src.services.telegram_chat_media_storage import StoredTelegramChatMedia, telegram_chat_media_storage


class TelegramChatVideoStorage:
    async def save_from_message(self, bot, message: Message) -> StoredTelegramChatMedia | None:
        video = message.video
        if not video:
            return None

        temp_path = None
        try:
            suffix = Path(video.file_name or "").suffix or ".mp4"
            file_info = await bot.get_file(video.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                temp_path = tmp.name
            await bot.download_file(file_info.file_path, destination=temp_path)

            return telegram_chat_media_storage.save_file(
                temp_path,
                filename=video.file_name or "telegram-video.mp4",
                mimetype=video.mime_type or "video/mp4",
            )
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


telegram_chat_video_storage = TelegramChatVideoStorage()
