from typing import Any
import logging

import httpx

from src.config import settings

logger = logging.getLogger(__name__)

SENSITIVE_KEYS = {
    "phone",
    "name",
    "full_name",
    "email",
    "address",
    "measurement_address",
    "client_phone",
    "contact_phone",
    "telegram_username",
    "username",
    "file",
    "filename",
    "url",
}


class PostHogService:
    def is_enabled(self) -> bool:
        return bool(settings.posthog_enabled and settings.posthog_project_api_key)

    def public_config(self) -> dict[str, str | bool]:
        return {
            "enabled": self.is_enabled(),
            "host": settings.posthog_host,
            "project_api_key": settings.posthog_project_api_key if self.is_enabled() else "",
        }

    async def capture(
        self,
        distinct_id: str,
        event: str,
        properties: dict[str, Any] | None = None,
    ) -> None:
        if not self.is_enabled():
            return

        payload = {
            "api_key": settings.posthog_project_api_key,
            "event": event,
            "distinct_id": distinct_id,
            "properties": self._sanitize(properties or {}),
        }

        try:
            async with httpx.AsyncClient(
                timeout=httpx.Timeout(settings.posthog_timeout_seconds, connect=2.0)
            ) as client:
                response = await client.post(
                    f"{settings.posthog_host.rstrip('/')}/capture/",
                    json=payload,
                )
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("PostHog capture failed for %s: %s", event, exc)

    def _sanitize(self, value: Any) -> Any:
        if isinstance(value, dict):
            clean: dict[str, Any] = {}
            for key, item in value.items():
                if str(key).lower() in SENSITIVE_KEYS:
                    continue
                clean[key] = self._sanitize(item)
            return clean
        if isinstance(value, list):
            return [self._sanitize(item) for item in value]
        return value


posthog_service = PostHogService()
