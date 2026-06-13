from __future__ import annotations

import mimetypes
import os
import shutil
import uuid
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StoredTelegramChatMedia:
    url: str
    filename: str
    mimetype: str | None
    size: int | None


class TelegramChatMediaStorage:
    def save_photo_file(self, source_path: str | os.PathLike[str]) -> StoredTelegramChatMedia | None:
        source = Path(source_path)
        if not source.exists() or not source.is_file():
            return None

        ext = source.suffix.lower() or ".jpg"
        media_dir = Path(os.getcwd()) / "media" / "telegram_chat"
        media_dir.mkdir(parents=True, exist_ok=True)

        stored_name = f"{uuid.uuid4()}{ext}"
        destination = media_dir / stored_name
        shutil.copyfile(source, destination)

        return StoredTelegramChatMedia(
            url=f"/media/telegram_chat/{stored_name}",
            filename="telegram-photo.jpg" if ext in {".jpg", ".jpeg"} else f"telegram-photo{ext}",
            mimetype=mimetypes.guess_type(destination.name)[0] or "image/jpeg",
            size=destination.stat().st_size,
        )


telegram_chat_media_storage = TelegramChatMediaStorage()
