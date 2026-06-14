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
        return self.save_file(source_path, filename="telegram-photo.jpg", mimetype="image/jpeg")

    def save_file(
        self,
        source_path: str | os.PathLike[str],
        *,
        filename: str = "telegram-file",
        mimetype: str | None = None,
    ) -> StoredTelegramChatMedia | None:
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
            filename=self._display_name(filename, ext),
            mimetype=mimetype or mimetypes.guess_type(destination.name)[0],
            size=destination.stat().st_size,
        )

    def _display_name(self, filename: str, ext: str) -> str:
        clean_name = Path(filename or "").name.strip()
        if clean_name and Path(clean_name).suffix:
            return clean_name[:180]
        return f"{clean_name or 'telegram-file'}{ext}"[:180]


telegram_chat_media_storage = TelegramChatMediaStorage()
