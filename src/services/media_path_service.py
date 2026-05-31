"""Resolve stored media URLs to local files."""

from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse


class MediaPathService:
    def resolve_local_media_path(self, url: str) -> Path:
        path = self._media_url_path(url)
        relative_path = path.lstrip("/")
        candidates = [
            Path.cwd() / relative_path,
            self._project_root() / relative_path,
            Path("/app") / relative_path,
        ]
        for candidate in candidates:
            if candidate.exists():
                return candidate
        return candidates[0]

    def _media_url_path(self, url: str) -> str:
        parsed = urlparse(url)
        path = parsed.path if parsed.scheme else url
        if not path.startswith("/media/"):
            raise ValueError("unsupported_media_url")
        return path

    def _project_root(self) -> Path:
        return Path(__file__).resolve().parents[2]


media_path_service = MediaPathService()
