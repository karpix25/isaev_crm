"""Lead deduplication for quiz submissions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
import json
import re
import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import Lead, LeadStatus
from src.schemas.quiz import QuizSubmitRequest
from src.services.lead_service import lead_service


@dataclass
class QuizLeadUpsertResult:
    lead: Lead
    created: bool


class QuizLeadDeduplicationService:
    PHONE_DIGITS_RE = re.compile(r"\D+")
    TERMINAL_SKIP_STATUSES = {LeadStatus.SPAM.value}

    async def create_or_update(
        self,
        *,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizSubmitRequest,
        extracted_payload: dict[str, Any],
        derived_status: LeadStatus,
        session_lead_id: uuid.UUID | None = None,
    ) -> QuizLeadUpsertResult:
        phone = self.clean_phone(payload.contact.phone)
        lead = await self.find_existing_lead(
            db=db,
            org_id=org_id,
            payload=payload,
            phone=phone,
            session_lead_id=session_lead_id,
        )

        if lead:
            await self.update_lead_from_quiz(
                lead=lead,
                payload=payload,
                phone=phone,
                extracted_payload=extracted_payload,
                derived_status=derived_status,
            )
            await db.commit()
            await db.refresh(lead)
            return QuizLeadUpsertResult(lead=lead, created=False)

        lead = await self.create_lead_from_quiz(
            db=db,
            org_id=org_id,
            payload=payload,
            phone=phone,
            extracted_payload=extracted_payload,
            derived_status=derived_status,
        )
        await db.commit()
        await db.refresh(lead)
        return QuizLeadUpsertResult(lead=lead, created=True)

    async def find_existing_lead(
        self,
        *,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizSubmitRequest,
        phone: str | None,
        session_lead_id: uuid.UUID | None = None,
    ) -> Lead | None:
        for lead_id in (payload.lead_id, session_lead_id):
            if not lead_id:
                continue
            lead = await self._find_by_id(db=db, org_id=org_id, lead_id=lead_id)
            if lead:
                return lead

        if payload.session_token:
            lead = await self._find_by_session_token(db=db, org_id=org_id, session_token=payload.session_token)
            if lead:
                return lead

        if payload.telegram_id:
            lead = await self._find_by_telegram_id(db=db, org_id=org_id, telegram_id=payload.telegram_id)
            if lead:
                return lead

        if phone:
            return await self._find_by_phone(db=db, org_id=org_id, phone=phone)

        return None

    async def update_lead_from_quiz(
        self,
        *,
        lead: Lead,
        payload: QuizSubmitRequest,
        phone: str | None,
        extracted_payload: dict[str, Any],
        derived_status: LeadStatus,
    ) -> None:
        data = self.parse_extracted_data(lead.extracted_data)
        self.merge_extracted_payload(data, extracted_payload)
        lead.full_name = payload.contact.name or lead.full_name
        if phone:
            lead.phone = phone
        lead.username = self.clean_username(payload.contact.telegram_username) or lead.username
        if payload.telegram_id and not lead.telegram_id:
            lead.telegram_id = payload.telegram_id
        lead.source = lead.source or payload.source or "quiz"
        if lead.status in self.auto_quiz_statuses():
            lead.status = derived_status.value
        lead.extracted_data = json.dumps(data, ensure_ascii=False)

    async def create_lead_from_quiz(
        self,
        *,
        db: AsyncSession,
        org_id: uuid.UUID,
        payload: QuizSubmitRequest,
        phone: str | None,
        extracted_payload: dict[str, Any],
        derived_status: LeadStatus,
    ) -> Lead:
        resolved = await lead_service.resolve_contact_data(
            db=db,
            org_id=org_id,
            full_name=payload.contact.name,
            phone=phone,
            username=payload.contact.telegram_username,
            source=payload.source or "quiz",
            existing_telegram_id=payload.telegram_id,
        )

        if resolved.get("telegram_id"):
            existing = await self._find_by_telegram_id(
                db=db,
                org_id=org_id,
                telegram_id=resolved["telegram_id"],
            )
            if existing:
                await self.update_lead_from_quiz(
                    lead=existing,
                    payload=payload,
                    phone=phone,
                    extracted_payload=extracted_payload,
                    derived_status=derived_status,
                )
                return existing

        data = self.parse_extracted_data(None)
        self.merge_extracted_payload(data, extracted_payload)
        if resolved.get("messenger_presence"):
            data["messengers"] = {
                **(data.get("messengers") or {}),
                **resolved["messenger_presence"],
            }
        if resolved.get("whatsapp_wa_id"):
            data["whatsapp_wa_id"] = resolved["whatsapp_wa_id"]

        lead = Lead(
            org_id=org_id,
            telegram_id=resolved.get("telegram_id"),
            username=resolved.get("username"),
            full_name=resolved.get("full_name") or payload.contact.name,
            phone=phone,
            status=derived_status.value,
            source=payload.source or "quiz",
            extracted_data=json.dumps(data, ensure_ascii=False),
            telegram_lookup_status=resolved.get("telegram_lookup_status") or "not_checked",
            telegram_lookup_checked_at=resolved.get("telegram_lookup_checked_at"),
            telegram_lookup_error=resolved.get("telegram_lookup_error"),
        )
        db.add(lead)
        return lead

    @classmethod
    def clean_phone(cls, phone: str | None) -> str | None:
        return phone.strip() if phone and phone.strip() else None

    @classmethod
    def phone_digits(cls, phone: str | None) -> str:
        return cls.PHONE_DIGITS_RE.sub("", phone or "")

    @staticmethod
    def clean_username(username: str | None) -> str | None:
        if not username:
            return None
        clean = username.strip()
        return clean[1:] if clean.startswith("@") else clean

    @staticmethod
    def parse_extracted_data(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}

    def merge_extracted_payload(self, target: dict[str, Any], payload: dict[str, Any]) -> None:
        existing_quiz = target.get("quiz")
        incoming_quiz = payload.get("quiz")
        if isinstance(existing_quiz, dict) and isinstance(incoming_quiz, dict):
            history = target.get("quiz_history")
            history_list = history if isinstance(history, list) else []
            history_list.append({**existing_quiz, "archived_at": datetime.now(timezone.utc).isoformat()})
            target["quiz_history"] = history_list[-10:]

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

    @classmethod
    def auto_quiz_statuses(cls) -> set[str]:
        return {
            LeadStatus.NEW.value,
            LeadStatus.QUIZ_COMPLETED.value,
            LeadStatus.MESSENGER_PENDING.value,
            LeadStatus.DESIGN_PENDING.value,
            LeadStatus.DESIGN_REVIEW.value,
            LeadStatus.MEASUREMENT_PENDING.value,
        }

    async def _find_by_id(self, *, db: AsyncSession, org_id: uuid.UUID, lead_id: uuid.UUID) -> Lead | None:
        result = await db.execute(select(Lead).where(Lead.org_id == org_id, Lead.id == lead_id))
        return result.scalar_one_or_none()

    async def _find_by_session_token(
        self,
        *,
        db: AsyncSession,
        org_id: uuid.UUID,
        session_token: str,
    ) -> Lead | None:
        result = await db.execute(
            select(Lead)
            .where(
                Lead.org_id == org_id,
                Lead.extracted_data.is_not(None),
                Lead.extracted_data.contains(session_token),
                Lead.status.notin_(self.TERMINAL_SKIP_STATUSES),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_by_telegram_id(self, *, db: AsyncSession, org_id: uuid.UUID, telegram_id: int) -> Lead | None:
        result = await db.execute(
            select(Lead)
            .where(
                Lead.org_id == org_id,
                Lead.telegram_id == telegram_id,
                Lead.status.notin_(self.TERMINAL_SKIP_STATUSES),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _find_by_phone(self, *, db: AsyncSession, org_id: uuid.UUID, phone: str) -> Lead | None:
        digits = self.phone_digits(phone)
        conditions = [Lead.phone == phone]
        if digits:
            conditions.append(func.regexp_replace(Lead.phone, r"\D", "", "g") == digits)
        if len(digits) >= 10:
            conditions.append(Lead.phone.ilike(f"%{digits[-10:]}%"))

        result = await db.execute(
            select(Lead)
            .where(
                Lead.org_id == org_id,
                Lead.phone.is_not(None),
                Lead.status.notin_(self.TERMINAL_SKIP_STATUSES),
                or_(*conditions),
            )
            .order_by(Lead.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()


quiz_lead_deduplication_service = QuizLeadDeduplicationService()
