"""Tracked Telegram entry links for quiz-domain campaigns."""

from __future__ import annotations

import re
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.schemas.analytics import FunnelSessionCreate
from src.services.analytics_service import analytics_service


CAMPAIGN_RE = re.compile(r"[^a-zA-Z0-9_-]+")


def clean_campaign_slug(value: str) -> str:
    cleaned = CAMPAIGN_RE.sub("-", (value or "").strip()).strip("-_").lower()
    return cleaned[:80] or "telegram-direct"


def telegram_entry_target() -> str:
    target = (settings.telegram_business_profile_url or "").strip()
    if target:
        return target

    username = (settings.telegram_bot_username or "").strip().lstrip("@")
    if username:
        return f"https://t.me/{username}"

    return "https://t.me/Isaev_CRM"


async def create_tracked_telegram_entry(
    *,
    db: AsyncSession,
    org_id,
    campaign: str,
    request: Request,
    utm_content: str | None = None,
    utm_term: str | None = None,
) -> str:
    campaign_slug = clean_campaign_slug(campaign)
    entry_url = str(request.url)
    referrer = request.headers.get("referer")
    user_agent = request.headers.get("user-agent")
    target = telegram_entry_target()

    session = await analytics_service.create_session(
        db=db,
        org_id=org_id,
        data=FunnelSessionCreate(
            funnel_name="telegram_direct_chat",
            channel="telegram",
            source="telegram_groups",
            utm_source="telegram",
            utm_medium="group_outreach",
            utm_campaign=campaign_slug,
            utm_content=utm_content,
            utm_term=utm_term,
            entry_url=entry_url,
            referrer=referrer,
            metadata={
                "entry": "telegram_direct_chat",
                "campaign_slug": campaign_slug,
                "target": target,
                "user_agent": user_agent,
                "client_host": request.client.host if request.client else None,
            },
        ),
    )

    event_data: dict[str, Any] = {
        "messenger": "telegram",
        "source": "telegram_groups",
        "campaign": campaign_slug,
        "entry_url": entry_url,
        "target": target,
        "utm_content": utm_content,
        "utm_term": utm_term,
    }
    await analytics_service.record_event(
        db=db,
        session_token=session.session_token,
        event_type="telegram_clicked",
        step_id="messenger",
        event_data=event_data,
    )
    return target
