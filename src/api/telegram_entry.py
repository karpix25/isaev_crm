"""Public tracked redirects from quiz domain to Telegram."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot.utils import get_default_org_id
from src.database import get_db
from src.services.telegram_entry_link_service import create_tracked_telegram_entry


router = APIRouter(prefix="/tg", tags=["Telegram Entry"])


@router.get("")
@router.get("/")
async def default_telegram_entry_redirect(
    request: Request,
    content: str | None = Query(None, max_length=120),
    term: str | None = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db),
):
    return await telegram_entry_redirect(
        campaign="tg",
        request=request,
        content=content,
        term=term,
        db=db,
    )


@router.get("/{campaign}")
async def telegram_entry_redirect(
    campaign: str,
    request: Request,
    content: str | None = Query(None, max_length=120),
    term: str | None = Query(None, max_length=120),
    db: AsyncSession = Depends(get_db),
):
    org_id = await get_default_org_id(db)
    target = await create_tracked_telegram_entry(
        db=db,
        org_id=org_id,
        campaign=campaign,
        request=request,
        utm_content=content,
        utm_term=term,
    )
    return RedirectResponse(url=target, status_code=302)
