"""LLM-based router for safe CRM tools in lead chats."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from src.models import Lead
from src.services.openrouter_service import openrouter_service


ALLOWED_ACTIONS = {
    "none",
    "read_lead_summary",
    "read_measurement_booking",
    "update_measurement_address",
    "change_measurement_booking",
    "reschedule_measurement",
    "cancel_measurement",
    "show_measurement_slots",
    "read_estimate_status",
    "send_final_estimate",
    "handoff_to_manager",
}


@dataclass
class CrmToolDecision:
    action: str = "none"
    args: dict[str, Any] = field(default_factory=dict)
    confidence: int = 0
    reason: str = ""

    @property
    def should_execute(self) -> bool:
        return self.action in ALLOWED_ACTIONS and self.action != "none" and self.confidence >= 55


async def choose_crm_tool(
    *,
    lead: Lead,
    user_text: str,
    stage_context: Any = None,
    model: str | None = None,
    trace_id: str | None = None,
    user_id: str | None = None,
) -> CrmToolDecision:
    text = (user_text or "").strip()
    if not text:
        return CrmToolDecision(reason="empty_text")

    prompt = _build_router_prompt(lead=lead, stage_context=stage_context)
    try:
        response = await openrouter_service.generate_response(
            conversation_history=[{"role": "user", "content": text}],
            system_prompt=prompt,
            model=model,
            trace_id=trace_id,
            user_id=user_id,
        )
    except Exception as exc:
        return CrmToolDecision(reason=f"router_error:{str(exc)[:120]}")

    data = response.get("extracted_data")
    if not isinstance(data, dict):
        data = _parse_json(response.get("text"))
    if not isinstance(data, dict):
        return CrmToolDecision(reason="no_json")

    action = str(data.get("action") or data.get("tool_action") or "none").strip().lower()
    if action not in ALLOWED_ACTIONS:
        action = "none"

    args = data.get("args") if isinstance(data.get("args"), dict) else {}
    confidence = _safe_int(data.get("confidence"), default=0)
    reason = str(data.get("reason") or "")[:240]
    return CrmToolDecision(action=action, args=args, confidence=confidence, reason=reason)


def _build_router_prompt(*, lead: Lead, stage_context: Any = None) -> str:
    snapshot = _lead_snapshot(lead=lead, stage_context=stage_context)
    return f"""
Ты CRM tool-router. Твоя задача: по последнему сообщению клиента выбрать ОДИН безопасный инструмент CRM.
Не отвечай клиенту текстом. Верни только JSON.

CRM_SNAPSHOT:
{json.dumps(snapshot, ensure_ascii=False)}

Доступные tools:
- read_lead_summary: клиент спрашивает, какие данные/заявка уже есть в CRM.
- read_measurement_booking: клиент спрашивает дату, время, адрес, статус записи/замера.
- update_measurement_address: клиент явно дает новый адрес для уже выбранного/записанного замера.
- change_measurement_booking: клиент хочет изменить данные записи, но не дал новое значение.
- reschedule_measurement: клиент хочет перенести дату/время существующего замера.
- cancel_measurement: клиент хочет отменить замер.
- show_measurement_slots: клиент явно хочет записаться или выбрать новый слот.
- read_estimate_status: клиент спрашивает статус сметы, готова ли смета.
- send_final_estimate: клиент просит прислать/повторно отправить файл готовой сметы.
- handoff_to_manager: клиент просит человека/менеджера.
- none: обычный вопрос про ремонт, цену, портфолио, гарантию, процесс или нет уверенности.

Правила приоритета:
1. Изменение данных выше чтения. "нет, адрес мой химки 24" => update_measurement_address.
2. Вопросы "когда замер?", "адрес записали?", "какая бронь?" => read_measurement_booking, НЕ show_measurement_slots.
3. show_measurement_slots только при явном желании записаться/выбрать время: "хочу записаться", "запишите", "подберите слот".
4. Если клиент дает новый адрес, извлеки чистый адрес в args.measurement_address без слов "нет", "мой адрес", "поменяйте".
5. Не выбирай инструмент ради продажи, выбирай только под намерение клиента.

Формат строго:
{{
  "action": "one_allowed_action",
  "args": {{"measurement_address": "..." }},
  "confidence": 0-100,
  "reason": "коротко почему"
}}
"""


def _lead_snapshot(*, lead: Lead, stage_context: Any = None) -> dict[str, Any]:
    data = _parse_json(getattr(lead, "extracted_data", None)) or {}
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    estimate = data.get("estimate_request") if isinstance(data.get("estimate_request"), dict) else {}
    metadata = getattr(stage_context, "metadata", {}) if stage_context else {}
    return {
        "lead_status": getattr(lead, "status", None),
        "lead_source": getattr(lead, "source", None),
        "phone_present": bool(getattr(lead, "phone", None)),
        "next_action": metadata.get("next_action") if isinstance(metadata, dict) else None,
        "measurement": {
            "status": measurement.get("status"),
            "start": measurement.get("start"),
            "address": measurement.get("address"),
            "booking_uid_present": bool(measurement.get("booking_uid")),
            "pending_start_present": bool(measurement.get("pending_start")),
        },
        "estimate": {
            "status": estimate.get("status"),
            "final_file_present": bool(isinstance(estimate.get("final_file"), dict) and estimate["final_file"].get("url")),
        },
    }


def _parse_json(value: Any) -> dict[str, Any] | None:
    if isinstance(value, dict):
        return value
    if not value:
        return None
    try:
        parsed = json.loads(str(value))
        return parsed if isinstance(parsed, dict) else None
    except json.JSONDecodeError:
        return None


def _safe_int(value: Any, *, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
