from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json
import uuid
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models import ChatMessage, FunnelEvent, FunnelSession, Lead, LeadStatus


QUIZ_ANSWER_LABELS = {
    "type": "Объект",
    "area": "Площадь",
    "rtype": "Тип ремонта",
    "state": "Состояние",
    "rooms": "Объем",
    "design": "Дизайн-проект",
    "deadline": "Срок старта",
    "budget": "Бюджет",
}


@dataclass
class LeadStageContext:
    next_action: str
    expected_from_client: str
    client_expects: str
    prompt_block: str
    metadata: dict[str, Any]


class LeadStageContextService:
    async def build_context(
        self,
        db: AsyncSession,
        lead: Lead,
        personal_quiz_url: str | None = None,
    ) -> LeadStageContext:
        extracted = self._parse_json(lead.extracted_data)
        quiz = extracted.get("quiz") if isinstance(extracted.get("quiz"), dict) else {}
        answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}

        session = await self._get_latest_session(db, lead.id)
        event_types = await self._get_event_types(db, session.id) if session else set()

        design_answer = str(answers.get("design") or "").lower()
        design_file = bool(quiz.get("design_project_file_url"))
        measurement = extracted.get("measurement") if isinstance(extracted.get("measurement"), dict) else {}
        measurement_start = str(measurement.get("start") or "").strip()
        measurement_status = str(measurement.get("status") or "").strip()
        measurement_booking_uid = str(measurement.get("booking_uid") or "").strip()
        measurement_booked = bool(measurement_start and measurement_booking_uid) or (
            measurement_status == "booked" and bool(measurement_start)
        ) or "measurement_booked" in event_types
        quiz_completed = bool(session and session.status == "completed") or "quiz_completed" in event_types
        has_quiz_answers = bool(answers)
        source = lead.source or ""

        lead_status = str(lead.status or "")

        if lead_status in {LeadStatus.CONTRACT.value, LeadStatus.CONTRACT_NEGOTIATION.value}:
            next_action = "contract_closing"
            expected_from_client = "confirm_contract_or_start_date"
            client_expects = "final_terms_or_start_confirmation"
            response_policy = [
                "Коротко вернуть клиента к финальному шагу.",
                "Предложить зафиксировать дату старта, бригаду или условия договора.",
                "Не начинать заново квалификацию и не задавать вопросы из квиза.",
            ]
        elif lead_status in {LeadStatus.ESTIMATE.value, LeadStatus.ESTIMATE_SENT.value}:
            next_action = "needs_estimate_review"
            expected_from_client = "review_estimate_or_ask_questions"
            client_expects = "estimate_explanation_or_optimization"
            response_policy = [
                "Напомнить про отправленную смету.",
                "Предложить коротко разобрать расчет или оптимизировать бюджет.",
                "Не давить на договор, пока клиент не отреагировал на смету.",
            ]
        elif lead_status == LeadStatus.ESTIMATE_REVIEW.value:
            next_action = "estimate_internal_review"
            expected_from_client = "wait_estimator_approval"
            client_expects = "approved_estimate_after_review"
            response_policy = [
                "Не отправлять клиенту финальные цифры до одобрения сметчика.",
                "Если клиент пишет сам — коротко сообщить, что расчет проверяет сметчик.",
                "Не давить на договор до отправки проверенной сметы.",
            ]
        elif lead_status == LeadStatus.ESTIMATE_PREPARING.value:
            next_action = "needs_estimate_review"
            expected_from_client = "wait_estimate_or_clarify_details"
            client_expects = "estimate_preparation_update"
            response_policy = [
                "Коротко сообщить, что расчет в работе.",
                "Если нужен один уточняющий вопрос для сметы — задать только его.",
                "Не продавать договор до отправки сметы.",
            ]
        elif lead_status == LeadStatus.DESIGN_REVIEW.value:
            next_action = "needs_estimate_review"
            expected_from_client = "wait_design_project_review_or_answer_question"
            client_expects = "design_project_review_and_estimate"
            response_policy = [
                "Подтвердить, что дизайн-проект получен.",
                "Объяснить следующий шаг по разбору проекта и расчету.",
                "Не просить проект повторно.",
            ]
        elif has_quiz_answers and design_answer in {"yes", "wip"} and not design_file:
            next_action = "awaiting_design_project"
            expected_from_client = "send_design_project_file"
            client_expects = "estimate_after_design_project"
            response_policy = [
                "Коротко подтвердить, что анкета получена.",
                "Попросить прислать дизайн-проект файлом сюда.",
                "Не предлагать замер первым шагом, пока клиент говорит, что проект есть или в работе.",
            ]
        elif lead_status in {LeadStatus.MEASUREMENT_BOOKED.value, LeadStatus.MEASUREMENT.value} and measurement_booked:
            next_action = "confirm_measurement"
            expected_from_client = "confirm_address_or_wait_manager"
            client_expects = "measurement_confirmation"
            response_policy = [
                "Подтвердить выбранный слот замера.",
                "Попросить адрес объекта только если его нет в CRM/переписке.",
                "Не задавать вопросы из квиза повторно.",
            ]
        elif lead_status == LeadStatus.MEASUREMENT_DONE.value:
            next_action = "needs_estimate_review"
            expected_from_client = "wait_estimate_after_measurement"
            client_expects = "estimate_after_measurement"
            response_policy = [
                "Опирайся на то, что замер уже проведен.",
                "Сообщи следующий шаг по подготовке сметы.",
                "Не предлагай записаться на замер повторно.",
            ]
        elif has_quiz_answers and not measurement_booked and design_answer in {"no", "", "none"}:
            next_action = "awaiting_measurement_slot"
            expected_from_client = "choose_measurement_time"
            client_expects = "estimate_or_measurement_booking"
            response_policy = [
                "Коротко подтвердить, что расчет по квизу получен.",
                "Объяснить, что для точной сметы нужен замер.",
                "Предложить выбрать время замера или попросить удобный день/интервал.",
            ]
        elif has_quiz_answers and quiz_completed:
            next_action = "needs_estimate_review"
            expected_from_client = "clarify_missing_details_or_wait_estimate"
            client_expects = "estimate_review"
            response_policy = [
                "Отталкиваться от ответов квиза.",
                "Дать короткий следующий шаг по смете.",
                "Задать максимум один уточняющий вопрос, если он действительно нужен.",
            ]
        elif source in {"userbot", "telegram", "quiz_telegram"} and not has_quiz_answers:
            next_action = "direct_chat_qualification"
            expected_from_client = "answer_in_chat_or_open_quiz"
            client_expects = "consultation"
            response_policy = [
                "Консультировать прямо в чате.",
                "Если клиент спрашивает про цену, сроки, замер или дал мало данных, предложить персональную ссылку на квиз.",
                "Не заставлять проходить квиз, если клиент явно хочет общаться здесь.",
            ]
        else:
            next_action = "general_consultation"
            expected_from_client = "clarify_request"
            client_expects = "answer_to_message"
            response_policy = [
                "Ответить по сути сообщения.",
                "Не расписывать длинную продажу без запроса.",
                "Задать максимум один следующий вопрос.",
            ]

        missing = self._missing_quiz_fields(answers)
        recent_messages = await self._get_recent_messages(db, lead.id)
        prompt_block = self._render_prompt(
            lead=lead,
            session=session,
            answers=answers,
            quiz=quiz,
            extracted=extracted,
            recent_messages=recent_messages,
            next_action=next_action,
            expected_from_client=expected_from_client,
            client_expects=client_expects,
            response_policy=response_policy,
            missing=missing,
            personal_quiz_url=personal_quiz_url,
        )
        return LeadStageContext(
            next_action=next_action,
            expected_from_client=expected_from_client,
            client_expects=client_expects,
            prompt_block=prompt_block,
            metadata={
                "next_action": next_action,
                "expected_from_client": expected_from_client,
                "client_expects": client_expects,
                "quiz_completed": quiz_completed,
                "has_quiz_answers": has_quiz_answers,
                "missing_quiz_fields": missing,
                "measurement_start": measurement.get("start"),
                "measurement_address": measurement.get("address") or extracted.get("address"),
            },
        )

    async def _get_latest_session(self, db: AsyncSession, lead_id: uuid.UUID) -> FunnelSession | None:
        result = await db.execute(
            select(FunnelSession)
            .where(FunnelSession.lead_id == lead_id)
            .order_by(FunnelSession.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _get_event_types(self, db: AsyncSession, session_id: uuid.UUID) -> set[str]:
        result = await db.execute(select(FunnelEvent.event_type).where(FunnelEvent.session_id == session_id))
        return {row[0] for row in result.all()}

    async def _get_recent_messages(self, db: AsyncSession, lead_id: uuid.UUID) -> list[ChatMessage]:
        result = await db.execute(
            select(ChatMessage)
            .where(ChatMessage.lead_id == lead_id)
            .order_by(ChatMessage.created_at.desc())
            .limit(8)
        )
        return list(reversed(result.scalars().all()))

    def _render_prompt(
        self,
        lead: Lead,
        session: FunnelSession | None,
        answers: dict[str, Any],
        quiz: dict[str, Any],
        extracted: dict[str, Any],
        recent_messages: list[ChatMessage],
        next_action: str,
        expected_from_client: str,
        client_expects: str,
        response_policy: list[str],
        missing: list[str],
        personal_quiz_url: str | None,
    ) -> str:
        answer_lines = []
        for key, label in QUIZ_ANSWER_LABELS.items():
            if answers.get(key) is not None:
                answer_lines.append(f"- {label}: {answers.get(key)}")
        if not answer_lines:
            answer_lines.append("- Нет заполненного квиза.")

        measurement = extracted.get("measurement") if isinstance(extracted.get("measurement"), dict) else {}
        design_file = (quiz.get("design_project_file_url") or "нет")
        measurement_start = self._format_measurement_start(measurement.get("start"))
        measurement_address = measurement.get("address") or extracted.get("address") or "не указан"
        price_label = ""
        price = quiz.get("price") if isinstance(quiz.get("price"), dict) else None
        if isinstance(price, dict):
            price_label = str(price.get("label") or "").strip()
        recent_lines = self._format_recent_messages(recent_messages)
        policy_lines = "\n".join(f"- {line}" for line in response_policy)
        missing_line = ", ".join(missing) if missing else "нет критичных пропусков"

        return f"""
CRM_STAGE_CONTEXT:
lead_id: {lead.id}
lead_status: {lead.status}
lead_source: {lead.source or "unknown"}
client_name: {lead.full_name or "не указано"}
client_phone: {lead.phone or "не указан"}
telegram_username: {lead.username or "не указан"}
funnel_session: {session.session_token if session else "none"}
next_action: {next_action}
expected_from_client: {expected_from_client}
client_expects: {client_expects}
quiz_completed: {bool(session and session.status == "completed")}
design_project_file: {design_file}
measurement_slot: {measurement.get("start") or "не выбран"}
measurement_slot_local: {measurement_start or "не выбран"}
measurement_status: {measurement.get("status") or "не указан"}
measurement_address: {measurement_address}
preliminary_estimate: {price_label or "не рассчитан"}
missing_quiz_fields: {missing_line}
personal_quiz_url: {personal_quiz_url or "none"}

QUIZ_ANSWERS:
{chr(10).join(answer_lines)}

RECENT_CRM_MESSAGES:
{recent_lines}

STAGE_AWARE_RESPONSE_RULES:
- Сначала учитывай CRM_STAGE_CONTEXT и QUIZ_ANSWERS.
- Если данные уже есть в квизе, не спрашивай их повторно.
- Если клиент пришел после квиза, отвечай коротко и веди к next_action.
- Если клиент выбрал/просит замер, не болтай лишнего: предложи или подтверди следующий шаг.
- Если lead_status = MEASUREMENT_BOOKED или MEASUREMENT, ты уже после записи на замер: не начинай продажу заново, не благодари за звонок, не представляйся заново, не говори "менеджер подтвердит" как единственный ответ. Подтверди, что ты на связи, и опирайся на measurement_slot_local и measurement_address.
- Если нужно уточнение, задай только один вопрос.
- Не обещай точную смету без замера или дизайн-проекта.
- Не отправляй personal_quiz_url клиенту, который уже заполнил квиз, кроме случая когда он сам просит пройти заново.

RESPONSE_POLICY:
{policy_lines}
"""

    def _format_measurement_start(self, value: Any) -> str:
        if not value:
            return ""
        try:
            dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
        except Exception:
            return str(value)

    def _format_recent_messages(self, messages: list[ChatMessage]) -> str:
        lines: list[str] = []
        for message in messages:
            direction = "client" if str(message.direction).endswith("INBOUND") else "assistant"
            content = str(message.content or "").replace("\n", " ").strip()
            if len(content) > 220:
                content = content[:217] + "..."
            if content:
                lines.append(f"- {direction}: {content}")
        return "\n".join(lines) if lines else "- Истории сообщений пока нет."

    def _missing_quiz_fields(self, answers: dict[str, Any]) -> list[str]:
        return [key for key in QUIZ_ANSWER_LABELS if not answers.get(key)]

    def _parse_json(self, value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except json.JSONDecodeError:
            return {}


lead_stage_context_service = LeadStageContextService()
