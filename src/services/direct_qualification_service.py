"""Inline qualification flow for direct Telegram leads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


CALLBACK_PREFIX = "dq"
STATE_KEY = "direct_qualification"


@dataclass(frozen=True)
class DirectQualificationOption:
    value: str
    label: str
    data: dict[str, Any]


@dataclass(frozen=True)
class DirectQualificationStep:
    field: str
    question: str
    options: tuple[DirectQualificationOption, ...]


@dataclass(frozen=True)
class DirectQualificationPrompt:
    field: str
    text: str
    keyboard: InlineKeyboardMarkup


@dataclass(frozen=True)
class DirectQualificationAnswer:
    field: str
    value: str
    label: str
    updated_data: dict[str, Any]
    next_prompt: DirectQualificationPrompt | None
    completion_text: str | None


STEPS: tuple[DirectQualificationStep, ...] = (
    DirectQualificationStep(
        field="area",
        question="Чтобы сориентировать по бюджету точнее, выберите площадь объекта:",
        options=(
            DirectQualificationOption("xs", "До 40 м²", {"area_range": "до 40 м²"}),
            DirectQualificationOption("sm", "40–70 м²", {"area_range": "40–70 м²"}),
            DirectQualificationOption("md", "70–100 м²", {"area_range": "70–100 м²"}),
            DirectQualificationOption("lg", "100+ м²", {"area_range": "100+ м²"}),
        ),
    ),
    DirectQualificationStep(
        field="property_type",
        question="Понял. Что ремонтируем?",
        options=(
            DirectQualificationOption("flat", "Квартира", {"property_type": "квартира"}),
            DirectQualificationOption("house", "Дом", {"property_type": "дом"}),
            DirectQualificationOption("commercial", "Коммерция", {"property_type": "коммерция"}),
        ),
    ),
    DirectQualificationStep(
        field="housing_type",
        question="Это новостройка или вторичное жилье?",
        options=(
            DirectQualificationOption("new", "Новостройка", {"housing_type": "новостройка"}),
            DirectQualificationOption("secondary", "Вторичка", {"housing_type": "вторичное жилье"}),
        ),
    ),
    DirectQualificationStep(
        field="renovation_type",
        question="Какой формат ремонта рассматриваете?",
        options=(
            DirectQualificationOption("cosmetic", "Косметический", {"renovation_type": "косметический"}),
            DirectQualificationOption("finish", "Чистовая отделка", {"renovation_type": "чистовая отделка"}),
            DirectQualificationOption("full", "Под ключ", {"renovation_type": "под ключ"}),
        ),
    ),
    DirectQualificationStep(
        field="design",
        question="Есть дизайн-проект?",
        options=(
            DirectQualificationOption("yes", "Да, готов", {"design_project_status": "готов"}),
            DirectQualificationOption("wip", "В работе", {"design_project_status": "в работе"}),
            DirectQualificationOption("no", "Пока нет", {"design_project_status": "нет"}),
        ),
    ),
    DirectQualificationStep(
        field="timeline",
        question="Когда планируете начинать ремонт?",
        options=(
            DirectQualificationOption("asap", "Как можно скорее", {"timeline": "как можно скорее"}),
            DirectQualificationOption("month", "В течение месяца", {"timeline": "в течение месяца"}),
            DirectQualificationOption("later", "Позже", {"timeline": "позже"}),
        ),
    ),
)

OPTION_BY_FIELD = {
    step.field: {option.value: option for option in step.options}
    for step in STEPS
}
PRICE_WORDS = (
    "цен",
    "стоим",
    "сколько",
    "прайс",
    "бюджет",
    "расчет",
    "расчёт",
    "смет",
    "ремонт",
)


def should_offer_qualification(text: str, extracted_data: dict[str, Any]) -> bool:
    if _has_quiz_answers(extracted_data):
        return False
    state = _state(extracted_data)
    if state.get("active") and not state.get("completed"):
        return True
    completed_fields = _completed_fields(extracted_data)
    if completed_fields and len(completed_fields) < len(STEPS):
        return True
    normalized = (text or "").lower()
    return any(word in normalized for word in PRICE_WORDS)


def build_next_prompt(extracted_data: dict[str, Any]) -> DirectQualificationPrompt | None:
    if _has_quiz_answers(extracted_data):
        return None
    completed_fields = _completed_fields(extracted_data)
    for step in STEPS:
        if step.field not in completed_fields:
            return DirectQualificationPrompt(
                field=step.field,
                text=step.question,
                keyboard=_keyboard_for_step(step),
            )
    return None


def apply_callback_answer(
    extracted_data: dict[str, Any],
    callback_data: str | None,
) -> DirectQualificationAnswer | None:
    field, value = _parse_callback(callback_data)
    if not field or not value:
        return None

    option = OPTION_BY_FIELD.get(field, {}).get(value)
    if not option:
        return None

    updated = dict(extracted_data or {})
    state = dict(_state(updated))
    answers = state.get("answers") if isinstance(state.get("answers"), dict) else {}
    answers = dict(answers)
    answers[field] = {
        "value": value,
        "label": option.label,
        "answered_at": _now_iso(),
    }

    state.update(
        {
            "active": True,
            "completed": False,
            "answers": answers,
            "updated_at": _now_iso(),
        }
    )
    updated[STATE_KEY] = state
    updated.update(option.data)

    next_prompt = build_next_prompt(updated)
    completion_text = None
    if next_prompt is None:
        state["completed"] = True
        state["completed_at"] = _now_iso()
        updated[STATE_KEY] = state
        completion_text = _completion_text(updated)

    return DirectQualificationAnswer(
        field=field,
        value=value,
        label=option.label,
        updated_data=updated,
        next_prompt=next_prompt,
        completion_text=completion_text,
    )


def _keyboard_for_step(step: DirectQualificationStep) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for option in step.options:
        row.append(
            InlineKeyboardButton(
                text=option.label,
                callback_data=f"{CALLBACK_PREFIX}:{step.field}:{option.value}",
            )
        )
        if len(row) == 2:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    return InlineKeyboardMarkup(inline_keyboard=rows)


def _parse_callback(data: str | None) -> tuple[str | None, str | None]:
    parts = (data or "").split(":")
    if len(parts) != 3 or parts[0] != CALLBACK_PREFIX:
        return None, None
    return parts[1], parts[2]


def _has_quiz_answers(extracted_data: dict[str, Any]) -> bool:
    quiz = extracted_data.get("quiz") if isinstance(extracted_data.get("quiz"), dict) else {}
    answers = quiz.get("answers") if isinstance(quiz.get("answers"), dict) else {}
    return bool(answers)


def _state(extracted_data: dict[str, Any]) -> dict[str, Any]:
    state = extracted_data.get(STATE_KEY)
    return state if isinstance(state, dict) else {}


def _completed_fields(extracted_data: dict[str, Any]) -> set[str]:
    fields: set[str] = set()
    answers = _state(extracted_data).get("answers")
    if isinstance(answers, dict):
        fields.update(key for key, value in answers.items() if value)
    if extracted_data.get("area_sqm") or extracted_data.get("area_range"):
        fields.add("area")
    if extracted_data.get("property_type"):
        fields.add("property_type")
    if extracted_data.get("housing_type"):
        fields.add("housing_type")
    if extracted_data.get("renovation_type"):
        fields.add("renovation_type")
    if extracted_data.get("design_project_status"):
        fields.add("design")
    if extracted_data.get("timeline") or extracted_data.get("deadline"):
        fields.add("timeline")
    return fields


def _completion_text(extracted_data: dict[str, Any]) -> str:
    return (
        "Спасибо, собрали базовые вводные ✅\n\n"
        "Менеджер уже увидит их в заявке и сможет точнее сориентировать вас "
        "по ремонту без лишних повторных вопросов."
    )


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
