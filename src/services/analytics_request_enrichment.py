from __future__ import annotations

from typing import Any

from fastapi import Request


BOT_USER_AGENT_MARKERS = (
    "bot",
    "crawler",
    "spider",
    "preview",
    "facebookexternalhit",
    "telegrambot",
    "whatsapp",
    "vkshare",
    "twitterbot",
    "slackbot",
    "discordbot",
)


def enrich_funnel_metadata(request: Request, metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Merge client analytics metadata with safe request context."""
    clean_metadata = dict(metadata or {})
    user_agent = _header(request, "user-agent")
    cf_ip = _header(request, "cf-connecting-ip")
    forwarded_for = _header(request, "x-forwarded-for")

    clean_metadata["request_context"] = {
        "user_agent": user_agent,
        "referer": _header(request, "referer"),
        "accept_language": _header(request, "accept-language"),
        "cf_country": _header(request, "cf-ipcountry"),
        "cf_ray": _header(request, "cf-ray"),
        "host": _header(request, "host"),
        "client_ip": cf_ip or _first_forwarded_ip(forwarded_for) or _client_host(request),
        "is_likely_bot": _is_likely_bot(user_agent),
    }
    return clean_metadata


def _header(request: Request, name: str) -> str | None:
    value = request.headers.get(name)
    return value.strip() if value else None


def _client_host(request: Request) -> str | None:
    return request.client.host if request.client else None


def _first_forwarded_ip(value: str | None) -> str | None:
    if not value:
        return None
    first = value.split(",")[0].strip()
    return first or None


def _is_likely_bot(user_agent: str | None) -> bool:
    if not user_agent:
        return False
    lowered = user_agent.lower()
    return any(marker in lowered for marker in BOT_USER_AGENT_MARKERS)
