from __future__ import annotations

import base64
import os
import tempfile

from aiogram.types import Message

from src.services.telegram_chat_media_storage import StoredTelegramChatMedia, telegram_chat_media_storage


class StoredTelegramPhoto:
    def __init__(self, media: StoredTelegramChatMedia | None, image_base64: str | None) -> None:
        self.media = media
        self.image_base64 = image_base64


class TelegramChatPhotoStorage:
    async def save_from_message(self, bot, message: Message) -> StoredTelegramPhoto:
        if not message.photo:
            return StoredTelegramPhoto(None, None)

        photo = message.photo[-1]
        temp_path = None
        try:
            file_info = await bot.get_file(photo.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                temp_path = tmp.name
            await bot.download_file(file_info.file_path, destination=temp_path)

            with open(temp_path, "rb") as photo_file:
                image_base64 = base64.b64encode(photo_file.read()).decode("utf-8")

            media = telegram_chat_media_storage.save_photo_file(temp_path)
            return StoredTelegramPhoto(media, image_base64)
        finally:
            if temp_path and os.path.exists(temp_path):
                os.remove(temp_path)


telegram_chat_photo_storage = TelegramChatPhotoStorage()
