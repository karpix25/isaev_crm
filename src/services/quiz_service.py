from datetime import datetime, timedelta, timezone
from typing import Any
import json
import logging
import re
import uuid

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import ChatMessage, FunnelSession, Lead, LeadStatus
from src.models.funnel import FunnelEvent
from src.schemas.analytics import FunnelSessionCreate
from src.schemas.quiz import QuizContactCaptureRequest, QuizSubmitRequest, MeasurementBookingRequest
from src.services.analytics_service import analytics_service
from src.services.cal_pro_service import cal_pro_service
from src.services.lead_manager_notification_service import lead_manager_notification_service
from src.services.quiz_lead_deduplication_service import QuizLeadUpsertResult, quiz_lead_deduplication_service
from src.services.quiz_hot_lead_service import quiz_hot_lead_service
from src.services.quiz_value_normalizer import normalize_quiz_design_answer

class QuizService:
    SESSION_TOKEN_RE = re.compile(r"\b(qz_[A-Za-z0-9_-]{12,})\b")

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

        lead_result = await self._create_or_update_lead(db, org_id, payload, session_lead_id=session.lead_id)
        lead = lead_result.lead

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
            event_type="lead_created" if lead_result.created else "lead_updated",
            step_id="crm",
            event_data={"lead_id": str(lead.id), "deduplicated": not lead_result.created},
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
        await self._notify_quiz_hot_lead_if_needed(db=db, lead=lead, payload=payload)

        slots = []
        if self.should_offer_measurement(payload.answers) and not payload.contact.preferred_messenger:
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
        lead_result = await self._create_or_update_lead(
            db,
            org_id,
            submit_payload,
            session_lead_id=session.lead_id,
        )
        lead = lead_result.lead

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
            event_type="lead_created" if lead_result.created else "lead_updated",
            step_id="crm",
            event_data={
                "lead_id": str(lead.id),
                "capture_type": "exit_or_pause",
                "deduplicated": not lead_result.created,
            },
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

        from src.services.measurement_booking_service import measurement_booking_service

        return await measurement_booking_service.book_from_quiz_payload(db=db, payload=payload, session=session)

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
            event_type="messenger_message_received",
            step_id="messenger",
            event_data={
                "lead_id": str(lead.id),
                "messenger": "telegram",
                "first_message": True,
            },
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
            event_type="messenger_message_received",
            step_id="messenger",
            event_data={
                "lead_id": str(lead.id),
                "messenger": "whatsapp",
                "first_message": True,
            },
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
        from src.services.measurement_booking_service import measurement_booking_service

        return measurement_booking_service.extract_booking_uid(booking)

    def _format_measurement_start(self, value: str) -> str:
        from src.services.measurement_booking_service import measurement_booking_service

        return measurement_booking_service.format_measurement_start(value)

    async def _notify_measurement_telegram(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        status: str,
        booking_uid: str | None,
    ) -> None:
        from src.services.measurement_booking_service import measurement_booking_service

        await measurement_booking_service.notify_measurement_telegram(
            db=db,
            lead=lead,
            start=start,
            address=address,
            status=status,
            booking_uid=booking_uid,
        )

    async def _enqueue_measurement_reminder(
        self,
        db: AsyncSession,
        lead: Lead | None,
        start: str,
        address: str,
        booking_uid: str | None,
    ) -> None:
        from src.services.measurement_booking_service import measurement_booking_service

        await measurement_booking_service.enqueue_measurement_reminder(
            db=db,
            lead=lead,
            start=start,
            address=address,
            booking_uid=booking_uid,
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
    ) -> QuizLeadUpsertResult:
        hot_lead_decision = quiz_hot_lead_service.evaluate(payload.answers)
        extracted = {
            "quiz": {
                "answers": payload.answers,
                "price": payload.price.model_dump() if payload.price else None,
                "design_project_file_url": payload.design_project_file_url,
                "preferred_messenger": payload.contact.preferred_messenger,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
                "hot_lead": hot_lead_decision.as_dict(),
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

        return await quiz_lead_deduplication_service.create_or_update(
            db=db,
            org_id=org_id,
            payload=payload,
            extracted_payload=extracted,
            derived_status=self._derive_quiz_status(payload),
            session_lead_id=session_lead_id,
        )

    async def _notify_quiz_hot_lead_if_needed(
        self,
        db: AsyncSession,
        lead: Lead,
        payload: QuizSubmitRequest,
    ) -> None:
        metadata = payload.metadata or {}
        if metadata.get("quiz_completed") is False:
            return

        decision = quiz_hot_lead_service.evaluate(payload.answers)
        if not decision.is_hot:
            return

        await lead_manager_notification_service.notify_hot_lead_if_needed(
            db=db,
            lead=lead,
            reason=decision.reason,
            source="quiz_answers",
            extracted_data={
                "is_hot_lead": True,
                "hot_lead_reason": decision.reason,
                "hot_lead_rules": list(decision.matched_rules),
            },
        )

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
