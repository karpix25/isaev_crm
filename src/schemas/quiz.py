from datetime import datetime
from typing import Any
import uuid

from pydantic import BaseModel, EmailStr, Field


class QuizPriceRange(BaseModel):
    lo: int | None = None
    hi: int | None = None
    label: str | None = None


class QuizContact(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    phone: str | None = Field(default=None, max_length=50)
    email: EmailStr | None = None
    telegram_username: str | None = None
    preferred_messenger: str | None = Field(default=None, max_length=32)


class QuizSubmitRequest(BaseModel):
    session_token: str | None = None
    contact: QuizContact
    answers: dict[str, Any] = Field(default_factory=dict)
    price: QuizPriceRange | None = None
    source: str | None = "quiz"
    channel: str | None = "web"
    entry_url: str | None = None
    referrer: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    design_project_file_url: str | None = None
    metadata: dict[str, Any] | None = None
    lead_id: uuid.UUID | None = None
    telegram_id: int | None = None


class QuizContactCaptureRequest(BaseModel):
    session_token: str | None = None
    contact: QuizContact
    answers: dict[str, Any] = Field(default_factory=dict)
    source: str | None = "quiz_exit_capture"
    channel: str | None = "web"
    entry_url: str | None = None
    referrer: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    utm_content: str | None = None
    utm_term: str | None = None
    metadata: dict[str, Any] | None = None
    lead_id: uuid.UUID | None = None
    telegram_id: int | None = None


class QuizContactCaptureResponse(BaseModel):
    lead_id: uuid.UUID
    session_token: str
    status: str


class MeasurementSlot(BaseModel):
    start: str
    end: str | None = None
    label: str
    date_label: str
    source: str = "cal_pro"


class QuizSubmitResponse(BaseModel):
    lead_id: uuid.UUID
    session_token: str
    status: str
    should_offer_measurement: bool
    measurement_slots: list[MeasurementSlot] = Field(default_factory=list)


class MeasurementSlotsResponse(BaseModel):
    enabled: bool
    reason: str | None = None
    slots: list[MeasurementSlot] = Field(default_factory=list)


class MeasurementBookingRequest(BaseModel):
    session_token: str
    lead_id: uuid.UUID | None = None
    start: str
    contact: QuizContact | None = None
    answers: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class MeasurementBookingResponse(BaseModel):
    status: str
    booking_uid: str | None = None
    booking: dict[str, Any] | None = None
    lead_id: uuid.UUID | None = None
    session_token: str
