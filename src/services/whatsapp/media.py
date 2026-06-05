from __future__ import annotations

import mimetypes
from urllib.parse import urlparse

from src.config import settings


def public_media_url(media_url: str | None) -> str | None:
    if not media_url:
        return None
    value = media_url.strip()
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"} and parsed.netloc:
        return value

    base_url = (settings.app_public_base_url or "").strip().rstrip("/")
    if not base_url:
        return None
    return f"{base_url}/{value.lstrip('/')}"


def media_type_from_mimetype(mimetype: str | None, filename: str | None = None) -> str:
    detected = mimetype or (mimetypes.guess_type(filename or "")[0] if filename else None) or ""
    normalized = detected.lower()
    if normalized.startswith("image/"):
        return "image"
    if normalized.startswith("video/"):
        return "video"
    if normalized.startswith("audio/"):
        return "audio"
    return "document"


def mimetype_for(filename: str | None, fallback: str | None = None) -> str | None:
    return fallback or (mimetypes.guess_type(filename or "")[0] if filename else None)
