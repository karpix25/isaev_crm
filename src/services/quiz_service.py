from datetime import datetime, timedelta, timezone
from typing import Any
import json
import logging
import re
import uuid
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ChatMessage, FunnelSession, Lead, LeadStatus
from src.models.funnel import FunnelEvent
from src.schemas.analytics import FunnelSessionCreate
from src.schemas.quiz import QuizContact, QuizContactCaptureRequest, QuizSubmitRequest, MeasurementBookingRequest
from src.services.analytics_service import analytics_service
from src.services.cal_pro_service import cal_pro_service
from src.services.lead_service import lead_service
from src.services.quiz_value_normalizer import normalize_quiz_design_answer

logger = logging.getLogger(__name__)


class QuizService:
    SESSION_TOKEN_RE = re.compile(r"\b(qz_[A-Za-z0-9_-]{12,})\b")
    AUTO_QUIZ_STATUSES = {
        LeadStatus.NEW.value,
        LeadStatus.QUIZ_COMPLETED.value,
        LeadStatus.MESSENGER_PENDING.value,
        LeadStatus.DESIGN_PENDING.value,
        LeadStatus.DESIGN_REVIEW.value,
        LeadStatus.MEASUREMENT_PENDING.value,
    }

    async def submit_quiz(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizSubmitRequest,
    ) -> tuple[Lead, str, list]:
        session_token = payload.session_token
        if session_token:
            session = await self._get_session(db, session_token)
        else:
            session = None

        if not session:
            session_data = FunnelSessionCreate(
                funnel_name="renovation_quiz",
                channel=payload.channel,
                source=payload.source,
                utm_source=payload.utm_source,
                utm_medium=payload.utm_medium,
                utm_campaign=payload.utm_campaign,
                utm_content=payload.utm_content,
                utm_term=payload.utm_term,
                entry_url=payload.entry_url,
                referrer=payload.referrer,
                metadata=payload.metadata,
            )
            session = await analytics_service.create_session(db=db, org_id=org_id, data=session_data)
            session_token = session.session_token

        lead = await self._create_or_update_lead(db, org_id, payload, session_lead_id=session.lead_id)

        session.lead_id = lead.id
        session.status = "completed"
        session.completed_at = datetime.now(timezone.utc)
        session.last_event_at = session.completed_at
        await db.commit()

        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="contact_submitted",
            step_id="contact",
            event_data={
                "name": payload.contact.name,
                "preferred_messenger": payload.contact.preferred_messenger,
            },
        )
        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="lead_created",
            step_id="crm",
            event_data={"lead_id": str(lead.id)},
        )
        if payload.design_project_file_url:
            await analytics_service.record_event(
                db=db,
                session_token=session_token,
                event_type="design_file_uploaded",
                step_id="design",
                event_data={"url": payload.design_project_file_url},
            )
        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="quiz_completed",
            step_id="complete",
            event_data={"lead_id": str(lead.id)},
        )

        slots = []
        if self.should_offer_measurement(payload.answers):
            slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
        return lead, session_token, slots

    async def capture_contact(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizContactCaptureRequest,
    ) -> tuple[Lead, str]:
        session_token = payload.session_token
        session = await self._get_session(db, session_token) if session_token else None

        if not session:
            session_data = FunnelSessionCreate(
                funnel_name="renovation_quiz",
                channel=payload.channel,
                source=payload.source,
                utm_source=payload.utm_source,
                utm_medium=payload.utm_medium,
                utm_campaign=payload.utm_campaign,
                utm_content=payload.utm_content,
                utm_term=payload.utm_term,
                entry_url=payload.entry_url,
                referrer=payload.referrer,
                metadata=payload.metadata,
            )
            session = await analytics_service.create_session(db=db, org_id=org_id, data=session_data)
            session_token = session.session_token

        submit_payload = QuizSubmitRequest(
            session_token=session_token,
            contact=payload.contact,
            answers=payload.answers,
            source=payload.source,
            channel=payload.channel,
            entry_url=payload.entry_url,
            referrer=payload.referrer,
            utm_source=payload.utm_source,
            utm_medium=payload.utm_medium,
            utm_campaign=payload.utm_campaign,
            utm_content=payload.utm_content,
            utm_term=payload.utm_term,
            metadata={
                **(payload.metadata or {}),
                "capture_type": "exit_or_pause",
                "quiz_completed": False,
            },
        )
        lead = await self._create_or_update_lead(db, org_id, submit_payload, session_lead_id=session.lead_id)

        session.lead_id = lead.id
        session.last_event_at = datetime.now(timezone.utc)
        await db.commit()

        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="contact_submitted",
            step_id="exit_capture",
            event_data={
                "name": payload.contact.name,
                "capture_type": "exit_or_pause",
                "preferred_messenger": payload.contact.preferred_messenger,
            },
        )
        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="lead_created",
            step_id="crm",
            event_data={"lead_id": str(lead.id), "capture_type": "exit_or_pause"},
        )
        await self._enqueue_abandoned_telegram_followup(db=db, session=session, lead=lead)
        return lead, session_token

    async def book_measurement(
        self,
        db: AsyncSession,
        payload: MeasurementBookingRequest,
    ) -> tuple[dict[str, Any], uuid.UUID | None]:
        session = await self._get_session(db, payload.session_token)
        if not session:
            raise ValueError("Funnel session not found")

        lead_id = payload.lead_id or session.lead_id
        contact = payload.contact
        if not contact and lead_id:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead and lead.full_name:
                contact = QuizContact(name=lead.full_name, phone=lead.phone)
        if not contact:
            raise ValueError("Booking contact is required")
        metadata = payload.metadata or {}
        measurement_address = (payload.address or metadata.get("measurement_address") or "").strip()
        if not measurement_address:
            raise ValueError("Measurement address is required")
        booking_source = str(metadata.get("source") or "quiz_inline_slots")
        selected_messenger = str(metadata.get("selected_messenger") or "").strip() or None
        analytics_base = {
            "lead_id": str(lead_id) if lead_id else None,
            "source": booking_source,
            "booking_source": "messenger" if selected_messenger else "quiz",
            "messenger": selected_messenger,
            "selected_messenger": selected_messenger,
            "selected_slot_label": metadata.get("selected_slot_label"),
            "previous_start": metadata.get("previous_start"),
            "previous_booking_uid": metadata.get("previous_booking_uid"),
            "has_address": bool(measurement_address),
        }

        logger.info(
            "Measurement booking requested: lead_id=%s start=%s address_present=%s contact_phone_present=%s",
            lead_id,
            payload.start,
            bool(measurement_address),
            bool(getattr(contact, "phone", None)),
        )

        lead = None
        data: dict[str, Any] = {}
        if lead_id:
            result = await db.execute(select(Lead).where(Lead.id == lead_id))
            lead = result.scalar_one_or_none()
            if lead:
                data = self._parse_extracted_data(lead.extracted_data)
                self._sync_measurement_address(data, measurement_address)
                measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
                if measurement.get("booking_uid") and measurement.get("start") == payload.start:
                    return measurement.get("booking") or {"status": "ok", "data": measurement}, lead_id

                data["measurement"] = {
                    **measurement,
                    "start": payload.start,
                    "status": "requested",
                    "requested_at": datetime.now(timezone.utc).isoformat(),
                    "address": measurement_address,
                    "phone": contact.phone,
                    "selected_slot_label": metadata.get("selected_slot_label"),
                    "source": booking_source,
                }
                lead.extracted_data = json.dumps(data, ensure_ascii=False)
                if lead.status in self.AUTO_QUIZ_STATUSES:
                    lead.status = LeadStatus.MEASUREMENT_PENDING.value
                await db.commit()

        await analytics_service.record_event(
            db=db,
            session_token=payload.session_token,
            event_type="measurement_booking_requested",
            step_id="measurement",
            event_data={
                **analytics_base,
                "start": payload.start,
            },
        )

        booking_metadata = {
            "lead_id": str(lead_id) if lead_id else None,
            "session_token": payload.session_token,
            "client_name": contact.name,
            "client_phone": contact.phone,
            "measurement_address": measurement_address,
            **metadata,
        }
        try:
            booking = await cal_pro_service.create_booking(
                start=payload.start,
                contact=contact,
                answers=payload.answers,
                metadata=booking_metadata,
            )
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning(
                "Measurement calendar booking failed: lead_id=%s start=%s error=%s",
                lead_id,
                payload.start,
                exc,
                exc_info=True,
            )
            if lead:
                data = self._parse_extracted_data(lead.extracted_data)
                self._sync_measurement_address(data, measurement_address)
                measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
                measurement.update(
                    {
                        "start": payload.start,
                        "status": "requested",
                        "address": measurement_address,
                        "phone": contact.phone,
                        "booking_error": str(exc)[:500],
                    }
                )
                data["measurement"] = measurement
                lead.extracted_data = json.dumps(data, ensure_ascii=False)
                if lead.status in self.AUTO_QUIZ_STATUSES:
                    lead.status = LeadStatus.MEASUREMENT_PENDING.value
                await db.commit()
            await analytics_service.record_event(
                db=db,
                session_token=payload.session_token,
                event_type="measurement_booking_failed",
                step_id="measurement",
                event_data={
                    **analytics_base,
                    "start": payload.start,
                    "error": str(exc)[:500],
                },
            )
            return {
                "status": "requested",
                "reason": "calendar_booking_failed",
                "start": payload.start,
                "message": "Measurement request saved, but calendar booking failed.",
            }, lead_id

        booking_uid = self.extract_booking_uid(booking)
        if not booking_uid:
            logger.warning(
                "Measurement calendar booking returned without uid: lead_id=%s start=%s response=%s",
                lead_id,
                payload.start,
                json.dumps(booking, ensure_ascii=False)[:1000],
            )
            if lead:
                data = self._parse_extracted_data(lead.extracted_data)
                self._sync_measurement_address(data, measurement_address)
                measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
                measurement.update(
                    {
                        "start": payload.start,
                        "status": "requested",
                        "address": measurement_address,
                        "phone": contact.phone,
                        "booking_error": "cal_booking_uid_missing",
                        "booking_response": booking,
                    }
                )
                data["measurement"] = measurement
                lead.extracted_data = json.dumps(data, ensure_ascii=False)
                if lead.status in self.AUTO_QUIZ_STATUSES:
                    lead.status = LeadStatus.MEASUREMENT_PENDING.value
                await db.commit()
            await analytics_service.record_event(
                db=db,
                session_token=payload.session_token,
                event_type="measurement_booking_uid_missing",
                step_id="measurement",
                event_data={
                    **analytics_base,
                    "start": payload.start,
                },
            )
            return {
                "status": "requested",
                "reason": "calendar_booking_uid_missing",
                "start": payload.start,
                "message": "Measurement request saved, but calendar booking was not confirmed.",
            }, lead_id

        logger.info(
            "Measurement calendar booking succeeded: lead_id=%s start=%s booking_uid=%s",
            lead_id,
            payload.start,
            booking_uid,
        )
        if lead:
            data = self._parse_extracted_data(lead.extracted_data)
            self._sync_measurement_address(data, measurement_address)
            measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
            measurement.update(
                {
                    "start": payload.start,
                    "status": "booked",
                    "address": measurement_address,
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
            await self._enqueue_measurement_reminder(
                db=db,
                lead=lead,
                start=payload.start,
                address=measurement_address,
                booking_uid=booking_uid,
            )

        await analytics_service.record_event(
            db=db,
            session_token=payload.session_token,
            event_type="measurement_booked",
            step_id="measurement",
            event_data={
                **analytics_base,
                "start": payload.start,
                "booking_uid": booking_uid,
            },
        )

        return booking, lead_id

    async def record_design_upload(
        self,
        db: AsyncSession,
        session_token: str,
        url: str,
        filename: str | None = None,
    ) -> None:
        session = await self._get_session(db, session_token)
        if not session:
            raise ValueError("Funnel session not found")

        await analytics_service.record_event(
            db=db,
            session_token=session_token,
            event_type="design_file_uploaded",
            step_id="design",
            event_data={"url": url, "filename": filename},
        )

        if session.lead_id:
            result = await db.execute(select(Lead).where(Lead.id == session.lead_id))
            lead = result.scalar_one_or_none()
            if lead:
                from src.services.estimate_request_service import estimate_request_service

                await estimate_request_service.register_file(
                    db=db,
                    lead=lead,
                    url=url,
                    filename=filename,
                    source="quiz_design_project",
                )

    def extract_session_token(self, text: str | None) -> str | None:
        if not text:
            return None
        match = self.SESSION_TOKEN_RE.search(text)
        return match.group(1) if match else None

    async def link_telegram_message(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        text: str | None,
        telegram_id: int,
        full_name: str | None = None,
        username: str | None = None,
    ) -> Lead | None:
        token = self.extract_session_token(text)
        if not token:
            return None

        session = await self._get_session(db, token)
        if not session or session.org_id != org_id:
            return None

        result = await db.execute(
            select(Lead).where(Lead.org_id == org_id, Lead.telegram_id == telegram_id)
        )
        telegram_lead = result.scalar_one_or_none()

        quiz_lead = None
        if session.lead_id:
            result = await db.execute(select(Lead).where(Lead.id == session.lead_id))
            quiz_lead = result.scalar_one_or_none()

        if quiz_lead:
            lead = quiz_lead
            if telegram_lead and telegram_lead.id != quiz_lead.id:
                await db.execute(
                    update(ChatMessage)
                    .where(ChatMessage.lead_id == telegram_lead.id)
                    .values(lead_id=quiz_lead.id)
                )
                if telegram_lead.last_message_at and (
                    not quiz_lead.last_message_at or telegram_lead.last_message_at > quiz_lead.last_message_at
                ):
                    quiz_lead.last_message_at = telegram_lead.last_message_at
                quiz_lead.unread_count = (quiz_lead.unread_count or 0) + (telegram_lead.unread_count or 0)
                telegram_lead.telegram_id = None
                telegram_lead.telegram_lookup_status = "not_checked"
                telegram_lead.telegram_lookup_error = "merged_into_quiz_lead"
                self._merge_quiz_data(source=telegram_lead, target=quiz_lead, overwrite_quiz=False)
                await db.flush()
        elif telegram_lead:
            lead = telegram_lead
        else:
            lead = Lead(
                org_id=org_id,
                telegram_id=telegram_id,
                full_name=full_name,
                username=self._clean_username(username),
                status=LeadStatus.NEW.value,
                source="quiz_telegram",
                telegram_lookup_status="active",
            )
            db.add(lead)
            await db.flush()

        lead.telegram_id = telegram_id
        lead.full_name = full_name or lead.full_name
        lead.username = self._clean_username(username) or lead.username
        lead.telegram_lookup_status = "active"
        lead.telegram_lookup_checked_at = datetime.now(timezone.utc)
        if not lead.source or lead.source in {"quiz", "quiz_exit_capture"}:
            lead.source = "quiz_telegram"

        data = self._parse_extracted_data(lead.extracted_data)
        data.setdefault("messengers", {})["telegram"] = True
        data["quiz_session_token"] = token
        data["telegram_chat"] = {
            "telegram_id": telegram_id,
            "username": self._clean_username(username),
            "linked_at": datetime.now(timezone.utc).isoformat(),
        }
        lead.extracted_data = json.dumps(data, ensure_ascii=False)

        session.lead_id = lead.id
        session.last_event_at = datetime.now(timezone.utc)
        await db.execute(
            update(FunnelEvent)
            .where(FunnelEvent.session_id == session.id)
            .values(lead_id=lead.id)
        )
        await db.commit()
        await db.refresh(lead)

        await analytics_service.record_event(
            db=db,
            session_token=token,
            event_type="telegram_message_received",
            step_id="messenger",
            event_data={"lead_id": str(lead.id), "telegram_id": telegram_id},
        )
        await analytics_service.record_event(
            db=db,
            session_token=token,
            event_type="telegram_linked",
            step_id="messenger",
            event_data={"lead_id": str(lead.id), "telegram_id": telegram_id},
        )
        return lead

    async def link_telegram_identity(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        telegram_id: int,
        full_name: str | None = None,
        username: str | None = None,
    ) -> Lead | None:
        result = await db.execute(
            select(Lead).where(Lead.org_id == org_id, Lead.telegram_id == telegram_id)
        )
        existing = result.scalar_one_or_none()

        normalized_name = (full_name or "").strip().casefold()
        normalized_username = self._clean_username(username)
        result = await db.execute(
            select(Lead)
            .where(
                Lead.org_id == org_id,
                Lead.telegram_id.is_(None),
                Lead.source.in_(["quiz", "quiz_exit_capture", "quiz_telegram"]),
            )
            .order_by(Lead.created_at.desc())
            .limit(25)
        )
        for lead in result.scalars().all():
            data = self._parse_extracted_data(lead.extracted_data)
            quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
            messengers = data.get("messengers") if isinstance(data.get("messengers"), dict) else {}
            preferred = str(quiz.get("preferred_messenger") or "").lower()
            if preferred != "telegram" and not messengers.get("telegram"):
                continue

            lead_name = (lead.full_name or "").strip().casefold()
            lead_username = self._clean_username(lead.username)
            name_matches = bool(normalized_name and lead_name and normalized_name == lead_name)
            username_matches = bool(normalized_username and lead_username and normalized_username == lead_username)
            if not name_matches and not username_matches:
                continue

            if existing and existing.id != lead.id:
                await db.execute(
                    update(ChatMessage)
                    .where(ChatMessage.lead_id == existing.id)
                    .values(lead_id=lead.id)
                )
                if existing.last_message_at and (
                    not lead.last_message_at or existing.last_message_at > lead.last_message_at
                ):
                    lead.last_message_at = existing.last_message_at
                lead.unread_count = (lead.unread_count or 0) + (existing.unread_count or 0)
                existing.telegram_id = None
                existing.telegram_lookup_status = "not_checked"

            lead.telegram_id = telegram_id
            lead.full_name = full_name or lead.full_name
            lead.username = normalized_username or lead.username
            lead.telegram_lookup_status = "active"
            lead.telegram_lookup_checked_at = datetime.now(timezone.utc)
            data.setdefault("messengers", {})["telegram"] = True
            data["telegram_chat"] = {
                "telegram_id": telegram_id,
                "username": normalized_username,
                "linked_at": datetime.now(timezone.utc).isoformat(),
                "link_method": "identity_match",
            }
            lead.extracted_data = json.dumps(data, ensure_ascii=False)

            token = data.get("quiz_session_token")
            if token:
                session = await self._get_session(db, token)
                if session:
                    session.lead_id = lead.id
                    session.last_event_at = datetime.now(timezone.utc)

            await db.commit()
            await db.refresh(lead)
            return lead

        return existing

    async def link_whatsapp_message(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        text: str | None,
        chat_id: str,
        sender_name: str | None = None,
    ) -> Lead | None:
        token = self.extract_session_token(text)
        if not token:
            return None

        session = await self._get_session(db, token)
        if not session or session.org_id != org_id:
            return None

        normalized_phone = None
        try:
            from src.services.wazzup_service import wazzup_service
            normalized_phone = wazzup_service.normalize_phone(chat_id)
        except Exception:
            normalized_phone = chat_id

        result = await db.execute(
            select(Lead).where(Lead.org_id == org_id, Lead.phone == normalized_phone)
        )
        whatsapp_lead = result.scalar_one_or_none() if normalized_phone else None

        quiz_lead = None
        if session.lead_id:
            result = await db.execute(select(Lead).where(Lead.id == session.lead_id))
            quiz_lead = result.scalar_one_or_none()

        if quiz_lead and (not whatsapp_lead or whatsapp_lead.id == quiz_lead.id):
            lead = quiz_lead
        elif whatsapp_lead:
            lead = whatsapp_lead
            if quiz_lead and quiz_lead.id != whatsapp_lead.id:
                self._merge_quiz_data(source=quiz_lead, target=lead)
        else:
            lead = Lead(
                org_id=org_id,
                full_name=(sender_name or "").strip() or None,
                phone=normalized_phone,
                status=LeadStatus.NEW.value,
                source="quiz_whatsapp",
                telegram_lookup_status="not_checked",
            )
            db.add(lead)
            await db.flush()

        lead.full_name = (sender_name or "").strip() or lead.full_name
        if normalized_phone:
            lead.phone = normalized_phone
        if not lead.source or lead.source in {"quiz", "quiz_exit_capture"}:
            lead.source = "quiz_whatsapp"

        data = self._parse_extracted_data(lead.extracted_data)
        data.setdefault("messengers", {})["whatsapp"] = True
        data["quiz_session_token"] = token
        data["whatsapp_chat"] = {
            "chat_id": chat_id,
            "linked_at": datetime.now(timezone.utc).isoformat(),
        }
        lead.extracted_data = json.dumps(data, ensure_ascii=False)

        session.lead_id = lead.id
        session.last_event_at = datetime.now(timezone.utc)
        await db.execute(
            update(FunnelEvent)
            .where(FunnelEvent.session_id == session.id)
            .values(lead_id=lead.id)
        )
        await db.commit()
        await db.refresh(lead)

        await analytics_service.record_event(
            db=db,
            session_token=token,
            event_type="whatsapp_message_received",
            step_id="messenger",
            event_data={"lead_id": str(lead.id), "chat_id": chat_id},
        )
        await analytics_service.record_event(
            db=db,
            session_token=token,
            event_type="whatsapp_linked",
            step_id="messenger",
            event_data={"lead_id": str(lead.id), "chat_id": chat_id},
        )
        return lead

    def should_offer_measurement(self, answers: dict[str, Any]) -> bool:
        return bool(answers)

    def extract_booking_uid(self, booking: dict[str, Any]) -> str | None:
        data = booking.get("data") if isinstance(booking, dict) else None
        source = data if isinstance(data, dict) else booking
        value = source.get("uid") or source.get("id") or source.get("bookingUid")
        return str(value) if value else None

    def _format_measurement_start(self, value: str) -> str:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            local_dt = dt.astimezone(ZoneInfo("Europe/Moscow"))
            return local_dt.strftime("%d.%m.%Y в %H:%M")
        except Exception:
            return value

    async def _notify_measurement_telegram(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        status: str,
        booking_uid: str | None,
    ) -> None:
        if not lead:
            return
        try:
            from src.services.telegram_notification_service import telegram_notification_service

            if not telegram_notification_service.has_recipients("measurement"):
                logger.warning(
                    "Skipping measurement Telegram notification: no manager recipients lead_id=%s",
                    getattr(lead, "id", None),
                )
                return

            status_label = "✅ Замер записан в календарь" if status == "booked" else "🟡 Клиент выбрал слот замера"
            text = (
                f"{status_label}\n\n"
                f"👤 Клиент: {lead.full_name or 'Клиент квиза'}\n"
                f"📞 Телефон: {lead.phone or 'не указан'}\n"
                f"📅 Дата: {self._format_measurement_start(start)}\n"
                f"📍 Адрес: {address}\n"
                f"🆔 Лид: {lead.id}"
            )
            if booking_uid:
                text += f"\n🔖 Booking: {booking_uid}"
            sent = await telegram_notification_service.send_to_managers(text, topic="measurement")
            logger.info(
                "Measurement Telegram notification sent: recipients=%s lead_id=%s status=%s",
                sent,
                lead.id,
                status,
            )
        except Exception:
            logger.warning(
                "Failed to send measurement Telegram notification for lead %s",
                getattr(lead, "id", None),
                exc_info=True,
            )

    async def _enqueue_measurement_reminder(
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
            run_at = start_dt.astimezone(timezone.utc) - timedelta(hours=24)
            min_run_at = datetime.now(timezone.utc) + timedelta(minutes=5)
            if run_at < min_run_at:
                run_at = min_run_at

            from src.services.background_job_service import background_job_service

            await background_job_service.enqueue(
                db=db,
                job_type="measurement_telegram_reminder",
                payload={
                    "lead_id": str(lead.id),
                    "start": start,
                    "address": address,
                    "booking_uid": booking_uid,
                },
                max_attempts=2,
                run_at=run_at,
            )
            logger.info(
                "Measurement Telegram reminder enqueued: lead_id=%s run_at=%s booking_uid=%s",
                lead.id,
                run_at.isoformat(),
                booking_uid,
            )
        except Exception:
            logger.warning(
                "Failed to enqueue measurement reminder for lead %s",
                getattr(lead, "id", None),
                exc_info=True,
            )

    async def _get_session(self, db: AsyncSession, session_token: str) -> FunnelSession | None:
        result = await db.execute(select(FunnelSession).where(FunnelSession.session_token == session_token))
        return result.scalar_one_or_none()

    async def _create_or_update_lead(
        self,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizSubmitRequest,
        session_lead_id: uuid.UUID | None = None,
    ) -> Lead:
        phone = payload.contact.phone.strip() if payload.contact.phone else None
        lead = None
        if payload.lead_id:
            result = await db.execute(select(Lead).where(Lead.org_id == org_id, Lead.id == payload.lead_id))
            lead = result.scalar_one_or_none()
        if not lead and session_lead_id:
            result = await db.execute(select(Lead).where(Lead.org_id == org_id, Lead.id == session_lead_id))
            lead = result.scalar_one_or_none()
        if not lead and payload.session_token:
            result = await db.execute(
                select(Lead)
                .where(
                    Lead.org_id == org_id,
                    Lead.extracted_data.is_not(None),
                    Lead.extracted_data.contains(payload.session_token),
                )
                .order_by(Lead.created_at.desc())
                .limit(1)
            )
            lead = result.scalar_one_or_none()
        if not lead and payload.telegram_id:
            result = await db.execute(select(Lead).where(Lead.org_id == org_id, Lead.telegram_id == payload.telegram_id))
            lead = result.scalar_one_or_none()
        if phone:
            result = await db.execute(select(Lead).where(Lead.org_id == org_id, Lead.phone == phone))
            lead = lead or result.scalar_one_or_none()

        extracted = {
            "quiz": {
                "answers": payload.answers,
                "price": payload.price.model_dump() if payload.price else None,
                "design_project_file_url": payload.design_project_file_url,
                "preferred_messenger": payload.contact.preferred_messenger,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            },
            "messengers": {
                payload.contact.preferred_messenger: True,
            } if payload.contact.preferred_messenger else {},
            "utm": {
                "source": payload.utm_source,
                "medium": payload.utm_medium,
                "campaign": payload.utm_campaign,
                "content": payload.utm_content,
                "term": payload.utm_term,
            },
            "metadata": payload.metadata or {},
        }
        if payload.session_token:
            extracted["quiz_session_token"] = payload.session_token

        if lead:
            data = self._parse_extracted_data(lead.extracted_data)
            self._merge_extracted_payload(data, extracted)
            lead.full_name = payload.contact.name or lead.full_name
            if phone:
                lead.phone = phone
            lead.username = self._clean_username(payload.contact.telegram_username) or lead.username
            if payload.telegram_id and not lead.telegram_id:
                lead.telegram_id = payload.telegram_id
            lead.source = lead.source or payload.source or "quiz"
            derived_status = self._derive_quiz_status(payload)
            if lead.status in self.AUTO_QUIZ_STATUSES:
                lead.status = derived_status.value
            lead.extracted_data = json.dumps(data, ensure_ascii=False)
            await db.commit()
            await db.refresh(lead)
            return lead

        lead = await lead_service.create_manual_lead(
            db=db,
            org_id=org_id,
            full_name=payload.contact.name,
            phone=phone,
            username=payload.contact.telegram_username,
            source=payload.source or "quiz",
        )
        data = self._parse_extracted_data(lead.extracted_data)
        self._merge_extracted_payload(data, extracted)
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.status = self._derive_quiz_status(payload).value
        await db.commit()
        await db.refresh(lead)
        return lead

    def _derive_quiz_status(self, payload: QuizSubmitRequest) -> LeadStatus:
        metadata = payload.metadata or {}
        if metadata.get("quiz_completed") is False:
            return LeadStatus.NEW

        design_answer = normalize_quiz_design_answer(payload.answers.get("design"))
        if payload.design_project_file_url:
            return LeadStatus.DESIGN_REVIEW
        if design_answer in {"yes", "wip"}:
            return LeadStatus.DESIGN_PENDING
        if design_answer in {"no", "", "none"}:
            return LeadStatus.MEASUREMENT_PENDING
        return LeadStatus.QUIZ_COMPLETED

    def _parse_extracted_data(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def _merge_extracted_payload(self, target: dict[str, Any], payload: dict[str, Any]) -> None:
        messengers = payload.get("messengers")
        for key, value in payload.items():
            if key == "messengers":
                continue
            target[key] = value
        if isinstance(messengers, dict) and messengers:
            target["messengers"] = {
                **(target.get("messengers") or {}),
                **messengers,
            }

    def _sync_measurement_address(self, data: dict[str, Any], address: str) -> None:
        clean_address = str(address or "").strip()
        if not clean_address:
            return
        data["address"] = clean_address
        data["measurement_address"] = clean_address
        if isinstance(data.get("quiz"), dict):
            data["quiz"]["address"] = clean_address

    async def _enqueue_abandoned_telegram_followup(
        self,
        db: AsyncSession,
        session: FunnelSession,
        lead: Lead,
    ) -> None:
        if not lead.telegram_id:
            return
        try:
            from src.config import settings

            if not settings.quiz_abandoned_telegram_followup_enabled:
                return

            from src.services.background_job_service import background_job_service

            delay = max(1, int(settings.quiz_abandoned_telegram_followup_delay_minutes))
            await background_job_service.enqueue(
                db=db,
                job_type="quiz_abandoned_telegram_followup",
                payload={
                    "session_token": session.session_token,
                    "lead_id": str(lead.id),
                    "org_id": str(lead.org_id),
                },
                max_attempts=2,
                run_at=datetime.now(timezone.utc) + timedelta(minutes=delay),
            )
        except Exception:
            import logging

            logging.getLogger(__name__).warning(
                "Failed to enqueue abandoned quiz follow-up for lead %s",
                lead.id,
                exc_info=True,
            )

    def _clean_username(self, username: str | None) -> str | None:
        if not username:
            return None
        clean = username.strip()
        return clean[1:] if clean.startswith("@") else clean

    def _merge_quiz_data(self, source: Lead, target: Lead, overwrite_quiz: bool = True) -> None:
        source_data = self._parse_extracted_data(source.extracted_data)
        target_data = self._parse_extracted_data(target.extracted_data)
        if source_data.get("quiz") and (overwrite_quiz or not target_data.get("quiz")):
            target_data["quiz"] = source_data["quiz"]
        if source_data.get("messengers"):
            target_data["messengers"] = {
                **(target_data.get("messengers") or {}),
                **source_data["messengers"],
            }
        if source_data.get("quiz_session_token") and not target_data.get("quiz_session_token"):
            target_data["quiz_session_token"] = source_data["quiz_session_token"]
        if source_data.get("telegram_chat") and not target_data.get("telegram_chat"):
            target_data["telegram_chat"] = source_data["telegram_chat"]
        if source_data.get("whatsapp_chat") and not target_data.get("whatsapp_chat"):
            target_data["whatsapp_chat"] = source_data["whatsapp_chat"]
        if source_data.get("utm"):
            target_data["utm"] = source_data["utm"]
        if source_data.get("metadata"):
            target_data["metadata"] = {
                **(target_data.get("metadata") or {}),
                **source_data["metadata"],
            }
        target.extracted_data = json.dumps(target_data, ensure_ascii=False)
        target.full_name = target.full_name or source.full_name
        target.phone = target.phone or source.phone


quiz_service = QuizService()
