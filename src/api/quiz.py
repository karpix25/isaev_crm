from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession
import httpx
import os
import uuid

from src.bot.utils import get_default_org_id
from src.database import get_db
from src.config import settings
from src.schemas.quiz import (
    MeasurementBookingRequest,
    MeasurementBookingResponse,
    MeasurementSlotsResponse,
    QuizContactCaptureRequest,
    QuizContactCaptureResponse,
    QuizSubmitRequest,
    QuizSubmitResponse,
)
from src.services.cal_pro_service import cal_pro_service
from src.services.posthog_service import posthog_service
from src.services.quiz_service import quiz_service
from src.bot import bot

router = APIRouter(prefix="/quiz", tags=["Quiz"])


@router.get("/config")
async def get_quiz_public_config():
    """Public browser config for optional quiz integrations."""
    bot_username = (settings.telegram_bot_username or "").replace("@", "").strip()
    if not bot_username and bot:
        try:
            me = await bot.get_me()
            bot_username = (getattr(me, "username", None) or "").replace("@", "").strip()
        except Exception:
            bot_username = ""

    return {
        "posthog": posthog_service.public_config(),
        "telegram": {
            "bot_username": bot_username,
        },
    }


@router.get("/measurement-slots", response_model=MeasurementSlotsResponse)
async def get_measurement_slots(
    days: int = Query(14, ge=1, le=45),
):
    """Public endpoint for the renovation quiz to show Cal Pro measurement slots."""
    if not cal_pro_service.is_configured():
        return MeasurementSlotsResponse(enabled=False, reason=cal_pro_service.missing_reason(), slots=[])
    slots = await cal_pro_service.get_slots(days_ahead=days)
    return MeasurementSlotsResponse(enabled=True, slots=slots)


@router.post("/submit", response_model=QuizSubmitResponse, status_code=status.HTTP_201_CREATED)
async def submit_quiz(
    payload: QuizSubmitRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create/update CRM lead from quiz answers and return measurement slots when relevant."""
    try:
        org_id = await get_default_org_id(db)
        lead, session_token, slots = await quiz_service.submit_quiz(db=db, org_id=org_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return QuizSubmitResponse(
        lead_id=lead.id,
        session_token=session_token,
        status="ok",
        should_offer_measurement=quiz_service.should_offer_measurement(payload.answers),
        measurement_slots=slots,
    )


@router.post("/capture-contact", response_model=QuizContactCaptureResponse, status_code=status.HTTP_201_CREATED)
async def capture_quiz_contact(
    payload: QuizContactCaptureRequest,
    db: AsyncSession = Depends(get_db),
):
    """Create/update CRM lead when a visitor saves an unfinished quiz calculation."""
    try:
        org_id = await get_default_org_id(db)
        lead, session_token = await quiz_service.capture_contact(db=db, org_id=org_id, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    return QuizContactCaptureResponse(lead_id=lead.id, session_token=session_token, status="ok")


@router.post("/design-project")
async def upload_design_project(
    session_token: str = Form(...),
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """Upload a client design project file from the public quiz."""
    if not file.filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File is required")

    safe_ext = os.path.splitext(file.filename)[1].lower()
    if safe_ext not in {".pdf", ".jpg", ".jpeg", ".png", ".zip", ".rar", ".dwg"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Unsupported file type")

    content = await file.read()
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File is too large")

    media_dir = os.path.join(os.getcwd(), "media", "design_projects")
    os.makedirs(media_dir, exist_ok=True)
    filename = f"{uuid.uuid4()}{safe_ext}"
    full_path = os.path.join(media_dir, filename)
    with open(full_path, "wb") as out:
        out.write(content)

    url = f"/media/design_projects/{filename}"
    try:
        await quiz_service.record_design_upload(db=db, session_token=session_token, url=url, filename=file.filename)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

    return {"url": url, "filename": file.filename}


@router.post("/book-measurement", response_model=MeasurementBookingResponse)
async def book_measurement(
    payload: MeasurementBookingRequest,
    db: AsyncSession = Depends(get_db),
):
    """Book selected measurement slot in Cal Pro and attach it to CRM lead context."""
    try:
        booking, lead_id = await quiz_service.book_measurement(db=db, payload=payload)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text[:500] if exc.response is not None else "Cal Pro booking failed"
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=detail)
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(exc))

    return MeasurementBookingResponse(
        status="ok",
        booking_uid=quiz_service.extract_booking_uid(booking),
        booking=booking,
        lead_id=lead_id,
        session_token=payload.session_token,
    )
