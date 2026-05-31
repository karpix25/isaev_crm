"""Helpers for storing Telegram files that must be visible in CRM."""

from __future__ import annotations

import os
import re
import uuid
from pathlib import Path


ALLOWED_ESTIMATE_EXTENSIONS = {".pdf", ".jpg", ".jpeg", ".png", ".zip", ".rar", ".dwg", ".xlsx", ".xls"}
MAX_ESTIMATE_FILE_SIZE = 50 * 1024 * 1024


def is_supported_estimate_filename(filename: str | None) -> bool:
    return Path(filename or "").suffix.lower() in ALLOWED_ESTIMATE_EXTENSIONS


async def save_telegram_document(bot, document, directory: str = "estimate_requests") -> tuple[str, str]:
    filename = document.file_name or "telegram-file"
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_ESTIMATE_EXTENSIONS:
        raise ValueError("unsupported_file_type")
    if document.file_size and document.file_size > MAX_ESTIMATE_FILE_SIZE:
        raise ValueError("file_too_large")

    media_dir = Path(os.getcwd()) / "media" / directory
    media_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{uuid.uuid4()}{ext}"
    full_path = media_dir / stored_name

    file_info = await bot.get_file(document.file_id)
    await bot.download_file(file_info.file_path, destination=str(full_path))
    return f"/media/{directory}/{stored_name}", _safe_display_name(filename)


def _safe_display_name(filename: str) -> str:
    cleaned = re.sub(r"[\r\n\t]+", " ", filename).strip()
    return cleaned[:180] or "Файл для расчета"
