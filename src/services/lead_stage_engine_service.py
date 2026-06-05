from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models import FunnelEvent, FunnelSession, Lead, LeadStatus
from src.services.lead_audit_service import lead_audit_service


TERMINAL_STATUSES = {
    LeadStatus.WON.value,
    LeadStatus.LOST.value,
    LeadStatus.SPAM.value,
}

HUMAN_LOCKED_STATUSES = {
    LeadStatus.CONTRACT_NEGOTIATION.value,
    LeadStatus.CONTRACT.value,
    LeadStatus.PAYMENT_PENDING.value,
    LeadStatus.KEYS_PENDING.value,
    LeadStatus.READY_TO_START.value,
    LeadStatus.WON.value,
    LeadStatus.LOST.value,
    LeadStatus.SPAM.value,
}

ENGINE_MANAGED_STATUSES = {
    LeadStatus.NEW.value,
    LeadStatus.QUIZ_COMPLETED.value,
    LeadStatus.MESSENGER_PENDING.value,
    LeadStatus.DESIGN_PENDING.value,
    LeadStatus.DESIGN_REVIEW.value,
    LeadStatus.CONSULTING.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.MEASUREMENT_PENDING.value,
    LeadStatus.MEASUREMENT_BOOKED.value,
    LeadStatus.MEASUREMENT.value,
    LeadStatus.MEASUREMENT_DONE.value,
    LeadStatus.ESTIMATE_PREPARING.value,
    LeadStatus.ESTIMATE_REVIEW.value,
    LeadStatus.ESTIMATE_SENT.value,
    LeadStatus.ESTIMATE.value,
    LeadStatus.FOLLOW_UP.value,
}


@dataclass(frozen=True)
class StageDecision:
    status: LeadStatus
    reason: str
    confidence: str = "high"


class LeadStageEngineService:
    """
    Central source of truth for automatic lead stage transitions.

    The engine uses durable facts: quiz answers, funnel events, uploaded files,
    booking metadata, and current CRM status. It only moves leads that are still
    in automation-owned stages; final/manual commercial stages stay untouched.
    """

    async def apply_for_session(
        self,
        db: AsyncSession,
        session: FunnelSession,
        event_type: str | None = None,
        source: str = "stage_engine",
    ) -> StageDecision | None:
        if not session.lead_id:
            return None

        result = await db.execute(select(Lead).where(Lead.id == session.lead_id))
        lead = result.scalar_one_or_none()
        if not lead:
            return None

        return await self.apply_for_lead(
            db=db,
            lead=lead,
            session=session,
            event_type=event_type,
            source=source,
        )

    async def apply_for_lead(
        self,
        db: AsyncSession,
        lead: Lead,
        session: FunnelSession | None = None,
        event_type: str | None = None,
        source: str = "stage_engine",
    ) -> StageDecision | None:
        if lead.status in TERMINAL_STATUSES:
            return None
        if lead.status in HUMAN_LOCKED_STATUSES and event_type not in {
            "contract_signed",
            "payment_received",
            "keys_received",
            "work_started",
        }:
            return None
        if lead.status and lead.status not in ENGINE_MANAGED_STATUSES:
            return None

        if not session:
            session = await self._latest_session(db, lead.id)

        event_types = await self._event_types(db, session.id) if session else set()
        decision = self.decide(lead=lead, session=session, event_types=event_types)
        if not decision or lead.status == decision.status.value:
            return decision

        previous = lead.status
        lead.status = decision.status.value
        await lead_audit_service.log_change(
            db=db,
            lead=lead,
            action="stage_auto_updated",
            source=source,
            changes={
                "status": {"old": previous, "new": decision.status.value},
                "reason": {"old": None, "new": decision.reason},
                "event_type": {"old": None, "new": event_type},
            },
        )
        return decision

    def decide(
        self,
        lead: Lead,
        session: FunnelSession | None,
        event_types: set[str],
    ) -> StageDecision | None:
        data = self._parse_json(lead.extracted_data)
        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}
        measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
        estimate_request = data.get("estimate_request") if isinstance(data.get("estimate_request"), dict) else {}

        design_answer = str(answers.get("design") or "").lower()
        has_quiz = bool(answers)
        has_design_file = bool(quiz.get("design_project_file_url")) or "design_file_uploaded" in event_types
        estimate_status = str(estimate_request.get("status") or "").lower()
        needs_estimate = estimate_status == "needs_estimate"
        final_estimate_ready = estimate_status == "ready_to_send" and bool(estimate_request.get("final_file"))
        final_estimate_sent = estimate_status == "sent" and bool(estimate_request.get("final_file"))
        design_later = "design_upload_skipped" in event_types
        has_inbound = bool(event_types & {"telegram_message_received", "whatsapp_message_received"})
        has_messenger_click = bool(event_types & {"telegram_clicked", "whatsapp_clicked"})
        measurement_status = str(measurement.get("status") or "").lower()
        measurement_start = str(measurement.get("start") or "").strip()
        measurement_booked = (
            bool(measurement_start and measurement.get("booking_uid"))
            or (measurement_status == "booked" and bool(measurement_start))
        )
        measurement_requested = (
            bool(measurement_start)
            or measurement_status == "requested"
            or "measurement_booking_requested" in event_types
            or "measurement_booking_failed" in event_types
        )
        measurement_clicked = "cal_slot_selected" in event_types
        quiz_completed = bool(session and session.status == "completed") or "quiz_completed" in event_types

        if "work_started" in event_types:
            return StageDecision(LeadStatus.WON, "work_started")
        if "keys_received" in event_types:
            return StageDecision(LeadStatus.READY_TO_START, "keys_received")
        if "payment_received" in event_types:
            return StageDecision(LeadStatus.KEYS_PENDING, "payment_received")
        if "contract_signed" in event_types:
            return StageDecision(LeadStatus.PAYMENT_PENDING, "contract_signed")
        if "contract_sent" in event_types:
            return StageDecision(LeadStatus.CONTRACT_NEGOTIATION, "contract_sent")
        if final_estimate_sent or "estimate_sent" in event_types:
            return StageDecision(LeadStatus.ESTIMATE_SENT, "estimate_sent")
        if final_estimate_ready:
            return StageDecision(LeadStatus.ESTIMATE, "estimate_ready_to_send")
        if "estimate_review_requested" in event_types or "estimate_ai_created" in event_types:
            return StageDecision(LeadStatus.ESTIMATE_REVIEW, "estimate_review_requested")
        if needs_estimate or "estimate_preparing" in event_types:
            return StageDecision(LeadStatus.ESTIMATE_PREPARING, "estimate_preparing")
        if "measurement_done" in event_types:
            return StageDecision(LeadStatus.MEASUREMENT_DONE, "measurement_done")
        if measurement_booked:
            return StageDecision(LeadStatus.MEASUREMENT_BOOKED, "measurement_booked")
        if measurement_requested:
            return StageDecision(LeadStatus.MEASUREMENT_PENDING, "measurement_requested")
        if has_design_file:
            return StageDecision(LeadStatus.DESIGN_REVIEW, "design_file_uploaded")
        if has_quiz and design_later and design_answer in {"yes", "wip"}:
            return StageDecision(LeadStatus.DESIGN_PENDING, "design_upload_skipped")
        if (measurement_clicked or has_messenger_click) and not has_inbound:
            return StageDecision(LeadStatus.MESSENGER_PENDING, "messenger_clicked_no_inbound")
        if has_quiz and design_answer in {"yes", "wip"}:
            return StageDecision(LeadStatus.DESIGN_PENDING, "design_project_expected")
        if has_quiz and design_answer in {"no", "", "none"}:
            return StageDecision(LeadStatus.MEASUREMENT_PENDING, "measurement_required")
        if has_inbound:
            return StageDecision(LeadStatus.CONSULTING, "messenger_message_received")
        if quiz_completed:
            return StageDecision(LeadStatus.QUIZ_COMPLETED, "quiz_completed")
        if has_quiz:
            return StageDecision(LeadStatus.QUIZ_COMPLETED, "quiz_answers_present")
        return StageDecision(LeadStatus.NEW, "default_new")

    async def _latest_session(self, db: AsyncSession, lead_id: uuid.UUID) -> FunnelSession | None:
        result = await db.execute(
            select(FunnelSession)
            .where(FunnelSession.lead_id == lead_id)
            .order_by(FunnelSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _event_types(self, db: AsyncSession, session_id: uuid.UUID) -> set[str]:
        result = await db.execute(select(FunnelEvent.event_type).where(FunnelEvent.session_id == session_id))
        return {row[0] for row in result.all()}

    def _parse_json(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


lead_stage_engine_service = LeadStageEngineService()
