from datetime import datetime, timedelta, timezone
from typing import Any
import json
import logging
import uuid
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import FunnelSession, Lead, LeadStatus
from src.schemas.quiz import MeasurementBookingRequest, QuizContact
from src.services.analytics_service import analytics_service
from src.services.cal_pro_service import cal_pro_service

logger = logging.getLogger(__name__)


class MeasurementBookingService:
    AUTO_QUIZ_STATUSES = {
        LeadStatus.NEW.value,
        LeadStatus.QUIZ_COMPLETED.value,
        LeadStatus.MESSENGER_PENDING.value,
        LeadStatus.DESIGN_PENDING.value,
        LeadStatus.DESIGN_REVIEW.value,
        LeadStatus.MEASUREMENT_PENDING.value,
    }

    async def book_from_quiz_payload(
        self,
        db: AsyncSession,
        payload: MeasurementBookingRequest,
        session: FunnelSession,
    ) -> tuple[dict[str, Any], uuid.UUID | None]:
        lead_id = payload.lead_id or session.lead_id
        contact = await self._resolve_contact(db, payload.contact, lead_id)
        if not contact:
            raise ValueError("Booking contact is required")

        metadata = payload.metadata or {}
        measurement_address = (payload.address or metadata.get("measurement_address") or "").strip()
        if not measurement_address:
            raise ValueError("Measurement address is required")

        booking_source = str(metadata.get("source") or "quiz_inline_slots")
        selected_messenger = str(metadata.get("selected_messenger") or "").strip() or None
        analytics_base = self._analytics_base(
            lead_id=lead_id,
            metadata=metadata,
            source=booking_source,
            selected_messenger=selected_messenger,
            has_address=bool(measurement_address),
        )

        logger.info(
            "Measurement booking requested: lead_id=%s start=%s address_present=%s contact_phone_present=%s",
            lead_id,
            payload.start,
            bool(measurement_address),
            bool(getattr(contact, "phone", None)),
        )

        lead = await self._get_lead(db, lead_id)
        existing = await self._prepare_lead_for_booking(
            db=db,
            lead=lead,
            payload=payload,
            contact=contact,
            address=measurement_address,
            source=booking_source,
        )
        if existing:
            return existing, lead_id

        await self._record_event(
            db=db,
            session_token=payload.session_token,
            event_type="measurement_booking_requested",
            data={**analytics_base, "start": payload.start},
        )

        try:
            booking = await cal_pro_service.create_booking(
                start=payload.start,
                contact=contact,
                answers=payload.answers,
                metadata={
                    "lead_id": str(lead_id) if lead_id else None,
                    "session_token": payload.session_token,
                    "client_name": contact.name,
                    "client_phone": contact.phone,
                    "measurement_address": measurement_address,
                    **metadata,
                },
            )
        except (httpx.HTTPError, ValueError) as exc:
            await self._handle_booking_error(
                db=db,
                lead=lead,
                payload=payload,
                contact=contact,
                address=measurement_address,
                analytics_base=analytics_base,
                error=str(exc),
            )
            return {
                "status": "requested",
                "reason": "calendar_booking_failed",
                "start": payload.start,
                "message": "Measurement request saved, but calendar booking failed.",
            }, lead_id

        booking_uid = self.extract_booking_uid(booking)
        if not booking_uid:
            await self._handle_missing_booking_uid(
                db=db,
                lead=lead,
                payload=payload,
                contact=contact,
                address=measurement_address,
                analytics_base=analytics_base,
                booking=booking,
            )
            return {
                "status": "requested",
                "reason": "calendar_booking_uid_missing",
                "start": payload.start,
                "message": "Measurement request saved, but calendar booking was not confirmed.",
            }, lead_id

        await self._complete_booking(
            db=db,
            lead=lead,
            payload=payload,
            contact=contact,
            address=measurement_address,
            booking=booking,
            booking_uid=booking_uid,
        )
        await self._record_event(
            db=db,
            session_token=payload.session_token,
            event_type="measurement_booked",
            data={**analytics_base, "start": payload.start, "booking_uid": booking_uid},
        )
        return booking, lead_id

    def extract_booking_uid(self, booking: dict[str, Any]) -> str | None:
        data = booking.get("data") if isinstance(booking, dict) else None
        source = data if isinstance(data, dict) else booking
        value = source.get("uid") or source.get("id") or source.get("bookingUid")
        return str(value) if value else None

    async def notify_measurement_telegram(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        status: str,
        booking_uid: str | None,
        source: str = "quiz_measurement_booking",
    ) -> None:
        if not lead:
            return
        try:
            from src.services.lead_manager_notification_service import lead_manager_notification_service

            sent = await lead_manager_notification_service.notify_measurement_booking_if_needed(
                db=db,
                lead=lead,
                start=self.format_measurement_start(start),
                address=address,
                status=status,
                booking_uid=booking_uid,
                source=source,
            )
            logger.info("Measurement Telegram notification sent: recipients=%s lead_id=%s status=%s", int(sent), lead.id, status)
        except Exception:
            logger.warning("Failed to send measurement Telegram notification for lead %s", getattr(lead, "id", None), exc_info=True)

    async def enqueue_measurement_reminder(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        booking_uid: str | None,
    ) -> None:
        if not lead:
            return
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
            if start_dt.tzinfo is None:
                start_dt = start_dt.replace(tzinfo=timezone.utc)
            run_at = max(
                start_dt.astimezone(timezone.utc) - timedelta(hours=24),
                datetime.now(timezone.utc) + timedelta(minutes=5),
            )
            from src.services.background_job_service import background_job_service

            await background_job_service.enqueue(
                db=db,
                job_type="measurement_telegram_reminder",
                payload={"lead_id": str(lead.id), "start": start, "address": address, "booking_uid": booking_uid},
                max_attempts=2,
                run_at=run_at,
            )
            logger.info("Measurement Telegram reminder enqueued: lead_id=%s run_at=%s booking_uid=%s", lead.id, run_at.isoformat(), booking_uid)
        except Exception:
            logger.warning("Failed to enqueue measurement reminder for lead %s", getattr(lead, "id", None), exc_info=True)

    def format_measurement_start(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
        except Exception:
            return value

    async def _resolve_contact(
        self,
        db: AsyncSession,
        contact: QuizContact | None,
        lead_id: uuid.UUID | None,
    ) -> QuizContact | None:
        if contact or not lead_id:
            return contact
        lead = await self._get_lead(db, lead_id)
        if lead and lead.full_name:
            return QuizContact(name=lead.full_name, phone=lead.phone)
        return None

    async def _get_lead(self, db: AsyncSession, lead_id: uuid.UUID | None) -> Lead | None:
        if not lead_id:
            return None
        result = await db.execute(select(Lead).where(Lead.id == lead_id))
        return result.scalar_one_or_none()

    async def _prepare_lead_for_booking(
        self,
        db: AsyncSession,
        lead: Lead | None,
        payload: MeasurementBookingRequest,
        contact: QuizContact,
        address: str,
        source: str,
    ) -> dict[str, Any] | None:
        if not lead:
            return None
        data = self._parse_extracted_data(lead.extracted_data)
        self._sync_measurement_address(data, address)
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        if measurement.get("booking_uid") and measurement.get("start") == payload.start:
            await self.notify_measurement_telegram(db, lead, payload.start, address, "booked", str(measurement.get("booking_uid") or ""))
            await self._notify_hot_lead(db, lead, "Клиент записался на замер", "measurement_booking_existing")
            return measurement.get("booking") or {"status": "ok", "data": measurement}

        data["measurement"] = {
            **measurement,
            "start": payload.start,
            "status": "requested",
            "requested_at": datetime.now(timezone.utc).isoformat(),
            "address": address,
            "phone": contact.phone,
            "selected_slot_label": (payload.metadata or {}).get("selected_slot_label"),
            "source": source,
        }
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        if lead.status in self.AUTO_QUIZ_STATUSES:
            lead.status = LeadStatus.MEASUREMENT_PENDING.value
        await db.commit()
        return None

    async def _handle_booking_error(
        self,
        db: AsyncSession,
        lead: Lead | None,
        payload: MeasurementBookingRequest,
        contact: QuizContact,
        address: str,
        analytics_base: dict[str, Any],
        error: str,
    ) -> None:
        logger.warning("Measurement calendar booking failed: lead_id=%s start=%s error=%s", getattr(lead, "id", None), payload.start, error, exc_info=True)
        await self._mark_requested(db, lead, payload.start, address, contact.phone, {"booking_error": error[:500]})
        await self._record_event(db, payload.session_token, "measurement_booking_failed", {**analytics_base, "start": payload.start, "error": error[:500]})

    async def _handle_missing_booking_uid(
        self,
        db: AsyncSession,
        lead: Lead | None,
        payload: MeasurementBookingRequest,
        contact: QuizContact,
        address: str,
        analytics_base: dict[str, Any],
        booking: dict[str, Any],
    ) -> None:
        logger.warning("Measurement calendar booking returned without uid: lead_id=%s start=%s response=%s", getattr(lead, "id", None), payload.start, json.dumps(booking, ensure_ascii=False)[:1000])
        await self._mark_requested(db, lead, payload.start, address, contact.phone, {"booking_error": "cal_booking_uid_missing", "booking_response": booking})
        await self._record_event(db, payload.session_token, "measurement_booking_uid_missing", {**analytics_base, "start": payload.start})

    async def _complete_booking(
        self,
        db: AsyncSession,
        lead: Lead | None,
        payload: MeasurementBookingRequest,
        contact: QuizContact,
        address: str,
        booking: dict[str, Any],
        booking_uid: str,
    ) -> None:
        logger.info("Measurement calendar booking succeeded: lead_id=%s start=%s booking_uid=%s", getattr(lead, "id", None), payload.start, booking_uid)
        if not lead:
            return
        data = self._parse_extracted_data(lead.extracted_data)
        self._sync_measurement_address(data, address)
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        measurement.update(
            {
                "start": payload.start,
                "status": "booked",
                "address": address,
                "phone": contact.phone,
                "booking_uid": booking_uid,
                "booking": booking.get("data") or booking,
                "booked_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.status = LeadStatus.MEASUREMENT_BOOKED.value
        await db.commit()
        await self.enqueue_measurement_reminder(db, lead, payload.start, address, booking_uid)
        await self.notify_measurement_telegram(db, lead, payload.start, address, "booked", booking_uid)
        await self._notify_hot_lead(db, lead, "Клиент записался на замер", "measurement_booking")

    async def _mark_requested(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        phone: str | None,
        extra: dict[str, Any],
    ) -> None:
        if not lead:
            return
        data = self._parse_extracted_data(lead.extracted_data)
        self._sync_measurement_address(data, address)
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        measurement.update({"start": start, "status": "requested", "address": address, "phone": phone, **extra})
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        if lead.status in self.AUTO_QUIZ_STATUSES:
            lead.status = LeadStatus.MEASUREMENT_PENDING.value
        await db.commit()

    async def _notify_hot_lead(self, db: AsyncSession, lead: Lead, reason: str, source: str) -> None:
        try:
            from src.services.lead_manager_notification_service import lead_manager_notification_service

            await lead_manager_notification_service.notify_hot_lead_if_needed(db=db, lead=lead, reason=reason, source=source)
        except Exception:
            logger.warning("Failed to notify hot lead after measurement booking: lead_id=%s", lead.id, exc_info=True)

    async def _record_event(self, db: AsyncSession, session_token: str, event_type: str, data: dict[str, Any]) -> None:
        await analytics_service.record_event(db=db, session_token=session_token, event_type=event_type, step_id="measurement", event_data=data)

    def _analytics_base(
        self,
        lead_id: uuid.UUID | None,
        metadata: dict[str, Any],
        source: str,
        selected_messenger: str | None,
        has_address: bool,
    ) -> dict[str, Any]:
        return {
            "lead_id": str(lead_id) if lead_id else None,
            "source": source,
            "booking_source": "messenger" if selected_messenger else "quiz",
            "messenger": selected_messenger,
            "selected_messenger": selected_messenger,
            "selected_slot_label": metadata.get("selected_slot_label"),
            "previous_start": metadata.get("previous_start"),
            "previous_booking_uid": metadata.get("previous_booking_uid"),
            "has_address": has_address,
        }

    def _parse_extracted_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _sync_measurement_address(self, data: dict[str, Any], address: str) -> None:
        clean_address = str(address or "").strip()
        if not clean_address:
            return
        data["address"] = clean_address
        data["measurement_address"] = clean_address
        if isinstance(data.get("quiz"), dict):
            data["quiz"]["address"] = clean_address


measurement_booking_service = MeasurementBookingService()
