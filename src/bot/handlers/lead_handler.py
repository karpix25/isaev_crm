"""
Lead handler for processing messages from potential clients.
Integrates AI-powered lead qualification using OpenRouter API.
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timedelta, timezone
import uuid
from zoneinfo import ZoneInfo
from aiogram import Router, F
from aiogram.enums import ChatAction
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram.filters import CommandStart
from aiogram.filters.command import CommandObject
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.bot import dp, bot
from src.database import AsyncSessionLocal
from src.models.lead import LeadStatus
from src.schemas.quiz import MeasurementBookingRequest, QuizContact
from src.services.lead_service import lead_service
from src.services.chat_service import chat_service
from src.services.cal_pro_service import cal_pro_service
from src.services.agent_tool_log_service import agent_tool_log_service
from src.services.openrouter_service import openrouter_service
from src.services.prompt_service import prompt_service
from src.services.knowledge_service import knowledge_service
from src.services.measurement_analytics_service import measurement_analytics_service
from src.services.quiz_value_normalizer import normalize_quiz_design_answer
from src.services.direct_qualification_service import (
    build_next_prompt,
    should_offer_qualification,
)
from src.services.prompts import SALES_AGENT_SYSTEM_PROMPT, IDENTITY_GUARDRAILS, get_initial_message, build_system_prompt, normalize_system_prompt_template
from src.services.business_hours import is_business_hours, get_business_now
from src.config import settings
from src.bot.utils import get_default_org_id, download_user_avatar
from src.bot.measurement_slots import (
    build_measurement_date_keyboard as _build_measurement_date_keyboard,
    build_measurement_time_keyboard as _build_measurement_time_keyboard,
    slot_date_button_label as _slot_date_button_label,
    slot_date_key as _slot_date_key,
    slot_local_datetime as _slot_local_datetime,
    slot_time_label as _slot_time_label,
)
from src.bot.telegram_file_service import save_telegram_document
from src.bot.crm_agent_router import choose_crm_tool
from src.bot.crm_safe_tools import answer_estimate_status, answer_lead_summary, answer_measurement_booking
from src.bot.estimate_actions import looks_like_estimate_file_request, send_ready_estimate_from_crm
from src.models import AuthSession, ChatMessage, Lead, MessageDirection, OperatorAccessRequest, OperatorAccessRequestStatus, Organization, User
from src.models.user import UserRole

logger = logging.getLogger(__name__)

# Create router for lead handlers
router = Router()
LEAD_MESSAGE_DEBOUNCE_SECONDS = 15.0

QUIZ_LABELS = {
    "type": {"flat": "Квартира", "house": "Дом", "commercial": "Коммерция"},
    "area": {"xs": "До 40 м²", "sm": "40–70 м²", "md": "70–100 м²", "lg": "Более 100 м²"},
    "rtype": {"cosm": "Косметический", "finish": "Чистовая отделка", "full": "Под ключ"},
    "design": {"yes": "Проект готов", "wip": "Проект в работе", "no": "Проекта нет"},
}
QUIZ_SUMMARY_FIELDS = [
    ("type", "Объект"),
    ("area", "Площадь"),
    ("rtype", "Ремонт"),
    ("design", "Дизайн"),
]
DEFAULT_ORG_NAME = "Default Organization"
FALLBACK_COMPANY_NAME = "Исаев Групп"


def _drain_background_task(task: asyncio.Task) -> None:
    if task.cancelled():
        return
    try:
        exc = task.exception()
    except asyncio.CancelledError:
        return
    except Exception as exc:
        logger.debug("Failed to inspect background task: %s", exc)
        return
    if exc:
        logger.error("Background task failed: %s", exc, exc_info=(type(exc), exc, exc.__traceback__))


async def _send_typing_action(message: Message) -> None:
    if not bot:
        return
    try:
        await bot.send_chat_action(
            chat_id=message.chat.id,
            action=ChatAction.TYPING,
            business_connection_id=getattr(message, "business_connection_id", None),
            message_thread_id=message.message_thread_id if getattr(message, "is_topic_message", False) else None,
        )
    except Exception as exc:
        logger.debug("Failed to send typing action: %s", exc)


def _is_business_author_message(message: Message) -> bool:
    if not getattr(message, "business_connection_id", None):
        return False
    from_user_id = getattr(getattr(message, "from_user", None), "id", None)
    chat_id = getattr(getattr(message, "chat", None), "id", None)
    return bool(from_user_id and chat_id and int(from_user_id) != int(chat_id))


async def _typing_indicator_loop(message: Message, interval_seconds: float = 4.0) -> None:
    while True:
        await _send_typing_action(message)
        await asyncio.sleep(interval_seconds)


def _start_typing_indicator(message: Message) -> asyncio.Task:
    typing_task = asyncio.create_task(_typing_indicator_loop(message))
    typing_task.add_done_callback(_drain_background_task)
    current_task = asyncio.current_task()
    if current_task:
        current_task.add_done_callback(lambda _: typing_task.cancel())
    return typing_task


def _format_measurement_start(value: str | None) -> str:
    if not value:
        return ""
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(ZoneInfo("Europe/Moscow")).strftime("%d.%m.%Y в %H:%M")
    except Exception:
        return str(value)


def _display_company_name(org) -> str:
    raw_name = str(getattr(org, "name", "") or "").strip()
    if not raw_name or raw_name == DEFAULT_ORG_NAME:
        return FALLBACK_COMPANY_NAME
    return raw_name


def _looks_like_measurement_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return any(word in normalized for word in ("замер", "когда", "во сколько", "дата", "адрес", "выезд"))


def _looks_like_measurement_acknowledgement(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    return normalized in {
        "ок",
        "окей",
        "хорошо",
        "понял",
        "поняла",
        "понятно",
        "спасибо",
        "спасибо!",
        "да",
        "ага",
        "угу",
        "жду",
        "буду ждать",
    }


def _looks_like_measurement_reschedule_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False

    measurement_words = ("замер", "выезд", "инженер", "встреч", "запис", "брон")
    reschedule_words = (
        "перен",
        "поменять",
        "изменить",
        "другую дату",
        "другой день",
        "другое время",
        "не удобно",
        "неудобно",
        "не смогу",
        "не получится",
    )
    if any(word in normalized for word in measurement_words) and any(word in normalized for word in reschedule_words):
        return True
    return any(
        phrase in normalized
        for phrase in (
            "можно поменять дату",
            "можно поменять время",
            "можно перенести",
            "перенесем дату",
            "перенести дату",
            "изменить дату",
            "изменить время",
            "поменять время",
        )
    )


def _looks_like_existing_measurement_lookup(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    booking_context = any(word in normalized for word in ("замер", "запис", "брон", "выезд", "инженер", "встреч", "адрес"))
    lookup_context = any(
        phrase in normalized
        for phrase in (
            "адрес запис",
            "адрес мой",
            "мой адрес",
            "какое число",
            "на какое",
            "когда",
            "во сколько",
            "напомн",
            "есть запись",
            "у нас запись",
            "перенести запись",
            "перенести брон",
        )
    )
    return booking_context and lookup_context


def _looks_like_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    return "?" in normalized or any(
        word in normalized
        for word in (
            "когда",
            "какой",
            "какое",
            "какая",
            "куда",
            "где",
            "напомн",
            "записали",
            "есть",
            "видите",
            "сохранили",
        )
    )


def _looks_like_address_or_booking_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    has_question = _looks_like_question(normalized)
    booking_context = any(word in normalized for word in ("замер", "запис", "брон", "адрес", "выезд"))
    return has_question and booking_context


def _extract_direct_address_correction(text: str) -> str:
    normalized = (text or "").strip()
    if not normalized:
        return ""
    lowered = normalized.lower()
    correction_markers = (
        "нет адрес",
        "адрес мой",
        "мой адрес",
        "поменяйте мой адрес",
        "поменяйте адрес",
        "измени адрес",
        "измените адрес",
        "адрес:",
    )
    if not any(marker in lowered for marker in correction_markers):
        return ""
    if _looks_like_question(lowered):
        return ""

    cleaned = re.sub(
        r"(?i)^(нет[,\\s]*)?(поменяйте|поменять|измени|измените|исправьте|исправь)?\\s*(мой\\s*)?адрес(\\s*(на|:|-))?",
        "",
        normalized,
    ).strip(" .,:;-")
    return cleaned if len(cleaned) >= 5 else ""


def _looks_like_measurement_cancel_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False

    cancel_words = ("отмен", "убери", "сними", "не надо", "не нужен", "не приезж")
    measurement_words = ("замер", "брон", "запис", "выезд", "инженер")
    if any(word in normalized for word in cancel_words) and any(word in normalized for word in measurement_words):
        return True
    return normalized in {"отменяй", "отменить", "отмена", "да отменяй", "отменяй да"}


def _looks_like_measurement_change_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    generic_change = any(word in normalized for word in ("изменить", "поменять", "исправить", "заменить"))
    measurement_context = any(word in normalized for word in ("замер", "брон", "запис", "данн", "дат", "адрес", "телефон", "номер"))
    return generic_change and measurement_context


def _looks_like_measurement_booking_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    if _looks_like_existing_measurement_lookup(normalized) or _looks_like_address_or_booking_question(normalized):
        return False

    direct_calendar_words = ("calpro", "cal pro", "cal.com", "calcom", "календар", "слот", "окн")
    booking_words = ("запис", "заброн", "брон", "замер", "выезд", "инженер")
    request_words = ("дай", "дайте", "скинь", "скиньте", "пришли", "пришлите", "можно", "хочу")
    explicit_booking_phrases = (
        "хочу запис",
        "запишите",
        "запиши",
        "забронируйте",
        "забронируй",
        "можно запис",
        "можно брон",
        "давайте замер",
        "давайте выезд",
        "подберите время",
        "выбрать время",
        "выбрать слот",
    )
    if any(word in normalized for word in direct_calendar_words) and any(word in normalized for word in request_words):
        return True
    if any(phrase in normalized for phrase in explicit_booking_phrases):
        return True
    return any(word in normalized for word in ("замер", "выезд", "инженер")) and any(
        word in normalized for word in request_words
    )


def _looks_like_support_question(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    support_words = (
        "портфолио",
        "портфель",
        "кейсы",
        "примеры",
        "фото работ",
        "фотки работ",
        "отзывы",
        "гарант",
        "договор",
        "оплата",
        "этап",
        "срок",
        "сроки",
        "материал",
        "цена",
        "цены",
        "расцен",
        "вилка",
        "смет",
    )
    question_words = ("есть", "покаж", "скинь", "пришл", "можно", "какие", "какая", "какой", "?")
    return any(word in normalized for word in support_words) and any(word in normalized for word in question_words)


def _looks_like_estimate_file_content_question(text: str) -> bool:
    normalized = (text or "").strip().lower().replace("ё", "е")
    if "смет" not in normalized:
        return False
    content_words = (
        "сумм",
        "итог",
        "тотал",
        "total",
        "сколько",
        "какая",
        "какой",
        "цена",
        "стоим",
        "пункт",
        "позици",
        "что внутри",
        "что там",
    )
    return any(word in normalized for word in content_words)


def _looks_like_measurement_slot_reply(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False

    short_confirmations = {
        "да",
        "давайте",
        "ок",
        "окей",
        "хорошо",
        "можно",
        "да можно",
        "давайте замер",
        "да хочу",
    }
    if normalized in short_confirmations:
        return True

    date_words = (
        "сегодня",
        "завтра",
        "послезавтра",
        "понедельник",
        "вторник",
        "среда",
        "среду",
        "ср",
        "четверг",
        "пятниц",
        "суббот",
        "воскрес",
        "утр",
        "днем",
        "днём",
        "вечер",
        "после обеда",
        "до обеда",
    )
    month_words = (
        "январ",
        "феврал",
        "март",
        "апрел",
        "мая",
        "май",
        "июн",
        "июл",
        "август",
        "сентябр",
        "октябр",
        "ноябр",
        "декабр",
    )
    has_date_word = any(word in normalized for word in date_words + month_words)
    has_time = bool(re.search(r"\b(?:в\s*)?\d{1,2}(?::\d{2})?\b", normalized))
    is_time_only = bool(re.fullmatch(r"(?:в\s*)?\d{1,2}(?::\d{2})?", normalized))
    has_date_number = bool(re.search(r"\b\d{1,2}\s*(?:числа|мая|июн|июл|август|сентябр|октябр|ноябр|декабр)", normalized))
    return has_date_word or has_date_number or is_time_only or ("замер" in normalized and has_time)


def _looks_like_manager_handoff_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    manager_words = ("менеджер", "человек", "оператор", "специалист", "живой")
    request_words = ("позов", "соедин", "передай", "передайте", "хочу", "нужен", "дайте")
    return any(word in normalized for word in manager_words) and any(word in normalized for word in request_words)


def _looks_like_do_not_contact_request(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    phrases = (
        "не пиши",
        "не пишите",
        "не звони",
        "не звоните",
        "не беспокой",
        "не беспокоить",
        "отстань",
        "отстаньте",
        "удалите мой номер",
        "удали мой номер",
        "больше не надо",
        "больше не пиш",
    )
    return any(phrase in normalized for phrase in phrases)


def _looks_like_not_interested(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    phrases = (
        "не хочу у вас",
        "не хочу с вами",
        "не нужен ремонт",
        "ремонт не нужен",
        "передумал делать ремонт",
        "передумали делать ремонт",
        "не актуально",
        "неактуально",
        "отказ",
        "не интересно",
        "неинтересно",
    )
    return any(phrase in normalized for phrase in phrases)


def _looks_like_reactivation(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    reactivation_markers = (
        "передумал",
        "передумали",
        "давай делаем",
        "давайте делать",
        "хочу продолжить",
        "вернемся",
        "вернёмся",
        "актуально снова",
        "снова актуально",
        "готов продолжить",
        "готовы продолжить",
    )
    action_markers = ("делаем", "ремонт", "замер", "запис", "продолж", "давай", "давайте")
    return any(marker in normalized for marker in reactivation_markers) and any(marker in normalized for marker in action_markers)


def _looks_like_abusive_message(text: str) -> bool:
    normalized = (text or "").strip().lower()
    if not normalized:
        return False
    abusive_words = (
        "пошел ты",
        "пошёл ты",
        "иди нах",
        "нахуй",
        "хуйня",
        "чорт",
        "черт",
        "мудак",
        "долбо",
    )
    return any(word in normalized for word in abusive_words)


def _normalize_phone(value: str | None) -> str:
    digits = re.sub(r"\D+", "", value or "")
    if len(digits) == 11 and digits.startswith("8"):
        digits = f"7{digits[1:]}"
    elif len(digits) == 10:
        digits = f"7{digits}"
    return digits if len(digits) >= 10 else ""


def _format_phone(value: str | None) -> str:
    digits = _normalize_phone(value)
    return f"+{digits}" if digits else "не указан"


def _build_measurement_context_answer(lead, text: str) -> str | None:
    if not _looks_like_measurement_question(text):
        return None

    measurement = _lead_measurement_data(lead)
    measurement_date = _format_measurement_start(measurement.get("start"))
    measurement_address = str(measurement.get("address") or "").strip()
    if not measurement_date and not measurement_address:
        return None

    lines = []
    if measurement_date:
        lines.append(f"Замер у нас записан на {measurement_date}.")
    if measurement_address:
        lines.append(f"Адрес: {measurement_address}.")
    lines.append(f"Телефон для связи: {_format_phone(lead.phone or measurement.get('phone'))}.")
    lines.append("За сутки до замера напомним вам, чтобы ничего не потерялось.")
    lines.append("Если нужно перенести запись или исправить адрес, напишите здесь.")
    return "\n".join(lines)


def _build_measurement_status_answer(lead, text: str) -> str:
    measurement = _lead_measurement_data(lead)
    measurement_date = _format_measurement_start(measurement.get("start"))
    measurement_address = str(measurement.get("address") or "").strip()
    has_active_booking = bool(measurement.get("booking_uid") and measurement.get("status") == "booked")
    wants_reschedule = _looks_like_measurement_reschedule_request(text)

    if has_active_booking or measurement_date:
        lines = [f"Да, вижу запись на замер: {measurement_date or 'дата не указана'}."]
        if measurement_address:
            lines.append(f"Адрес: {measurement_address}.")
        if wants_reschedule:
            lines.append("Можем перенести. Показать свободные дни?")
        return "\n".join(lines)

    if wants_reschedule:
        return "Активной записи у вас пока не вижу. Можем записать на бесплатный замер — показать свободные окна?"
    return "Активной записи у вас пока не вижу. Можем записать на бесплатный замер, если удобно."


def _extract_measurement_context_from_text(text: str) -> tuple[str | None, str | None]:
    date_match = re.search(r"Дата:\s*([^\n]+)", text or "", flags=re.IGNORECASE)
    address_match = re.search(r"Адрес:\s*([^\n]+)", text or "", flags=re.IGNORECASE)
    date_text = date_match.group(1).strip(" .") if date_match else None
    address_text = address_match.group(1).strip(" .") if address_match else None
    return date_text, address_text


def _build_measurement_context_answer_from_parts(date_text: str | None, address_text: str | None) -> str | None:
    if not date_text and not address_text:
        return None
    lines = []
    if date_text:
        lines.append(f"Замер у нас записан на {date_text}.")
    if address_text:
        lines.append(f"Адрес: {address_text}.")
    lines.append("За сутки до замера напомним вам, чтобы ничего не потерялось.")
    lines.append("Если нужно перенести запись или исправить адрес, напишите здесь.")
    return "\n".join(lines)


async def _answer_measurement_question_if_possible(
    db: AsyncSession,
    message: Message,
    lead,
    text: str,
) -> bool:
    if not _looks_like_measurement_question(text):
        return False

    answer = _build_measurement_context_answer(lead, text)
    if not answer:
        history, _ = await chat_service.get_chat_history(db, lead.id, page_size=12)
        for chat_message in history:
            if chat_message.direction != MessageDirection.OUTBOUND:
                continue
            date_text, address_text = _extract_measurement_context_from_text(chat_message.content or "")
            answer = _build_measurement_context_answer_from_parts(date_text, address_text)
            if answer:
                break

    if not answer:
        return False

    sent = await message.answer(answer)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=answer,
        telegram_message_id=sent.message_id,
        sender_name="AI",
        ai_metadata={"source": "measurement_context", "skip_knowledge_index": True},
    )
    return True


def _lead_measurement_data(lead) -> dict:
    if not getattr(lead, "extracted_data", None):
        return {}
    try:
        data = json.loads(lead.extracted_data)
    except json.JSONDecodeError:
        return {}
    measurement = data.get("measurement") if isinstance(data, dict) else None
    return measurement if isinstance(measurement, dict) else {}


def _lead_quiz_data(lead) -> dict:
    if not getattr(lead, "extracted_data", None):
        return {}
    try:
        data = json.loads(lead.extracted_data)
    except json.JSONDecodeError:
        return {}
    quiz = data.get("quiz") if isinstance(data, dict) else None
    return quiz if isinstance(quiz, dict) else {}


def _lead_price_label(lead) -> str:
    quiz = _lead_quiz_data(lead)
    price = quiz.get("price") if isinstance(quiz, dict) else None
    if not isinstance(price, dict):
        return ""
    return str(price.get("label") or "").strip()


def _lead_quiz_answers(lead) -> dict:
    quiz = _lead_quiz_data(lead)
    answers = quiz.get("answers") if isinstance(quiz, dict) else None
    return answers if isinstance(answers, dict) else {}


def _lead_extracted_data(lead) -> dict:
    if not getattr(lead, "extracted_data", None):
        return {}
    try:
        data = json.loads(lead.extracted_data)
    except json.JSONDecodeError:
        return {}
    return data if isinstance(data, dict) else {}


def _lead_session_token(lead) -> str:
    data = _lead_extracted_data(lead)
    return str(data.get("quiz_session_token") or "").strip()


def _lead_quiz_summary_lines(lead) -> list[str]:
    answers = _lead_quiz_answers(lead)
    lines: list[str] = []
    for key, title in QUIZ_SUMMARY_FIELDS:
        raw_value = str(answers.get(key) or "").strip()
        if not raw_value:
            continue
        value = QUIZ_LABELS.get(key, {}).get(raw_value, raw_value)
        lines.append(f"{title}: {value}")
    return lines


def _build_quiz_estimate_text(lead) -> str:
    price_label = _lead_price_label(lead)
    if not price_label:
        return ""

    answers = _lead_quiz_answers(lead)
    summary = _lead_quiz_summary_lines(lead)
    text = (
        "Здравствуйте! Я Александр, менеджер компании ISAEV GROUP.\n\n"
        "Предварительная цена по работам без стройматериалов:\n"
        f"{price_label}"
    )
    if summary:
        text += "\n\n" + "\n".join(summary)

    design_answer = normalize_quiz_design_answer(answers.get("design"))
    if design_answer in {"yes", "wip"}:
        text += (
            "\n\n📎 Если пришлете сюда дизайн-проект файлом, мы спокойнее проверим объемы, "
            "чертежи и спорные места — так расчет по работам будет точнее."
        )
    else:
        text += (
            "\n\n📍 Чтобы не считать вслепую, лучше выбрать удобное время бесплатного замера. "
            "Инженер посмотрит объект, замерит нюансы и после этого мы точнее посчитаем работы."
        )
    return text


def _build_measurement_change_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="Дата/время", callback_data="quiz_measure_change:time"),
                InlineKeyboardButton(text="Адрес", callback_data="quiz_measure_change:address"),
            ],
            [InlineKeyboardButton(text="Телефон", callback_data="quiz_measure_change:phone")],
        ]
    )


async def _find_lead_by_telegram(db: AsyncSession, telegram_id: int):
    lead_result = await db.execute(
        select(Lead)
        .where(Lead.telegram_id == telegram_id)
        .order_by(Lead.updated_at.desc())
        .limit(1)
    )
    return lead_result.scalar_one_or_none()


async def _send_measurement_slot_dates(message: Message, db: AsyncSession, lead) -> bool:
    if not cal_pro_service.is_configured():
        text = (
            "Календарь сейчас не открылся. Напишите, пожалуйста, удобный день и время — "
            "менеджер вручную подберет ближайший слот и подтвердит запись 📍"
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "quiz_deep_link", "engine": "bot_template", "type": "measurement_slots_unavailable"},
        )
        return True

    try:
        slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
    except Exception:
        logger.warning("Failed to load measurement slots for lead %s", lead.id, exc_info=True)
        text = (
            "Календарь сейчас не загрузил свободные окна. Напишите, пожалуйста, удобный день и время — "
            "менеджер проверит расписание и подтвердит запись 📍"
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "quiz_deep_link", "engine": "bot_template", "type": "measurement_slots_error"},
        )
        return True
    if not slots:
        text = (
            "Свободные окна сейчас не загрузились. Напишите, пожалуйста, удобный день и время — "
            "менеджер проверит расписание и подтвердит запись 📍"
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "quiz_deep_link", "engine": "bot_template", "type": "measurement_slots_empty"},
        )
        return True

    text = (
        "Выберите удобный день бесплатного замера. "
        "Так мы спокойно посмотрим объект и посчитаем работы без догадок 📍"
    )
    sent = await message.answer(text, reply_markup=_build_measurement_date_keyboard(slots))
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "quiz_deep_link", "engine": "bot_template", "type": "measurement_slot_dates"},
    )
    return True


async def _send_measurement_reschedule_slot_dates(message: Message, db: AsyncSession, lead) -> bool:
    if not cal_pro_service.is_configured():
        text = (
            "Да, перенесем. Календарь сейчас не открылся — напишите удобный день и время, "
            "менеджер вручную подберет ближайший слот и подтвердит перенос."
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "measurement_reschedule", "engine": "bot_template", "type": "measurement_reschedule_slots_unavailable"},
        )
        return True

    try:
        slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
    except Exception:
        logger.warning("Failed to load reschedule slots for lead %s", lead.id, exc_info=True)
        text = (
            "Да, перенесем. Календарь сейчас не загрузил свободные окна — напишите удобный день и время, "
            "менеджер проверит расписание и подтвердит перенос."
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "measurement_reschedule", "engine": "bot_template", "type": "measurement_reschedule_slots_error"},
        )
        return True
    if not slots:
        text = (
            "Да, перенесем. Свободные окна сейчас не загрузились — напишите удобный день и время, "
            "менеджер проверит расписание и подтвердит перенос."
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "measurement_reschedule", "engine": "bot_template", "type": "measurement_reschedule_slots_empty"},
        )
        return True

    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    measurement["status"] = "awaiting_reschedule_slot"
    measurement["reschedule_requested_at"] = datetime.now(timezone.utc).isoformat()
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    await db.commit()

    text = "Да, конечно, перенесем. Выберите новый удобный день, чтобы инженеру было удобно приехать без спешки 📍"
    sent = await message.answer(text, reply_markup=_build_measurement_date_keyboard(slots))
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "measurement_reschedule", "engine": "bot_template", "type": "measurement_reschedule_slot_dates"},
    )
    return True


async def _send_measurement_change_choices(message: Message, db: AsyncSession, lead) -> bool:
    measurement = _lead_measurement_data(lead)
    measurement_date = _format_measurement_start(measurement.get("start"))
    measurement_address = str(measurement.get("address") or "").strip()
    text = "Конечно, изменим. Что нужно поправить по замеру?"
    if measurement_date or measurement_address or lead.phone:
        details = []
        if measurement_date:
            details.append(f"Дата: {measurement_date}")
        if measurement_address:
            details.append(f"Адрес: {measurement_address}")
        details.append(f"Телефон: {_format_phone(lead.phone or measurement.get('phone'))}")
        text = f"{text}\n\nСейчас записано:\n" + "\n".join(details)

    sent = await message.answer(text, reply_markup=_build_measurement_change_keyboard())
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "measurement_change", "engine": "bot_template", "type": "measurement_change_choices"},
    )
    return True


async def _send_measurement_acknowledgement(message: Message, db: AsyncSession, lead) -> bool:
    measurement = _lead_measurement_data(lead)
    measurement_date = _format_measurement_start(measurement.get("start"))
    measurement_address = str(measurement.get("address") or "").strip()
    text = "Отлично, тогда держим запись ✅"
    if measurement_date or measurement_address:
        details = []
        if measurement_date:
            details.append(f"Дата: {measurement_date}")
        if measurement_address:
            details.append(f"Адрес: {measurement_address}")
        text = f"{text}\n\n" + "\n".join(details)
    text = f"{text}\n\nЕсли нужно будет изменить дату, адрес или телефон — просто напишите сюда."
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "measurement_confirmation", "engine": "bot_template", "type": "measurement_acknowledgement"},
    )
    return True


async def _store_pending_measurement_slot(db: AsyncSession, lead, start: str) -> None:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    has_phone = bool(_normalize_phone(lead.phone or measurement.get("phone")))
    measurement.update(
        {
            "status": "awaiting_address" if has_phone else "awaiting_phone_for_measurement",
            "pending_start": start,
            "pending_slot_label": f"{_slot_date_button_label(_slot_date_key(start))} {_slot_time_label(start)}",
            "source": "telegram_inline_slots",
        }
    )
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    if lead.status in {
        LeadStatus.NEW.value,
        LeadStatus.QUIZ_COMPLETED.value,
        LeadStatus.MESSENGER_PENDING.value,
        LeadStatus.MEASUREMENT_PENDING.value,
    }:
        lead.status = LeadStatus.MEASUREMENT_PENDING.value
    await db.commit()


async def _set_pending_measurement_update(db: AsyncSession, lead, field: str) -> None:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    measurement["status"] = f"awaiting_{field}_update"
    measurement["update_requested_at"] = datetime.now(timezone.utc).isoformat()
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    await db.commit()


async def _confirm_measurement_reschedule(
    db: AsyncSession,
    query: CallbackQuery,
    lead,
    start: str,
) -> bool:
    session_token = _lead_session_token(lead)
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    address = str(measurement.get("address") or data.get("measurement_address") or data.get("address") or "").strip()

    if not address:
        await _store_pending_measurement_slot(db, lead, start)
        text = (
            f"Хорошо, держу новое окно {_slot_date_button_label(_slot_date_key(start))} "
            f"в {_slot_time_label(start)} ✅\n\n"
            "Напишите адрес объекта, чтобы я закрепил перенос замера."
        )
        if query.message:
            await query.message.edit_text(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=query.message.message_id if query.message else None,
            sender_name="AI",
            ai_metadata={"source": "measurement_reschedule", "type": "measurement_reschedule_address_request"},
        )
        return True

    from src.services.quiz_service import quiz_service

    previous_start = str(measurement.get("start") or "").strip()
    previous_booking_uid = str(measurement.get("booking_uid") or "").strip()
    measurement["reschedule_from"] = {
        "start": previous_start,
        "booking_uid": previous_booking_uid,
        "requested_at": measurement.get("reschedule_requested_at"),
    }
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    await db.commit()

    contact = QuizContact(
        name=lead.full_name or query.from_user.full_name or "Клиент квиза",
        phone=lead.phone,
        telegram_username=lead.username,
        preferred_messenger="telegram",
    )

    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_reschedule_requested",
        source="telegram_reschedule",
        event_data={
            "start": start,
            "previous_start": previous_start or None,
            "previous_booking_uid": previous_booking_uid or None,
            "has_address": bool(address),
        },
    )

    try:
        if previous_booking_uid:
            booking = await cal_pro_service.reschedule_booking(
                booking_uid=previous_booking_uid,
                start=start,
                rescheduled_by=contact.email,
                reason="Client requested measurement reschedule in Telegram",
            )
            booking_uid = quiz_service.extract_booking_uid(booking)
            data = _lead_extracted_data(lead)
            measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
            measurement.update(
                {
                    "start": start,
                    "status": "booked",
                    "address": address,
                    "phone": contact.phone,
                    "booking_uid": booking_uid,
                    "booking": booking.get("data") or booking,
                    "rescheduled_at": datetime.now(timezone.utc).isoformat(),
                    "source": "telegram_reschedule",
                }
            )
            data["measurement"] = measurement
            lead.extracted_data = json.dumps(data, ensure_ascii=False)
            lead.status = LeadStatus.MEASUREMENT_BOOKED.value
            await db.commit()
            await quiz_service._enqueue_measurement_reminder(
                db=db,
                lead=lead,
                start=start,
                address=address,
                booking_uid=booking_uid,
            )
        elif session_token:
            booking, _ = await quiz_service.book_measurement(
                db=db,
                payload=MeasurementBookingRequest(
                    session_token=session_token,
                    lead_id=lead.id,
                    start=start,
                    address=address,
                    contact=contact,
                    answers=_lead_quiz_answers(lead),
                    metadata={
                        "selected_slot_label": f"{_slot_date_button_label(_slot_date_key(start))} {_slot_time_label(start)}",
                        "selected_messenger": "telegram",
                        "measurement_address": address,
                        "source": "telegram_reschedule",
                        "previous_start": previous_start,
                        "previous_booking_uid": previous_booking_uid,
                    },
                ),
            )
            booking_uid = quiz_service.extract_booking_uid(booking)
        else:
            booking, booking_uid = await _book_measurement_directly(
                db=db,
                lead=lead,
                start=start,
                address=address,
                contact=contact,
                source="telegram_reschedule_direct",
            )
    except Exception:
        logger.warning("Failed to reschedule Telegram measurement for lead %s", lead.id, exc_info=True)
        await measurement_analytics_service.record_event(
            db=db,
            lead=lead,
            event_type="measurement_reschedule_failed",
            source="telegram_reschedule",
            event_data={
                "start": start,
                "previous_start": previous_start or None,
                "previous_booking_uid": previous_booking_uid or None,
                "has_address": bool(address),
            },
        )
        text = (
            "Новое окно выбрали, но календарь сейчас не закрепил перенос автоматически. "
            "Менеджер проверит слот вручную и подтвердит вам здесь."
        )
        if query.message:
            await query.message.edit_text(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=query.message.message_id if query.message else None,
            sender_name="AI",
            ai_metadata={"source": "measurement_reschedule", "type": "measurement_reschedule_error"},
        )
        return True

    text = (
        "Готово, перенесли замер ✅\n\n"
        f"Новая дата: {_slot_date_button_label(_slot_date_key(start))} в {_slot_time_label(start)}\n"
        f"Адрес: {address}\n"
        f"Телефон для связи: {_format_phone(contact.phone)}\n\n"
        "За сутки до замера напомним вам, чтобы ничего не потерялось. "
        "Если нужно изменить дату, адрес или телефон — напишите сюда."
    )
    if query.message:
        await query.message.edit_text(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=query.message.message_id if query.message else None,
        sender_name="AI",
        ai_metadata={
            "source": "measurement_reschedule",
            "type": "measurement_reschedule_confirmed",
            "booking_uid": booking_uid,
            "previous_booking_uid": previous_booking_uid,
        },
    )
    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_rescheduled",
        source="telegram_reschedule",
        event_data={
            "start": start,
            "booking_uid": booking_uid or None,
            "previous_start": previous_start or None,
            "previous_booking_uid": previous_booking_uid or None,
            "has_address": bool(address),
        },
    )
    return True


async def _book_measurement_directly(
    db: AsyncSession,
    lead,
    *,
    start: str,
    address: str,
    contact: QuizContact,
    source: str,
) -> tuple[dict, str | None]:
    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_booking_requested",
        source=source,
        event_data={
            "start": start,
            "has_address": bool(address),
        },
    )
    booking = await cal_pro_service.create_booking(
        start=start,
        contact=contact,
        answers=_lead_quiz_answers(lead),
        metadata={
            "selected_slot_label": f"{_slot_date_button_label(_slot_date_key(start))} {_slot_time_label(start)}",
            "selected_messenger": "telegram",
            "measurement_address": address,
            "lead_id": str(lead.id),
            "source": source,
        },
    )
    booking_uid = str(cal_pro_service._extract_booking_uid(booking) or "").strip()
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    measurement.update(
        {
            "start": start,
            "status": "booked" if booking_uid else "requested",
            "address": address,
            "phone": contact.phone,
            "booking_uid": booking_uid,
            "booking": booking.get("data") or booking,
            "booked_at": datetime.now(timezone.utc).isoformat(),
            "source": source,
        }
    )
    data["measurement"] = measurement
    data["measurement_address"] = address
    data["address"] = address
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    lead.status = LeadStatus.MEASUREMENT_BOOKED.value if booking_uid else LeadStatus.MEASUREMENT_PENDING.value
    await db.commit()
    await db.refresh(lead)

    try:
        from src.services.quiz_service import quiz_service

        await quiz_service._enqueue_measurement_reminder(
            db=db,
            lead=lead,
            start=start,
            address=address,
            booking_uid=booking_uid,
        )
    except Exception:
        logger.warning("Failed to enqueue direct measurement reminder for lead %s", lead.id, exc_info=True)

    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_booked" if booking_uid else "measurement_booking_uid_missing",
        source=source,
        event_data={
            "start": start,
            "booking_uid": booking_uid or None,
            "has_address": bool(address),
        },
    )
    return booking, booking_uid


async def _pop_pending_measurement_slot(db: AsyncSession, lead) -> str:
    await db.refresh(lead)
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    start = str(measurement.get("pending_start") or "").strip()
    if not start:
        return ""
    measurement.pop("pending_start", None)
    measurement.pop("pending_slot_label", None)
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    await db.commit()
    return start


async def _try_handle_pending_measurement_update(
    db: AsyncSession,
    message: Message,
    lead,
    text_value: str,
) -> bool:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    status = str(measurement.get("status") or "")

    if status == "awaiting_address_update":
        clean_address = text_value.strip()
        if len(clean_address) < 5:
            text = "Похоже, адрес получился неполным. Напишите, пожалуйста: город, улицу, дом и квартиру/офис."
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="AI",
                ai_metadata={"source": "measurement_change", "type": "measurement_address_update_retry"},
            )
            return True

        old_address = str(measurement.get("address") or data.get("measurement_address") or "").strip()
        measurement["address"] = clean_address
        measurement["status"] = "booked" if measurement.get("start") else "address_updated"
        measurement["address_updated_at"] = datetime.now(timezone.utc).isoformat()
        data["measurement"] = measurement
        data["address"] = clean_address
        data["measurement_address"] = clean_address
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()

        date_text = _format_measurement_start(measurement.get("start"))
        text = (
            "Готово, адрес замера обновил ✅\n\n"
            f"Дата: {date_text or 'не выбрана'}\n"
            f"Адрес: {clean_address}\n"
            f"Телефон для связи: {_format_phone(lead.phone or measurement.get('phone'))}"
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={
                "source": "measurement_change",
                "type": "measurement_address_updated",
                "crm_tool_action": "update_measurement_address",
                "tool_call": {
                    "action": "update_measurement_address",
                    "channel": _telegram_tool_channel(message),
                },
                "old_address": old_address,
            },
        )
        return True

    if status == "awaiting_phone_update":
        normalized_phone = _normalize_phone(text_value)
        if not normalized_phone:
            text = "Похоже, номер не распознал. Напишите, пожалуйста, телефон в формате +7..."
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="AI",
                ai_metadata={"source": "measurement_change", "type": "measurement_phone_update_retry"},
            )
            return True

        old_phone = lead.phone
        lead.phone = normalized_phone
        measurement["phone"] = normalized_phone
        measurement["status"] = "booked" if measurement.get("start") else "phone_updated"
        measurement["phone_updated_at"] = datetime.now(timezone.utc).isoformat()
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()

        date_text = _format_measurement_start(measurement.get("start"))
        address = str(measurement.get("address") or data.get("measurement_address") or data.get("address") or "").strip()
        text = (
            "Готово, телефон для связи обновил ✅\n\n"
            f"Дата: {date_text or 'не выбрана'}\n"
            f"Адрес: {address or 'не указан'}\n"
            f"Телефон для связи: {_format_phone(normalized_phone)}"
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={
                "source": "measurement_change",
                "type": "measurement_phone_updated",
                "old_phone": old_phone,
            },
        )
        return True

    return False


async def _try_handle_pending_measurement_address(
    db: AsyncSession,
    message: Message,
    lead,
    address: str,
) -> bool:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    pending_start = str(measurement.get("pending_start") or "").strip()
    if measurement.get("status") == "awaiting_phone_for_measurement" and pending_start:
        normalized_phone = _normalize_phone(address)
        if not normalized_phone:
            text = "Чтобы закрепить замер, нужен телефон для связи. Напишите, пожалуйста, номер в формате +7..."
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="AI",
                ai_metadata={"source": "telegram_inline_slots", "type": "measurement_phone_retry"},
            )
            return True

        lead.phone = normalized_phone
        measurement["phone"] = normalized_phone
        measurement["status"] = "awaiting_address"
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()

        text = "Спасибо, телефон сохранил. Теперь напишите адрес объекта: город, улицу, дом и квартиру/офис."
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={"source": "telegram_inline_slots", "type": "measurement_address_request_after_phone"},
        )
        return True

    if measurement.get("status") != "awaiting_address" or not pending_start:
        return False

    clean_address = address.strip()
    corrected_address = _extract_direct_address_correction(clean_address)
    if corrected_address:
        clean_address = corrected_address

    if _looks_like_address_or_booking_question(clean_address):
        answer = _build_measurement_status_answer(lead, clean_address)
        sent = await message.answer(answer)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=answer,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "bot_scenario", "type": "pending_measurement_question"},
        )
        return True

    if len(clean_address) < 5:
        text = "Похоже, адрес получился неполным. Напишите, пожалуйста: город, улицу, дом и квартиру/офис."
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={"source": "telegram_inline_slots", "type": "measurement_address_retry"},
        )
        return True

    session_token = _lead_session_token(lead)

    contact = QuizContact(
        name=lead.full_name or message.from_user.full_name or "Клиент квиза",
        phone=lead.phone,
        telegram_username=lead.username,
        preferred_messenger="telegram",
    )
    try:
        if session_token:
            from src.services.quiz_service import quiz_service

            booking, _ = await quiz_service.book_measurement(
                db=db,
                payload=MeasurementBookingRequest(
                    session_token=session_token,
                    lead_id=lead.id,
                    start=pending_start,
                    address=clean_address,
                    contact=contact,
                    answers=_lead_quiz_answers(lead),
                    metadata={
                        "selected_slot_label": f"{_slot_date_button_label(_slot_date_key(pending_start))} {_slot_time_label(pending_start)}",
                        "selected_messenger": "telegram",
                        "measurement_address": clean_address,
                        "source": "telegram_inline_slots",
                    },
                ),
            )
            booking_uid = quiz_service.extract_booking_uid(booking)
        else:
            booking, booking_uid = await _book_measurement_directly(
                db=db,
                lead=lead,
                start=pending_start,
                address=clean_address,
                contact=contact,
                source="telegram_inline_slots_direct",
            )
    except Exception:
        logger.warning("Failed to book Telegram measurement slot for lead %s", lead.id, exc_info=True)
        await measurement_analytics_service.record_event(
            db=db,
            lead=lead,
            event_type="measurement_booking_failed",
            source="telegram_inline_slots",
            event_data={
                "start": pending_start,
                "has_address": bool(clean_address),
            },
        )
        text = (
            "Адрес сохранил. Календарь сейчас не закрепил слот автоматически — "
            "выберите, пожалуйста, другое окно. Если не получится, менеджер поможет записаться вручную."
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={"source": "telegram_inline_slots", "type": "measurement_booking_error"},
        )
        return True

    await _pop_pending_measurement_slot(db, lead)
    booked = bool(booking_uid) or booking.get("status") == "ok"
    text = (
        "Готово, записали вас на замер ✅\n\n"
        f"Дата: {_slot_date_button_label(_slot_date_key(pending_start))} в {_slot_time_label(pending_start)}\n"
        f"Адрес: {clean_address}\n"
        f"Телефон для связи: {_format_phone(contact.phone)}\n\n"
        "Бронь закреплена в календаре. За сутки до замера напомним вам, чтобы ничего не потерялось. "
        "Если нужно изменить дату, адрес или телефон — напишите сюда."
        if booked
        else
        "Заявку на замер сохранили ✅\n\n"
        f"Дата: {_slot_date_button_label(_slot_date_key(pending_start))} в {_slot_time_label(pending_start)}\n"
        f"Адрес: {clean_address}\n"
        f"Телефон для связи: {_format_phone(contact.phone)}\n\n"
        "Календарь не подтвердил бронь автоматически. Выберите другое окно, а если не получится — менеджер поможет вручную."
    )
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="AI",
        ai_metadata={
            "source": "telegram_inline_slots",
            "type": "measurement_booking_confirmed" if booked else "measurement_booking_requested",
            "booking_uid": booking_uid,
        },
    )
    return True


async def _handle_direct_measurement_address_correction(
    db: AsyncSession,
    message: Message,
    lead,
    address: str,
) -> bool:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    if not measurement.get("start") and not measurement.get("booking_uid"):
        return False

    old_address = str(measurement.get("address") or data.get("measurement_address") or data.get("address") or "").strip()
    measurement["address"] = address
    measurement["address_updated_at"] = datetime.now(timezone.utc).isoformat()
    measurement["address_update_source"] = "telegram_direct_correction"
    data["measurement"] = measurement
    data["address"] = address
    data["measurement_address"] = address
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    await db.commit()

    date_text = _format_measurement_start(measurement.get("start"))
    text = (
        "Да, поправил адрес замера ✅\n\n"
        f"Дата: {date_text or 'не выбрана'}\n"
        f"Адрес: {address}\n"
        f"Телефон для связи: {_format_phone(lead.phone or measurement.get('phone'))}"
    )
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={
            "source": "bot_scenario",
            "type": "measurement_address_directly_updated",
            "crm_tool_action": "update_measurement_address",
            "tool_call": {
                "action": "update_measurement_address",
                "channel": _telegram_tool_channel(message),
            },
            "old_address": old_address,
        },
    )
    return True


async def _quiz_estimate_already_sent(db: AsyncSession, lead_id: uuid.UUID, session_token: str) -> bool:
    result = await db.execute(select(ChatMessage).where(ChatMessage.lead_id == lead_id))
    for chat_message in result.scalars().all():
        metadata = chat_message.ai_metadata if isinstance(chat_message.ai_metadata, dict) else {}
        if (
            metadata.get("type") == "quiz_estimate_after_activation"
            and metadata.get("session_token") == session_token
        ):
            return True
    return False


async def _handle_quiz_lead_activation_flow(
    message: Message,
    db: AsyncSession,
    lead,
    session_token: str | None = None,
    source: str = "quiz_deep_link",
) -> bool:
    """
    Continue the quiz flow for a linked lead.
    This also handles plain /start when Telegram opens the bot without the qz_ payload.
    """
    session_token = (session_token or _lead_session_token(lead) or str(lead.id)).strip()
    estimate_text = _build_quiz_estimate_text(lead)
    if not estimate_text:
        return False

    from src.services.lead_stage_context_service import lead_stage_context_service
    stage_context = await lead_stage_context_service.build_context(db=db, lead=lead)
    next_action = stage_context.metadata.get("next_action")

    if not await _quiz_estimate_already_sent(db, lead.id, session_token):
        sent_estimate = await message.answer(estimate_text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=estimate_text,
            telegram_message_id=sent_estimate.message_id,
            sender_name="Bot",
            ai_metadata={
                "source": source,
                "engine": "bot_template",
                "type": "quiz_estimate_after_activation",
                "session_token": session_token,
                "stage_context": stage_context.metadata,
            },
        )

    if next_action == "awaiting_design_project":
        welcome_text = (
            "Следующий шаг — пришлите сюда дизайн-проект файлом 📎\n\n"
            "Мы спокойно проверим объемы, чертежи и спорные места, "
            "чтобы точнее рассчитать работы без стройматериалов."
        )
    elif next_action == "awaiting_measurement_slot":
        if await _send_measurement_slot_dates(message, db, lead):
            return True
        welcome_text = (
            "Можно выбрать другое окно или написать удобный день и время. "
            "Подберем ближайший свободный слот для бесплатного замера 📍"
        )
    elif next_action == "confirm_measurement":
        measurement = _lead_measurement_data(lead)
        measurement_date = _format_measurement_start(measurement.get("start"))
        measurement_address = str(measurement.get("address") or "").strip()
        if measurement_date and measurement_address:
            status_label = "замер записан" if measurement.get("status") == "booked" else "слот замера выбран"
            welcome_text = (
                f"Здравствуйте! Вижу, что {status_label}: {measurement_date}.\n"
                f"Адрес: {measurement_address}\n"
                f"Телефон для связи: {_format_phone(lead.phone or measurement.get('phone'))}\n\n"
                "Запись закреплена в календаре ✅\n"
                "За сутки до замера напомним вам спокойно, чтобы ничего не потерялось. "
                "Если нужно изменить дату, адрес или телефон — напишите сюда."
            )
        elif measurement_date:
            welcome_text = (
                f"Здравствуйте! Вижу выбранный слот замера: {measurement_date}.\n\n"
                "Напишите, пожалуйста, адрес объекта — так инженер заранее поймет, куда ехать, и мы подтвердим выезд 📍"
            )
        else:
            if await _send_measurement_slot_dates(message, db, lead):
                return True
            welcome_text = (
                "Чтобы спокойно подобрать замер, напишите удобный день и время — "
                "проверим ближайший свободный слот и подтвердим запись 📍"
            )
    else:
        welcome_text = (
            "Здравствуйте! Вижу вашу заявку по квизу.\n\n"
            "Напишите сюда любой вопрос — продолжим по вашим данным и подскажем понятный следующий шаг."
        )

    if not is_business_hours():
        welcome_text = f"{welcome_text}\n\nСейчас команда не на связи. Ответим в рабочее время 🕘"

    sent_message = await message.answer(welcome_text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=welcome_text,
        telegram_message_id=sent_message.message_id,
        sender_name="Bot",
        ai_metadata={"source": source, "engine": "bot_template", "stage_context": stage_context.metadata},
    )
    return True


async def _send_quiz_token_fallback(
    message: Message,
    db: AsyncSession,
    lead,
    session_token: str,
    source: str,
) -> bool:
    text = (
        "Вижу код вашей заявки по квизу ✅\n\n"
        "Сейчас данные анкеты не подтянулись автоматически, но сообщение получили. "
        "Чтобы не терять время: если дизайн-проекта нет, напишите удобный день и время для бесплатного замера. "
        "Если проект есть — можно прикрепить его сюда файлом."
    )
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={
            "source": source,
            "engine": "bot_template",
            "type": "quiz_token_activation_fallback",
            "session_token": session_token,
        },
    )
    return True


async def _send_manager_handoff_notice(message: Message, db: AsyncSession, lead) -> bool:
    lead.ai_qualification_status = "handoff_required"
    if lead.status in {LeadStatus.NEW.value, LeadStatus.QUIZ_COMPLETED.value, LeadStatus.MESSENGER_PENDING.value}:
        lead.status = LeadStatus.QUALIFIED.value
    await db.commit()

    text = (
        "Передал менеджеру вашу заявку ✅\n"
        "Он увидит переписку и подключится с контекстом. Если вопрос срочный, напишите его сюда одним сообщением."
    )
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "bot_scenario", "type": "manager_handoff_requested"},
    )
    return True


def _measurement_has_active_booking(measurement: dict) -> bool:
    status = str(measurement.get("status") or "").strip().lower()
    return bool(measurement.get("booking_uid")) and status not in {"cancelled", "cancel_requested"}


def _set_lead_conversation_mode(lead, mode: str, reason: str) -> dict:
    data = _lead_extracted_data(lead)
    data["conversation_mode"] = mode
    data["conversation_mode_reason"] = reason
    data["conversation_mode_updated_at"] = datetime.now(timezone.utc).isoformat()
    data["do_not_contact"] = mode == "do_not_contact"
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    return data


async def _handle_measurement_cancel_request(
    db: AsyncSession,
    message: Message,
    lead,
    reason: str = "Client requested measurement cancellation in Telegram",
    final_lost: bool = False,
) -> bool:
    data = _lead_extracted_data(lead)
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    booking_uid = str(measurement.get("booking_uid") or "").strip()
    measurement_date = _format_measurement_start(measurement.get("start"))
    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_cancel_requested",
        source="telegram_cancel",
        event_data={
            "start": measurement.get("start"),
            "booking_uid": booking_uid or None,
            "final_lost": final_lost,
        },
    )

    if not booking_uid:
        measurement["status"] = "cancelled" if measurement.get("start") else "cancel_requested"
        measurement["cancel_requested_at"] = datetime.now(timezone.utc).isoformat()
        measurement["cancel_reason"] = reason
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        if final_lost:
            lead.status = LeadStatus.LOST.value
            lead.ai_qualification_status = "not_interested"
        elif lead.status in {LeadStatus.MEASUREMENT_BOOKED.value, LeadStatus.MEASUREMENT.value, LeadStatus.MEASUREMENT_PENDING.value}:
            lead.status = LeadStatus.CONSULTING.value
        await db.commit()

        text = (
            f"Принял, замер{f' на {measurement_date}' if measurement_date else ''} отменил в CRM. "
            "В календаре не нашел активный номер брони, поэтому менеджер дополнительно проверит вручную."
        )
        if final_lost:
            text += " Больше не будем беспокоить."
        else:
            text += "\n\nЕсли захотите перенести на другой день, напишите сюда."
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "bot_scenario", "type": "measurement_cancel_no_booking_uid"},
        )
        await measurement_analytics_service.record_event(
            db=db,
            lead=lead,
            event_type="measurement_cancelled" if measurement.get("start") else "measurement_cancel_pending",
            source="telegram_cancel",
            event_data={
                "start": measurement.get("start"),
                "booking_uid": None,
                "final_lost": final_lost,
            },
        )
        return True

    try:
        cancel_response = await cal_pro_service.cancel_booking(booking_uid=booking_uid, reason=reason)
    except Exception:
        logger.warning("Failed to cancel Cal Pro booking for lead %s", lead.id, exc_info=True)
        measurement["status"] = "cancel_requested"
        measurement["cancel_requested_at"] = datetime.now(timezone.utc).isoformat()
        measurement["cancel_reason"] = reason
        data["measurement"] = measurement
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        lead.ai_qualification_status = "handoff_required"
        await db.commit()

        text = (
            "Принял запрос на отмену замера, но календарь не подтвердил отмену автоматически. "
            "Передал менеджеру для ручной проверки брони."
        )
        if final_lost:
            text += " Больше не будем беспокоить."
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "bot_scenario", "type": "measurement_cancel_failed", "booking_uid": booking_uid},
        )
        await measurement_analytics_service.record_event(
            db=db,
            lead=lead,
            event_type="measurement_cancel_failed",
            source="telegram_cancel",
            event_data={
                "start": measurement.get("start"),
                "booking_uid": booking_uid,
                "final_lost": final_lost,
            },
        )
        return True

    measurement["status"] = "cancelled"
    measurement["cancelled_at"] = datetime.now(timezone.utc).isoformat()
    measurement["cancel_reason"] = reason
    measurement["cancel_response"] = cancel_response.get("data") or cancel_response
    data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    if final_lost:
        lead.status = LeadStatus.LOST.value
        lead.ai_qualification_status = "not_interested"
    elif lead.status in {LeadStatus.MEASUREMENT_BOOKED.value, LeadStatus.MEASUREMENT.value, LeadStatus.MEASUREMENT_PENDING.value}:
        lead.status = LeadStatus.CONSULTING.value
    await db.commit()

    text = f"Готово, замер{f' на {measurement_date}' if measurement_date else ''} отменил в календаре."
    if final_lost:
        text += " Больше не будем беспокоить."
    else:
        text += "\n\nХотите перенести на другой день или пока отложим ремонт?"
    sent = await message.answer(text)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=text,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={
            "source": "bot_scenario",
            "type": "measurement_cancelled",
            "booking_uid": booking_uid,
        },
    )
    await measurement_analytics_service.record_event(
        db=db,
        lead=lead,
        event_type="measurement_cancelled",
        source="telegram_cancel",
        event_data={
            "start": measurement.get("start"),
            "booking_uid": booking_uid,
            "final_lost": final_lost,
        },
    )
    return True


async def _handle_not_interested(
    db: AsyncSession,
    message: Message,
    lead,
    text_value: str,
) -> bool:
    data = _set_lead_conversation_mode(lead, "not_interested", text_value[:300])
    lead.status = LeadStatus.LOST.value
    lead.ai_qualification_status = "not_interested"
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    if _measurement_has_active_booking(measurement):
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()
        return await _handle_measurement_cancel_request(
            db=db,
            message=message,
            lead=lead,
            reason="Client declined renovation after booking",
            final_lost=True,
        )

    await db.commit()
    reply = "Понял вас. Зафиксировал отказ, больше не будем вас беспокоить. Всего доброго."
    sent = await message.answer(reply)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=reply,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "bot_scenario", "type": "lead_not_interested"},
    )
    return True


async def _handle_do_not_contact(
    db: AsyncSession,
    message: Message,
    lead,
    text_value: str,
) -> bool:
    data = _set_lead_conversation_mode(lead, "do_not_contact", text_value[:300])
    lead.status = LeadStatus.LOST.value
    lead.ai_qualification_status = "not_interested"
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    if _measurement_has_active_booking(measurement):
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        await db.commit()
        return await _handle_measurement_cancel_request(
            db=db,
            message=message,
            lead=lead,
            reason="Client requested do-not-contact after booking",
            final_lost=True,
        )

    await db.commit()

    reply = "Понял, больше не будем вас беспокоить. Всего доброго."
    sent = await message.answer(reply)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=reply,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "bot_scenario", "type": "do_not_contact"},
    )
    return True


async def _handle_abusive_message(
    db: AsyncSession,
    message: Message,
    lead,
    text_value: str,
) -> bool:
    data = _lead_extracted_data(lead)
    if data.get("do_not_contact"):
        logger.info("Ignoring abusive message after do-not-contact for lead %s", lead.id)
        return True

    _set_lead_conversation_mode(lead, "abusive", text_value[:300])
    lead.status = LeadStatus.LOST.value
    lead.ai_qualification_status = "not_interested"
    await db.commit()

    reply = "Понял, больше не беспокоим."
    sent = await message.answer(reply)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=reply,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "bot_scenario", "type": "abusive_lead_closed"},
    )
    return True


async def _handle_reactivation(
    db: AsyncSession,
    message: Message,
    lead,
    text_value: str,
) -> bool:
    data = _lead_extracted_data(lead)
    data["conversation_mode"] = "reactivated"
    data["conversation_mode_reason"] = text_value[:300]
    data["conversation_mode_updated_at"] = datetime.now(timezone.utc).isoformat()
    data["do_not_contact"] = False
    measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
    if measurement.get("status") in {"cancelled", "cancel_requested"}:
        measurement["status"] = "reactivated"
        measurement["reactivated_at"] = datetime.now(timezone.utc).isoformat()
        data["measurement"] = measurement
    lead.extracted_data = json.dumps(data, ensure_ascii=False)
    lead.status = LeadStatus.MEASUREMENT_PENDING.value
    lead.ai_qualification_status = "in_progress"
    await db.commit()

    intro = (
        "Да, вижу переписку. Продолжаем спокойно: лучше снова подобрать время бесплатного замера, "
        "чтобы посчитать работы не вслепую."
    )
    sent = await message.answer(intro)
    await chat_service.send_outbound_message(
        db=db,
        lead_id=lead.id,
        content=intro,
        telegram_message_id=sent.message_id,
        sender_name="Bot",
        ai_metadata={"source": "bot_scenario", "type": "lead_reactivated"},
    )
    await _send_measurement_slot_dates(message, db, lead)
    return True


def _build_ai_support_tools_prompt(stage_context) -> str:
    next_action = stage_context.metadata.get("next_action") if stage_context else "unknown"
    return f"""
SCENARIO_ORCHESTRATION:
- Главный сценарий ведет бот. ИИ только отвечает на вопросы поддержки, возражения и боковые уточнения.
- Тон ИИ: заботливый живой менеджер, который продает через ясность. Спокойно, понятно, без давления, срочности, рекламных лозунгов и ощущения скрипта.
- Не дави, но веди. Если вопрос клиента закрыт, не оставляй диалог в воздухе: предложи один конкретный следующий шаг.
- Следующий шаг объясняй через пользу клиенту: меньше сюрпризов, точнее расчет, понятнее сроки, спокойнее подготовка ремонта.
- Если клиент просит действие, не обещай выполнить его текстом. Верни tool_action в JSON, чтобы backend вызвал инструмент.
- Если клиент просит записаться, выбрать время, календарь, слот или замер: tool_action = "show_measurement_slots".
- Если клиент просит перенести существующий замер: tool_action = "reschedule_measurement".
- Если клиент просит отменить существующий замер: tool_action = "cancel_measurement".
- Если клиент просит изменить дату, адрес, телефон или данные брони: tool_action = "change_measurement_booking".
- Если клиент просит прислать, повторить, скинуть или найти готовую смету файлом: tool_action = "send_final_estimate".
- Если клиент спрашивает сумму, итог, позиции или содержимое сметы-файла: не делай вид, что прочитал файл; ответь, что передашь вопрос менеджеру/сметчику, tool_action = "none".
- Если клиент спрашивает, есть ли у него запись на замер, на какое число/время записан или какой адрес в записи: tool_action = "read_measurement_booking".
- Если клиент спрашивает статус сметы, готова ли смета, где расчет, но не просит именно файл: tool_action = "read_estimate_status".
- Если клиент спрашивает, какие данные по заявке уже есть в CRM: tool_action = "read_lead_summary".
- Если клиент просит менеджера/оператора/живого человека: tool_action = "handoff_to_manager".
- Если клиент спрашивает портфолио, кейсы, примеры работ, фото, отзывы, гарантии, оплату, сроки, материалы или цены: ответь в message и ставь tool_action = "none".
- Если клиент отказался от ремонта или просит больше не писать: tool_action = "none", status = "LOST", message должен быть коротким без продолжения продажи.
- Если клиент сам вернулся после отказа: tool_action = "show_measurement_slots".
- Если клиент спрашивает о компании, процессе ремонта, гарантиях, оплате, сроках, материалах или цене: отвечай в message и мягко возвращай к next_action.
- Не выводи клиенту названия инструментов, JSON, markdown-блоки или рассуждения.
- Текущий next_action CRM: {next_action}.

AVAILABLE_TOOL_ACTIONS:
- show_measurement_slots
- reschedule_measurement
- cancel_measurement
- change_measurement_booking
- send_final_estimate
- read_measurement_booking
- read_estimate_status
- read_lead_summary
- handoff_to_manager
- none

JSON_CONTRACT:
{{
  "message": "короткий ответ клиенту, если это вопрос поддержки",
  "tool_action": "none",
  "status": "CONSULTING",
  "is_hot_lead": false,
  "confidence": 50
}}
"""


def _extract_ai_tool_action(extracted_data: dict | None) -> str:
    if not isinstance(extracted_data, dict):
        return ""
    raw_action = (
        extracted_data.get("tool_action")
        or extracted_data.get("tool")
        or extracted_data.get("action")
        or extracted_data.get("requested_tool")
    )
    if isinstance(raw_action, dict):
        raw_action = raw_action.get("name") or raw_action.get("action")
    action = str(raw_action or "").strip().lower()
    aliases = {
        "calendar": "show_measurement_slots",
        "show_calendar": "show_measurement_slots",
        "booking_slots": "show_measurement_slots",
        "book_measurement": "show_measurement_slots",
        "measurement_slots": "show_measurement_slots",
        "cancel_booking": "cancel_measurement",
        "cancel_measurement_booking": "cancel_measurement",
        "cancel_measurement_slots": "cancel_measurement",
        "update_measurement_data": "change_measurement_booking",
        "change_booking": "change_measurement_booking",
        "estimate": "send_final_estimate",
        "send_estimate": "send_final_estimate",
        "send_final_estimate_file": "send_final_estimate",
        "resend_estimate": "send_final_estimate",
        "repeat_estimate": "send_final_estimate",
        "final_estimate": "send_final_estimate",
        "measurement_booking": "read_measurement_booking",
        "booking_status": "read_measurement_booking",
        "read_booking": "read_measurement_booking",
        "get_booking": "read_measurement_booking",
        "estimate_status": "read_estimate_status",
        "read_estimate": "read_estimate_status",
        "lead_summary": "read_lead_summary",
        "read_lead": "read_lead_summary",
        "crm_lead": "read_lead_summary",
        "manager_handoff": "handoff_to_manager",
        "human_handoff": "handoff_to_manager",
        "operator_handoff": "handoff_to_manager",
    }
    action = aliases.get(action, action)
    return action if action not in {"", "none", "null", "answer_support"} else ""


async def _execute_ai_tool_action(
    db: AsyncSession,
    message: Message,
    lead,
    action: str,
    args: dict | None = None,
) -> bool:
    args = args or {}
    if action == "show_measurement_slots":
        if _lead_measurement_data(lead).get("start"):
            text = _build_measurement_status_answer(lead, "запись")
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="Bot",
                ai_metadata=_crm_tool_message_metadata(
                    message,
                    action,
                    "measurement_existing_booking_guard",
                    source="bot_scenario",
                ),
            )
            return True
        return await _send_measurement_slot_dates(message, db, lead)

    if action == "update_measurement_address":
        address = str(args.get("measurement_address") or args.get("address") or "").strip()
        if address and await _handle_direct_measurement_address_correction(db, message, lead, address):
            return True
        measurement = _lead_measurement_data(lead)
        if measurement.get("start"):
            await _set_pending_measurement_update(db, lead, "address")
            text = "Напишите новый адрес объекта: город, улицу, дом и квартиру/офис."
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="Bot",
                ai_metadata=_crm_tool_message_metadata(message, action, "measurement_address_update_request"),
            )
            return True
        return False

    if action == "reschedule_measurement":
        measurement = _lead_measurement_data(lead)
        if measurement.get("start"):
            return await _send_measurement_reschedule_slot_dates(message, db, lead)
        return await _send_measurement_slot_dates(message, db, lead)

    if action == "cancel_measurement":
        measurement = _lead_measurement_data(lead)
        if measurement.get("start") or measurement.get("booking_uid"):
            return await _handle_measurement_cancel_request(db, message, lead)
        return False

    if action == "change_measurement_booking":
        measurement = _lead_measurement_data(lead)
        if measurement.get("start"):
            return await _send_measurement_change_choices(message, db, lead)
        return await _send_measurement_slot_dates(message, db, lead)

    if action == "send_final_estimate":
        return await send_ready_estimate_from_crm(db, message, lead)

    if action == "read_measurement_booking":
        return await answer_measurement_booking(db, message, lead)

    if action == "read_estimate_status":
        return await answer_estimate_status(db, message, lead)

    if action == "read_lead_summary":
        return await answer_lead_summary(db, message, lead)

    if action == "handoff_to_manager":
        return await _send_manager_handoff_notice(message, db, lead)

    return False


def _crm_tool_message_metadata(
    message: Message,
    action: str,
    tool_type: str,
    *,
    source: str = "crm_tool",
) -> dict:
    return {
        "source": source,
        "type": tool_type,
        "crm_tool_action": action,
        "tool_call": {
            "action": action,
            "channel": _telegram_tool_channel(message),
        },
    }


def _telegram_tool_channel(message: Message) -> str:
    return "telegram_business" if getattr(message, "business_connection_id", None) else "telegram"


async def _try_execute_llm_crm_tool(
    db: AsyncSession,
    message: Message,
    lead,
    text: str,
    stage_context,
    config=None,
) -> bool:
    decision = await choose_crm_tool(
        lead=lead,
        user_text=text,
        stage_context=stage_context,
        model=getattr(config, "llm_model", None) if config else None,
        trace_id=f"crm_tool_router_{lead.id}",
        user_id=str(message.from_user.id),
    )
    logger.info(
        "CRM tool router: lead_id=%s action=%s confidence=%s reason=%s args=%s",
        lead.id,
        decision.action,
        decision.confidence,
        decision.reason,
        decision.args,
    )
    tool_call = await agent_tool_log_service.create_call(
        db,
        lead=lead,
        user_message=text,
        action=decision.action,
        confidence=decision.confidence,
        reason=decision.reason,
        args=decision.args,
        strict_schema=decision.strict_schema,
    )
    if not decision.should_execute:
        await agent_tool_log_service.mark_result(
            db,
            tool_call,
            executed=False,
            result="skipped_low_confidence" if decision.action != "none" else "none",
        )
        return False
    try:
        executed = await _execute_ai_tool_action(db, message, lead, decision.action, decision.args)
    except Exception as exc:
        await agent_tool_log_service.mark_result(
            db,
            tool_call,
            executed=False,
            result="error",
            error=str(exc),
        )
        raise
    await agent_tool_log_service.mark_result(
        db,
        tool_call,
        executed=executed,
        result="executed" if executed else "not_applicable",
    )
    return executed


async def _try_route_scenario_before_ai(
    db: AsyncSession,
    message: Message,
    lead,
    text: str,
    stage_context,
) -> bool:
    next_action = stage_context.metadata.get("next_action") if stage_context else ""
    measurement_data = _lead_measurement_data(lead)

    if _looks_like_reactivation(text):
        return await _handle_reactivation(db, message, lead, text)

    if _looks_like_do_not_contact_request(text):
        return await _handle_do_not_contact(db, message, lead, text)

    if _looks_like_abusive_message(text):
        return await _handle_abusive_message(db, message, lead, text)

    if _looks_like_not_interested(text):
        return await _handle_not_interested(db, message, lead, text)

    if _looks_like_estimate_file_content_question(text):
        text_reply = "Я не читаю содержимое Excel-сметы в чате, поэтому сумму называть не буду. Передам вопрос менеджеру или сметчику, чтобы ответили точно."
        sent = await message.answer(text_reply)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text_reply,
            telegram_message_id=sent.message_id,
            sender_name="AI",
            ai_metadata={
                "source": "bot_scenario",
                "type": "estimate_file_content_question",
                "skip_knowledge_index": True,
            },
        )
        return True

    if await _try_execute_llm_crm_tool(db, message, lead, text, stage_context):
        return True

    if _looks_like_manager_handoff_request(text):
        return await _send_manager_handoff_notice(message, db, lead)

    if looks_like_estimate_file_request(text):
        return await send_ready_estimate_from_crm(db, message, lead)

    corrected_address = _extract_direct_address_correction(text)
    if corrected_address and await _handle_direct_measurement_address_correction(db, message, lead, corrected_address):
        return True

    if _looks_like_existing_measurement_lookup(text):
        answer = _build_measurement_status_answer(lead, text)
        sent = await message.answer(answer)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=answer,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "bot_scenario", "type": "measurement_status_lookup"},
        )
        return True

    if _looks_like_measurement_cancel_request(text) and (measurement_data.get("start") or measurement_data.get("booking_uid")):
        return await _handle_measurement_cancel_request(db, message, lead)

    if _looks_like_measurement_change_request(text) and measurement_data.get("start"):
        return await _send_measurement_change_choices(message, db, lead)

    if _looks_like_measurement_reschedule_request(text) and measurement_data.get("start"):
        return await _send_measurement_reschedule_slot_dates(message, db, lead)

    if _looks_like_measurement_booking_request(text):
        return await _send_measurement_slot_dates(message, db, lead)

    if next_action == "awaiting_measurement_slot" and _looks_like_measurement_slot_reply(text):
        return await _send_measurement_slot_dates(message, db, lead)

    if next_action == "confirm_measurement" and await _answer_measurement_question_if_possible(db, message, lead, text):
        return True

    if next_action == "confirm_measurement" and _looks_like_measurement_acknowledgement(text):
        return await _send_measurement_acknowledgement(message, db, lead)

    return False


# Debouncing state: {conversation_key: (task, [messages], original_message, has_voice)}
pending_updates = {}

AUTH_SESSION_TTL_SECONDS = 5 * 60
PROTECTED_EXTRACTED_DATA_KEYS = {
    "quiz",
    "messengers",
    "utm",
    "metadata",
    "measurement",
    "telegram_chat",
    "whatsapp_chat",
    "quiz_session_token",
}


def _parse_extracted_data(value: str | None) -> dict:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        return parsed if isinstance(parsed, dict) else {}
    except json.JSONDecodeError:
        return {}


def _merge_ai_extracted_data(existing_value: str | None, ai_data: dict) -> str:
    """
    Preserve durable CRM/quiz context while letting the AI update qualification fields.
    The quiz block is the source of truth for already answered quiz questions.
    """
    existing = _parse_extracted_data(existing_value)
    merged = dict(existing)
    current_ai = merged.get("ai_extracted")
    if not isinstance(current_ai, dict):
        current_ai = {}

    clean_ai = {key: value for key, value in ai_data.items() if value is not None}
    merged["ai_extracted"] = {
        **current_ai,
        **clean_ai,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    for key, value in clean_ai.items():
        if key in PROTECTED_EXTRACTED_DATA_KEYS:
            continue
        merged[key] = value

    return json.dumps(merged, ensure_ascii=False)


def _normalize_username(username: str | None) -> str | None:
    return (username or "").replace("@", "").strip() or None


def _build_crm_login_url() -> str:
    explicit_url = (getattr(settings, "crm_login_url", "") or "").strip()
    if explicit_url:
        return explicit_url
    origins = settings.cors_origins_list
    if origins:
        base_url = origins[0].rstrip("/")
        if base_url.endswith("/login"):
            return base_url
        return f"{base_url}/login"
    return "/login"


async def _resolve_operator_request_org(db: AsyncSession) -> Organization | None:
    result = await db.execute(
        select(Organization)
        .order_by(Organization.created_at.asc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_latest_operator_access_request(
    db: AsyncSession,
    org_id,
    telegram_id: int,
) -> OperatorAccessRequest | None:
    result = await db.execute(
        select(OperatorAccessRequest)
        .where(
            OperatorAccessRequest.org_id == org_id,
            OperatorAccessRequest.telegram_id == telegram_id,
        )
        .order_by(OperatorAccessRequest.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _get_or_create_operator_access_request(
    db: AsyncSession,
    org_id,
    telegram_id: int,
    full_name: str | None = None,
    username: str | None = None,
) -> tuple[OperatorAccessRequest, bool]:
    request = await _get_latest_operator_access_request(db, org_id=org_id, telegram_id=telegram_id)
    normalized_username = _normalize_username(username)
    if request:
        changed = False
        next_full_name = (full_name or "").strip() or request.full_name
        if next_full_name != request.full_name:
            request.full_name = next_full_name
            changed = True
        next_username = normalized_username or request.username
        if next_username != request.username:
            request.username = next_username
            changed = True
        if changed:
            await db.flush()
        return request, False

    request = OperatorAccessRequest(
        org_id=org_id,
        telegram_id=telegram_id,
        full_name=(full_name or "").strip() or None,
        username=normalized_username,
        status=OperatorAccessRequestStatus.PENDING.value,
    )
    db.add(request)
    await db.flush()
    return request, True


def _build_operator_access_keyboard(request_id: uuid.UUID) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Одобрить", callback_data=f"operator_access:approve:{request_id}"),
                InlineKeyboardButton(text="❌ Отклонить", callback_data=f"operator_access:reject:{request_id}"),
            ]
        ]
    )


async def _notify_admins_about_operator_request(db: AsyncSession, access_request: OperatorAccessRequest) -> None:
    if not bot:
        return

    result = await db.execute(
        select(User)
        .where(
            User.org_id == access_request.org_id,
            User.role == UserRole.ADMIN,
            User.telegram_id.is_not(None),
        )
    )
    admins = result.scalars().all()
    if not admins:
        logger.warning("No Telegram admins found for operator access request %s", access_request.id)
        return

    applicant_name = (access_request.full_name or "").strip() or "Без имени"
    applicant_username = f"@{access_request.username}" if access_request.username else "—"
    message_text = (
        "🔐 Новая заявка на доступ в CRM\n\n"
        f"Имя: {applicant_name}\n"
        f"Username: {applicant_username}\n"
        f"Telegram ID: {access_request.telegram_id}\n\n"
        "Выберите действие:"
    )
    keyboard = _build_operator_access_keyboard(access_request.id)

    for admin in admins:
        try:
            await bot.send_message(
                chat_id=admin.telegram_id,
                text=message_text,
                reply_markup=keyboard,
            )
        except Exception as exc:
            logger.warning(
                "Failed to send operator request %s notification to admin %s: %s",
                access_request.id,
                admin.telegram_id,
                exc,
            )


async def _notify_operator_access_approved(telegram_id: int) -> None:
    if not bot:
        return
    try:
        login_url = _build_crm_login_url()
        message_text = (
            "✅ Доступ в CRM одобрен администратором.\n"
            f"Войдите по ссылке: {login_url}"
        )
        await bot.send_message(chat_id=telegram_id, text=message_text)
    except Exception as exc:
        logger.warning("Failed to send approval notification to operator %s: %s", telegram_id, exc)


async def _notify_operator_access_rejected(telegram_id: int, reason: str | None = None) -> None:
    if not bot:
        return
    try:
        base_reason = (reason or "").strip() or "Заявка отклонена администратором."
        await bot.send_message(
            chat_id=telegram_id,
            text=f"❌ Доступ в CRM не одобрен.\n{base_reason}",
        )
    except Exception as exc:
        logger.warning("Failed to send rejection notification to operator %s: %s", telegram_id, exc)


async def _try_authorize_login_payload(message: Message, payload: str | None) -> bool:
    """
    Handle admin web login deep-link payload: login_<session_uuid>.
    Returns True when payload was recognized and processed.
    """
    try:
        if not payload or not payload.startswith("login_"):
            return False

        if not message.from_user:
            await message.answer("Не удалось определить пользователя Telegram. Попробуйте ещё раз.")
            return True

        if message.chat and getattr(message.chat, "type", None) != "private":
            await message.answer("Напишите боту в личные сообщения для входа в CRM.")
            return True

        session_id_str = payload.removeprefix("login_")
        try:
            session_uuid = uuid.UUID(session_id_str)
        except Exception:
            await message.answer("Ссылка для входа недействительна. Откройте страницу входа на сайте ещё раз.")
            return True

        async with AsyncSessionLocal() as db:
            res = await db.execute(select(AuthSession).where(AuthSession.id == session_uuid))
            session = res.scalar_one_or_none()
            if not session or session.status != "pending":
                await message.answer("Срок действия сессии истёк. Откройте страницу входа на сайте ещё раз.")
                return True

            now = datetime.now(timezone.utc)
            created_at = session.created_at or now
            if created_at.tzinfo is None:
                created_at = created_at.replace(tzinfo=timezone.utc)
            else:
                created_at = created_at.astimezone(timezone.utc)

            if now - created_at > timedelta(seconds=AUTH_SESSION_TTL_SECONDS):
                await db.delete(session)
                await db.commit()
                await message.answer("Срок действия сессии истёк. Откройте страницу входа на сайте ещё раз.")
                return True

            session.telegram_id = message.from_user.id
            session.username = message.from_user.username
            session.full_name = message.from_user.full_name

            user_result = await db.execute(select(User).where(User.telegram_id == message.from_user.id))
            user = user_result.scalar_one_or_none()
            if user:
                session.status = "authorized"
                await db.commit()
                await message.answer("✅ Вход подтверждён. Вернитесь на сайт — авторизация выполнится автоматически.")
                return True

            count_result = await db.execute(select(func.count(User.id)))
            total_users = count_result.scalar() or 0
            if total_users == 0:
                session.status = "authorized"
                await db.commit()
                await message.answer(
                    "✅ Вход подтверждён.\n"
                    "Вы будете первым администратором CRM. Вернитесь на сайт — вход выполнится автоматически."
                )
                return True

            organization = await _resolve_operator_request_org(db)
            if not organization:
                await db.delete(session)
                await db.commit()
                await message.answer("Организация не найдена. Обратитесь к администратору.")
                return True

            access_request, created = await _get_or_create_operator_access_request(
                db=db,
                org_id=organization.id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )

            if access_request.status == OperatorAccessRequestStatus.REJECTED.value:
                session.status = "rejected"
                await db.commit()
                await message.answer(
                    "❌ Заявка на доступ отклонена.\n"
                    f"{access_request.rejection_reason or 'Обратитесь к администратору CRM.'}"
                )
                return True

            if access_request.status == OperatorAccessRequestStatus.APPROVED.value:
                session.status = "authorized"
                await db.commit()
                await message.answer("✅ Доступ уже одобрен. Вернитесь на сайт — вход выполнится автоматически.")
                return True

            session.status = "pending_approval"
            await db.commit()

            await message.answer("⏳ Заявка отправлена администратору. Ожидайте одобрения.")
            if created:
                await _notify_admins_about_operator_request(db, access_request)
            return True
    except Exception as e:
        logger.error("Failed to handle login_ payload: %s", e, exc_info=True)
        await message.answer("Произошла ошибка при подтверждении входа. Попробуйте ещё раз.")
        return True

    return False


async def _handle_regular_start(message: Message) -> None:
    """
    Handle regular /start command from potential leads.
    Creates lead if new user and starts AI conversation.
    """
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        # Get or create lead
        avatar_url = await download_user_avatar(bot, message.from_user.id)
        from src.services.quiz_service import quiz_service
        lead = await quiz_service.link_telegram_identity(
            db=db,
            org_id=org_id,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        if not lead:
            lead = await lead_service.create_or_get_lead(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
                avatar_url=avatar_url
            )
        elif avatar_url and not lead.avatar_url:
            lead.avatar_url = avatar_url
            await db.flush()
        
        # Save /start command
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=message.text,
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name
        )

        if await _handle_quiz_lead_activation_flow(
            message=message,
            db=db,
            lead=lead,
            source="plain_start_existing_quiz",
        ):
            return
        
        # Get initial message from database or fallback
        config = await prompt_service.get_active_config(db, org_id)

        # Get company name from org settings
        from src.models.organization import Organization
        from sqlalchemy import select
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        company_name = _display_company_name(org)

        welcome_text = config.welcome_message if config and config.welcome_message else get_initial_message(company_name)
        if not is_business_hours():
            logger.info(
                "Outside business hours at %s, sending /start out-of-hours notice for lead %s",
                get_business_now().isoformat(),
                lead.id
            )
            welcome_text = (
                f"{welcome_text}\n\n"
                "Сейчас команда не на связи. Ответим в рабочее время 🕘"
            )
        
        # Save AI response to database
        sent_message = await message.answer(welcome_text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=welcome_text,
            telegram_message_id=sent_message.message_id,
            sender_name="AI"
        )


async def _handle_quiz_start(message: Message, session_token: str) -> None:
    """
    Handle quiz deep-link /start qz_... and connect Telegram user to CRM lead.
    """
    async with AsyncSessionLocal() as db:
        org_id = await get_default_org_id(db)
        avatar_url = await download_user_avatar(bot, message.from_user.id)

        from src.services.quiz_service import quiz_service
        lead = await quiz_service.link_telegram_message(
            db=db,
            org_id=org_id,
            text=session_token,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        if not lead:
            lead = await lead_service.create_or_get_lead(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
                avatar_url=avatar_url,
                source="telegram_bot",
            )
        elif avatar_url and not lead.avatar_url:
            lead.avatar_url = avatar_url
            await db.flush()

        try:
            from src.services.analytics_service import analytics_service
            await analytics_service.record_event(
                db=db,
                session_token=session_token,
                event_type="telegram_bot_started",
                step_id="messenger",
                event_data={"lead_id": str(lead.id), "telegram_id": message.from_user.id},
            )
        except Exception as exc:
            logger.warning("Failed to record telegram_bot_started for %s: %s", session_token, exc)

        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=message.text or f"/start {session_token}",
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name,
            ai_metadata={"source": "quiz_deep_link", "session_token": session_token},
        )

        if await _handle_quiz_lead_activation_flow(
            message=message,
            db=db,
            lead=lead,
            session_token=session_token,
            source="quiz_deep_link",
        ):
            return

        welcome_text = (
            "Здравствуйте! Вижу вашу заявку по квизу.\n\n"
            "Напишите сюда любой вопрос — продолжим расчет по вашим данным и подскажем следующий шаг."
        )
        if not is_business_hours():
            welcome_text = f"{welcome_text}\n\nСейчас команда не на связи. Ответим в рабочее время 🕘"

        sent_message = await message.answer(welcome_text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=welcome_text,
            telegram_message_id=sent_message.message_id,
            sender_name="Bot",
            ai_metadata={"source": "quiz_deep_link", "engine": "bot_template", "type": "quiz_deep_link_fallback"},
        )


@router.message(CommandStart(deep_link=True))
async def cmd_start_deep_link(message: Message, command: CommandObject):
    """
    Handle deep-link /start payloads like /start login_<session_id> or /start qz_...
    """
    payload = (command.args or "").strip()
    handled = await _try_authorize_login_payload(message, payload)
    if handled:
        return
    if re.fullmatch(r"qz_[A-Za-z0-9_-]{12,}", payload):
        await _handle_quiz_start(message, payload)
        return
    await _handle_regular_start(message)


@router.message(CommandStart())
async def cmd_start(message: Message):
    """
    Handle plain /start.
    """
    await _handle_regular_start(message)

# Fallback: user may send payload as plain message if Telegram doesn't re-trigger /start.
@router.message(F.text.regexp(r"^login_[0-9a-fA-F-]{36}$"))
async def login_payload_fallback(message: Message):
    payload = (message.text or "").strip()
    handled = await _try_authorize_login_payload(message, payload)
    if handled:
        return


@router.callback_query(F.data.regexp(r"^operator_access:(approve|reject):[0-9a-fA-F-]{36}$"))
async def operator_access_callback(query: CallbackQuery):
    if not query.data or not query.from_user:
        await query.answer("Некорректный запрос", show_alert=True)
        return

    parts = query.data.split(":")
    if len(parts) != 3:
        await query.answer("Некорректный формат запроса", show_alert=True)
        return

    action = parts[1]
    try:
        request_id = uuid.UUID(parts[2])
    except Exception:
        await query.answer("Некорректный идентификатор заявки", show_alert=True)
        return

    async with AsyncSessionLocal() as db:
        request_result = await db.execute(select(OperatorAccessRequest).where(OperatorAccessRequest.id == request_id))
        access_request = request_result.scalar_one_or_none()
        if not access_request:
            await query.answer("Заявка не найдена", show_alert=True)
            return

        admin_result = await db.execute(select(User).where(User.telegram_id == query.from_user.id))
        admin_user = admin_result.scalar_one_or_none()
        if (
            not admin_user
            or admin_user.role != UserRole.ADMIN
            or str(admin_user.org_id) != str(access_request.org_id)
        ):
            await query.answer("Недостаточно прав", show_alert=True)
            return

        if access_request.status != OperatorAccessRequestStatus.PENDING.value:
            await query.answer("Заявка уже обработана")
            return

        if action == "approve":
            user_result = await db.execute(select(User).where(User.telegram_id == access_request.telegram_id))
            operator = user_result.scalar_one_or_none()
            if operator and str(operator.org_id) != str(access_request.org_id):
                await query.answer("Пользователь привязан к другой организации", show_alert=True)
                return
            if operator and operator.role == UserRole.ADMIN:
                await query.answer("Нельзя изменять роль ADMIN", show_alert=True)
                return

            if operator is None:
                operator = User(
                    org_id=access_request.org_id,
                    telegram_id=access_request.telegram_id,
                    full_name=(access_request.full_name or "").strip() or None,
                    username=_normalize_username(access_request.username),
                    role=UserRole.MANAGER,
                )
                db.add(operator)
            else:
                operator.role = UserRole.MANAGER
                if not operator.full_name and access_request.full_name:
                    operator.full_name = (access_request.full_name or "").strip() or None
                if not operator.username and access_request.username:
                    operator.username = _normalize_username(access_request.username)

            access_request.status = OperatorAccessRequestStatus.APPROVED.value
            access_request.processed_by_user_id = admin_user.id
            access_request.processed_at = datetime.now(timezone.utc)
            access_request.rejection_reason = None
            await db.commit()

            await query.answer("Заявка одобрена")
            if query.message:
                applicant_name = (access_request.full_name or "").strip() or "Без имени"
                try:
                    await query.message.edit_text(
                        "✅ Заявка одобрена\n\n"
                        f"Имя: {applicant_name}\n"
                        f"Telegram ID: {access_request.telegram_id}\n"
                        f"Одобрил: {admin_user.full_name or admin_user.username or admin_user.email or 'Администратор'}"
                    )
                except Exception:
                    pass

            await _notify_operator_access_approved(access_request.telegram_id)
            return

        access_request.status = OperatorAccessRequestStatus.REJECTED.value
        access_request.processed_by_user_id = admin_user.id
        access_request.processed_at = datetime.now(timezone.utc)
        access_request.rejection_reason = "Отклонено администратором."
        await db.commit()

        await query.answer("Заявка отклонена")
        if query.message:
            applicant_name = (access_request.full_name or "").strip() or "Без имени"
            try:
                await query.message.edit_text(
                    "❌ Заявка отклонена\n\n"
                    f"Имя: {applicant_name}\n"
                    f"Telegram ID: {access_request.telegram_id}\n"
                    f"Отклонил: {admin_user.full_name or admin_user.username or admin_user.email or 'Администратор'}"
                )
            except Exception:
                pass

        await _notify_operator_access_rejected(access_request.telegram_id, access_request.rejection_reason)


@router.callback_query(F.data.regexp(r"^quiz_measure_change:(time|address|phone)$"))
async def quiz_measure_change_callback(query: CallbackQuery):
    action = (query.data or "").split(":", 1)[1]
    async with AsyncSessionLocal() as db:
        lead = await _find_lead_by_telegram(db, query.from_user.id)
        if not lead:
            await query.answer("Заявка не найдена", show_alert=True)
            return

        if action == "time":
            slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
            if not slots:
                await query.answer("Слоты сейчас не загрузились", show_alert=True)
                return
            data = _lead_extracted_data(lead)
            measurement = data.get("measurement") if isinstance(data.get("measurement"), dict) else {}
            measurement["status"] = "awaiting_reschedule_slot"
            measurement["reschedule_requested_at"] = datetime.now(timezone.utc).isoformat()
            data["measurement"] = measurement
            lead.extracted_data = json.dumps(data, ensure_ascii=False)
            await db.commit()
            if query.message:
                await query.message.edit_text(
                    "Выберите новый удобный день замера 📍",
                    reply_markup=_build_measurement_date_keyboard(slots),
                )
            await query.answer()
            return

        if action == "address":
            await _set_pending_measurement_update(db, lead, "address")
            text = "Напишите новый адрес объекта: город, улицу, дом и квартиру/офис."
            if query.message:
                await query.message.edit_text(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=query.message.message_id if query.message else None,
                sender_name="AI",
                ai_metadata={"source": "measurement_change", "type": "measurement_address_update_request"},
            )
            await query.answer()
            return

        await _set_pending_measurement_update(db, lead, "phone")
        text = "Напишите новый телефон для связи по замеру в формате +7..."
        if query.message:
            await query.message.edit_text(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=query.message.message_id if query.message else None,
            sender_name="AI",
            ai_metadata={"source": "measurement_change", "type": "measurement_phone_update_request"},
        )
        await query.answer()


@router.callback_query(F.data == "quiz_measure_back")
async def quiz_measure_back_callback(query: CallbackQuery):
    async with AsyncSessionLocal() as db:
        lead = await _find_lead_by_telegram(db, query.from_user.id)
        if not lead:
            await query.answer("Заявка не найдена", show_alert=True)
            return
        slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
        if not slots:
            await query.answer("Слоты сейчас не загрузились", show_alert=True)
            return
        measurement = _lead_measurement_data(lead)
        text = (
            "Выберите новый удобный день замера 📍"
            if measurement.get("status") == "awaiting_reschedule_slot"
            else "Выберите удобный день бесплатного замера. Он поможет точно посчитать работы без стройматериалов 📍"
        )
        await query.message.edit_text(
            text,
            reply_markup=_build_measurement_date_keyboard(slots),
        )
        await query.answer()


@router.callback_query(F.data.regexp(r"^quiz_measure_date:\d{4}-\d{2}-\d{2}$"))
async def quiz_measure_date_callback(query: CallbackQuery):
    date_key = (query.data or "").split(":", 1)[1]
    async with AsyncSessionLocal() as db:
        lead = await _find_lead_by_telegram(db, query.from_user.id)
        if not lead:
            await query.answer("Заявка не найдена", show_alert=True)
            return
        slots = await cal_pro_service.get_slots(days_ahead=7, limit=80)
        matching_slots = [slot for slot in slots if _slot_date_key(slot.start) == date_key]
        if not matching_slots:
            await query.answer("На этот день окна уже заняты. Выберите, пожалуйста, другой день.", show_alert=True)
            return
        await query.message.edit_text(
            f"Выберите удобное время замера на {_slot_date_button_label(date_key)} 🕘",
            reply_markup=_build_measurement_time_keyboard(slots, date_key),
        )
        await query.answer()


@router.callback_query(F.data.regexp(r"^quiz_measure_time:.+"))
async def quiz_measure_time_callback(query: CallbackQuery):
    start = (query.data or "").split(":", 1)[1]
    async with AsyncSessionLocal() as db:
        lead = await _find_lead_by_telegram(db, query.from_user.id)
        if not lead:
            await query.answer("Заявка не найдена", show_alert=True)
            return
        measurement = _lead_measurement_data(lead)
        if measurement.get("status") == "awaiting_reschedule_slot":
            await _confirm_measurement_reschedule(db, query, lead, start)
            await query.answer()
            return
        await _store_pending_measurement_slot(db, lead, start)
        if _normalize_phone(lead.phone):
            text = (
                f"Отлично, держу для вас окно {_slot_date_button_label(_slot_date_key(start))} "
                f"в {_slot_time_label(start)} ✅\n\n"
                "Чтобы подтвердить выезд специалиста, напишите адрес объекта: город, улицу, дом и квартиру/офис."
            )
        else:
            text = (
                f"Отлично, держу для вас окно {_slot_date_button_label(_slot_date_key(start))} "
                f"в {_slot_time_label(start)} ✅\n\n"
                "Чтобы закрепить замер, напишите телефон для связи в формате +7..."
            )
        await query.message.edit_text(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=query.message.message_id,
            sender_name="AI",
            ai_metadata={"source": "telegram_inline_slots", "type": "measurement_address_request"},
        )
        await query.answer()


@router.business_message(F.text)
@router.message(F.text)
async def handle_lead_message(message: Message):
    """
    Handle text messages from leads with debouncing.
    Groups messages sent within the debounce window into a single AI request.
    """
    if _is_business_author_message(message):
        logger.info(
            "Ignoring Telegram business author message: chat_id=%s user_id=%s connection=%s",
            getattr(message.chat, "id", None),
            getattr(message.from_user, "id", None),
            getattr(message, "business_connection_id", None),
        )
        return

    user_id = message.from_user.id
    business_connection_id = getattr(message, "business_connection_id", None)
    conversation_key = (
        f"business:{business_connection_id}:{message.chat.id}:{user_id}"
        if business_connection_id
        else f"bot:{user_id}"
    )
    if business_connection_id:
        logger.info(
            "Telegram business message queued: chat_id=%s user_id=%s connection=%s text=%s",
            message.chat.id,
            user_id,
            business_connection_id,
            (message.text or "")[:120],
        )
    typing_once_task = asyncio.create_task(_send_typing_action(message))
    typing_once_task.add_done_callback(_drain_background_task)
    is_voice = getattr(message, "is_voice", False)
    
    # Add message to pending list
    if conversation_key in pending_updates:
        task, msgs, saved_message, has_voice = pending_updates[conversation_key]
        task.cancel() # Cancel previous timer
        msgs.append(message.text)
        has_voice = has_voice or is_voice
    else:
        msgs = [message.text]
        saved_message = message
        has_voice = is_voice
    
    # Start new timer task
    task = asyncio.create_task(process_debounced_message(conversation_key))
    task.add_done_callback(_drain_background_task)
    pending_updates[conversation_key] = (task, msgs, saved_message, has_voice)

async def process_debounced_message(conversation_key: str):
    """Wait for quiet period and then process all accumulated messages."""
    await asyncio.sleep(LEAD_MESSAGE_DEBOUNCE_SECONDS)
    
    if conversation_key not in pending_updates:
        return
        
    _, msgs, message, has_voice = pending_updates.pop(conversation_key)
    combined_text = " ".join(msgs)
    user_id = message.from_user.id
    business_connection_id = getattr(message, "business_connection_id", None)
    _start_typing_indicator(message)
    
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        from src.services.quiz_service import quiz_service
        lead = await quiz_service.link_telegram_message(
            db=db,
            org_id=org_id,
            text=combined_text,
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        if not lead:
            lead = await quiz_service.link_telegram_identity(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )
        if not lead:
            lead = await lead_service.create_or_get_lead(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username
            )
        
        # Save incoming message (using combined text as one entry for AI context)
        metadata = {"is_voice": True} if has_voice else {}
        if business_connection_id:
            metadata.update(
                {
                    "source": "telegram_business",
                    "business_connection_id": business_connection_id,
                    "business_chat_id": message.chat.id,
                }
            )
        
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=combined_text,
            telegram_message_id=message.message_id,
            sender_name=message.from_user.full_name,
            ai_metadata=metadata or None,
        )

        if business_connection_id:
            data = _lead_extracted_data(lead)
            data["telegram_business_chat"] = {
                "business_connection_id": business_connection_id,
                "chat_id": message.chat.id,
                "telegram_id": message.from_user.id,
                "username": _normalize_username(message.from_user.username),
                "linked_at": datetime.now(timezone.utc).isoformat(),
            }
            data.setdefault("messengers", {})["telegram"] = True
            lead.extracted_data = json.dumps(data, ensure_ascii=False)
            if not lead.source or lead.source == "telegram":
                lead.source = "telegram_business"
            await db.commit()

        session_token = quiz_service.extract_session_token(combined_text)
        if session_token:
            source = "quiz_business_message" if business_connection_id else "quiz_token_message"
            try:
                if await _handle_quiz_lead_activation_flow(
                    message=message,
                    db=db,
                    lead=lead,
                    session_token=session_token,
                    source=source,
                ):
                    return
            except Exception:
                logger.error(
                    "Quiz activation failed: lead_id=%s session_token=%s business=%s",
                    getattr(lead, "id", None),
                    session_token,
                    bool(business_connection_id),
                    exc_info=True,
                )
            await _send_quiz_token_fallback(
                message=message,
                db=db,
                lead=lead,
                session_token=session_token,
                source=source,
            )
            return

        if await _try_handle_pending_measurement_update(db, message, lead, combined_text):
            return

        if await _try_handle_pending_measurement_address(db, message, lead, combined_text):
            return

        from src.services.lead_stage_context_service import lead_stage_context_service
        stage_context = await lead_stage_context_service.build_context(db=db, lead=lead)
        if await _try_route_scenario_before_ai(db, message, lead, combined_text, stage_context):
            return

        outside_business_hours = not is_business_hours()
        if outside_business_hours:
            logger.info(
                "Outside business hours at %s, continuing AI reply for lead %s with after-hours context",
                get_business_now().isoformat(),
                lead.id
            )
        
        # Check if AI should handle this lead
        if lead.ai_qualification_status == "handoff_required":
            direct_data = _lead_extracted_data(lead)
            if (
                stage_context.next_action == "direct_chat_qualification"
                and should_offer_qualification(combined_text, direct_data)
            ):
                lead.ai_qualification_status = "in_progress"
                await db.commit()
            elif _looks_like_measurement_question(combined_text):
                measurement_answer = _build_measurement_context_answer(lead, combined_text)
                if measurement_answer:
                    await message.answer(measurement_answer)
                    return

        try:
            # Get conversation history
            messages, total = await chat_service.get_chat_history(
                db=db,
                lead_id=lead.id,
                page=1,
                page_size=20  # Last 20 messages
            )
            
            # Convert to OpenRouter format
            conversation = []
            for msg in reversed(messages):  # Oldest first (messages are DESC, so reverse)
                role = "user" if msg.direction == "inbound" else "assistant"
                text_content = msg.content
                
                # Tell AI if the user sent a voice message
                if msg.ai_metadata and msg.ai_metadata.get("is_voice"):
                    text_content = f"[Голосовое сообщение] {text_content}"
                    
                conversation.append({
                    "role": role,
                    "content": text_content
                })
            
            # Get active prompt configuration
            config = await prompt_service.get_active_config(db, org_id)
            
            # Get company name for prompt injection
            from src.models.organization import Organization
            from sqlalchemy import select
            org_result = await db.execute(select(Organization).where(Organization.id == org_id))
            org = org_result.scalar_one_or_none()
            company_name = _display_company_name(org)
            
            if config and config.system_prompt:
                base_prompt = config.system_prompt
                if "{company_name}" in base_prompt:
                    base_prompt = base_prompt.replace("{company_name}", company_name)
                
                from src.services.custom_field_service import enrich_system_prompt
                system_prompt = await enrich_system_prompt(db, org_id, base_prompt)
            else:
                system_prompt = await build_system_prompt(db, org_id, company_name)
            
            # Technical constraints to prevent breakage
            system_prompt = normalize_system_prompt_template(system_prompt)
            technical_rules = (
                "\n\nCRITICAL: Always respond in valid JSON format. "
                "If you need to speak to the user, put your text in the \"message\" field of the JSON. "
                "Keep user-facing message concise: normally 1-4 short sentences."
            )
            identity_rules = IDENTITY_GUARDRAILS.format(company_name=company_name)
            system_prompt = f"{system_prompt}\n\n{identity_rules}{technical_rules}"
            if outside_business_hours:
                system_prompt = (
                    f"{system_prompt}\n\n"
                    "AFTER-HOURS CONTEXT: Сейчас команда не на связи. Все равно ответь клиенту полезно и по делу. "
                    "Если нужен менеджер, скажи, что команда вернется в рабочее время; не исчезай и не отказывайся отвечать."
                )

            system_prompt = f"{system_prompt}\n\n{stage_context.prompt_block}\n\n{_build_ai_support_tools_prompt(stage_context)}"
            
            # Perform RAG (Retrieval)
            trace_id = f"lead_{lead.id}_{len(messages)}" # Unique per turn
            ai_metadata = {}
            ai_metadata["stage_context"] = stage_context.metadata
            logger.info(
                "AI reply requested: lead_id=%s status=%s next_action=%s text=%s",
                lead.id,
                lead.status,
                stage_context.metadata.get("next_action"),
                combined_text[:200],
            )
            try:
                relevant_docs = await knowledge_service.search_knowledge(
                    db=db,
                    org_id=org_id,
                    query=combined_text,
                    limit=3,
                    lead_id=lead.id,
                    embedding_model=config.embedding_model if config else None,
                    trace_id=trace_id,
                    user_id=str(message.from_user.id)
                )
            except Exception as rag_err:
                relevant_docs = []
                ai_metadata["rag_error"] = str(rag_err)[:500]
                logger.warning("RAG search failed (non-critical): %s", rag_err)

            if relevant_docs:
                context_str = "\n\n".join([f"Source: {d.title}\nContent: {d.content}" for d in relevant_docs])
                system_prompt = f"{system_prompt}\n\nRELEVANT KNOWLEDGE:\n{context_str}\n\nUse this context to answer accurately."
                
                # Save context for transparency
                ai_metadata["retrieved_context"] = [
                    {"title": d.title, "content": d.content, "id": str(d.id)}
                    for d in relevant_docs
                ]
            
            # Generate AI response
            ai_response = await openrouter_service.generate_response(
                conversation_history=conversation,
                system_prompt=system_prompt,
                model=config.llm_model if config else None,
                trace_id=trace_id,
                user_id=str(message.from_user.id)
            )

            is_support_question = _looks_like_support_question(combined_text)
            requested_tool_action = _extract_ai_tool_action(ai_response.get("extracted_data"))
            if requested_tool_action:
                ai_metadata["requested_tool_action"] = requested_tool_action
                ai_metadata["source"] = "ai_requested_tool"
                if is_support_question:
                    ai_metadata["ignored_tool_action"] = requested_tool_action
                    requested_tool_action = ""
                elif await _execute_ai_tool_action(db, message, lead, requested_tool_action):
                    return
            
            # Send AI response to user
            response_text = openrouter_service.enforce_identity_answer(
                user_message=combined_text,
                ai_text=ai_response["text"],
                company_name=company_name
            )
            extracted_data = ai_response.get("extracted_data")
            direct_prompt = None
            effective_extracted_data = _lead_extracted_data(lead)
            if extracted_data:
                effective_extracted_data = _parse_extracted_data(
                    _merge_ai_extracted_data(lead.extracted_data, extracted_data)
                )
            if (
                stage_context.next_action == "direct_chat_qualification"
                and should_offer_qualification(combined_text, effective_extracted_data)
            ):
                direct_prompt = build_next_prompt(effective_extracted_data, company_name=company_name)
                if direct_prompt:
                    ai_metadata["direct_qualification"] = {
                        "type": "inline_prompt",
                        "field": direct_prompt.field,
                    }

            outbound_text = direct_prompt.text if direct_prompt else response_text
            sent_message = await message.answer(
                outbound_text,
                reply_markup=direct_prompt.keyboard if direct_prompt else None,
            )
            logger.info(
                "AI reply sent: lead_id=%s telegram_message_id=%s",
                lead.id,
                sent_message.message_id,
            )
            
            # Save AI response to database
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=outbound_text,
                telegram_message_id=sent_message.message_id,
                sender_name="AI",
                ai_metadata=ai_metadata
            )
            
            # Update lead with extracted data
            if extracted_data:
                # 1. Sync structured fields if present
                update_fields = {}
                
                # Full Name
                if extracted_data.get("client_name") and not lead.full_name:
                    update_fields["full_name"] = extracted_data.get("client_name")
                
                # Phone
                if extracted_data.get("phone") and not lead.phone:
                    update_fields["phone"] = extracted_data.get("phone")
                
                # Status Change (from AI)
                ai_status = extracted_data.get("status")
                if ai_status and ai_status in [s.value for s in LeadStatus]:
                    update_fields["status"] = ai_status
                
                # Qualification Status
                if extracted_data.get("is_hot_lead"):
                    update_fields["ai_qualification_status"] = "qualified"
                    
                # A/B/C Readiness Score
                readiness_score = extracted_data.get("readiness_score")
                if readiness_score in ["A", "B", "C"]:
                    update_fields["readiness_score"] = readiness_score
                
                # Save extracted data without erasing quiz answers and messenger links.
                update_fields["extracted_data"] = _merge_ai_extracted_data(lead.extracted_data, extracted_data)
                
                # Execute update
                if update_fields:
                    await lead_service.update_lead(
                        db=db,
                        lead_id=lead.id,
                        **update_fields
                    )
                
                # Check if handoff is needed
                if openrouter_service.should_handoff(extracted_data) and not direct_prompt:
                    # Update lead status to handoff if not already set by AI
                    if update_fields.get("ai_qualification_status") != "handoff_required":
                        await lead_service.update_lead(
                            db=db,
                            lead_id=lead.id,
                            ai_qualification_status="handoff_required",
                            status=LeadStatus.QUALIFIED
                        )
                    
                    logger.info("🔥 HOT LEAD: %s (%s) - Ready for handoff!", lead.full_name, lead.telegram_id)
                    
                    # Notify managers/groups via Telegram if configured
                    try:
                        from src.services.telegram_notification_service import telegram_notification_service

                        try:
                            lead_info = (
                                f"🔥 *Горячий лид!*\n"
                                f"👤 Имя: {lead.full_name or 'Неизвестно'}\n"
                                f"📱 Telegram: @{lead.username or lead.telegram_id}\n"
                                f"📞 Телефон: {lead.phone or 'не указан'}\n"
                                f"📊 Статус: {lead.status}\n"
                                f"💬 Данные: {extracted_data.get('budget', 'нет')} | {extracted_data.get('area_sqm', 'нет')} м²"
                            )
                            await telegram_notification_service.send_to_managers(lead_info, parse_mode="Markdown")
                        except Exception as notify_err:
                            logger.warning("Failed to notify manager: %s", notify_err)
                    except Exception as notify_err:
                        logger.warning("Failed to initialize manager notification service: %s", notify_err)
                    
                    ai_metadata["silent_manager_handoff"] = True
        
        except Exception as e:
            logger.error("Error in AI handler for user %s: %s", user_id, e, exc_info=True)
            # Send user-facing error message instead of silently failing
            try:
                if not await _answer_measurement_question_if_possible(db, message, lead, combined_text):
                    await message.answer(
                        "Похоже, сейчас не получилось обработать сообщение автоматически. "
                        "Попробуйте написать еще раз, а если вопрос срочный — менеджер поможет вручную."
                    )
            except Exception:
                pass  # If even sending error message fails, just log it


@router.business_message(F.voice | F.audio | F.video_note)
@router.message(F.voice | F.audio | F.video_note)
async def handle_lead_voice(message: Message):
    """
    Handle voice messages from leads.
    Downloads the file, transcribes it via AssemblyAI, and passes text to AI silently.
    """
    if _is_business_author_message(message):
        logger.info(
            "Ignoring Telegram business author voice: chat_id=%s user_id=%s connection=%s",
            getattr(message.chat, "id", None),
            getattr(message.from_user, "id", None),
            getattr(message, "business_connection_id", None),
        )
        return

    import os
    import tempfile
    from src.services.voice_service import voice_service
    
    try:
        # Determine file type and get file ID
        if message.voice:
            file_id = message.voice.file_id
        elif message.audio:
            file_id = message.audio.file_id
        else:
            file_id = message.video_note.file_id
            
        file_info = await bot.get_file(file_id)
        
        # Download file to a temporary location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".ogg") as temp_file:
            temp_path = temp_file.name
            
        await bot.download_file(file_info.file_path, destination=temp_path)
        
        # Transcribe using service
        transcript = await voice_service.transcribe_audio(temp_path)
        
        # Cleanup temp file
        if os.path.exists(temp_path):
            os.remove(temp_path)
            
        if not transcript:
            # If transcription fails, the bot doesn't know what to say. 
            # We can log it, but we shouldn't reveal it's a bot.
            # Best is to do nothing, or perhaps say something generic via AI later, but right now just return.
            logger.warning(f"Failed to transcribe voice from user {message.from_user.id}")
            return
            
        # Forward the transcribed text to the main AI handler by modifying the message object
        message.text = transcript
        message.is_voice = True
        await handle_lead_message(message)
        
    except Exception as e:
        logger.error(f"Error handling voice message: {e}", exc_info=True)



@router.business_message(F.photo)
@router.message(F.photo)
async def handle_lead_photo(message: Message):
    """
    Handle photo messages from leads.
    Downloads the photo and sends it to AI via vision API so AI can actually see the image.
    """
    if _is_business_author_message(message):
        logger.info(
            "Ignoring Telegram business author photo: chat_id=%s user_id=%s connection=%s",
            getattr(message.chat, "id", None),
            getattr(message.from_user, "id", None),
            getattr(message, "business_connection_id", None),
        )
        return

    import base64
    import tempfile
    import os
    from src.models import MessageDirection
    
    # Get photo file_id (largest size)
    photo = message.photo[-1]
    
    async with AsyncSessionLocal() as db:
        # Get default organization ID
        org_id = await get_default_org_id(db)
        
        # Get or create lead
        from src.services.quiz_service import quiz_service
        lead = await quiz_service.link_telegram_message(
            db=db,
            org_id=org_id,
            text=message.caption or "",
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        if not lead:
            lead = await quiz_service.link_telegram_identity(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )
        if not lead:
            lead = await lead_service.create_or_get_lead(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username
            )
        
        # Save incoming message
        caption = message.caption or ""
        content_for_db = f"[Фото] {caption}" if caption else "[Фото]"
        
        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=content_for_db,
            telegram_message_id=message.message_id,
            media_url=f"tg://photo/{photo.file_id}",
            sender_name=message.from_user.full_name
        )
        
        # Download photo and convert to base64
        image_base64 = None
        try:
            file_info = await bot.get_file(photo.file_id)
            with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
                temp_path = tmp.name
            await bot.download_file(file_info.file_path, destination=temp_path)
            
            with open(temp_path, "rb") as f:
                image_base64 = base64.b64encode(f.read()).decode("utf-8")
            
            os.remove(temp_path)
        except Exception as e:
            logger.error(f"Failed to download photo: {e}", exc_info=True)
        
        # Build system prompt
        config = await prompt_service.get_active_config(db, org_id)

        outside_business_hours = not is_business_hours()
        if outside_business_hours:
            logger.info(
                "Outside business hours at %s, continuing photo reply for lead %s with after-hours context",
                get_business_now().isoformat(),
                lead.id
            )

        from src.models.organization import Organization
        org_result = await db.execute(select(Organization).where(Organization.id == org_id))
        org = org_result.scalar_one_or_none()
        company_name = _display_company_name(org)
        
        if config and config.system_prompt:
            base_prompt = config.system_prompt
            if "{company_name}" in base_prompt:
                base_prompt = base_prompt.replace("{company_name}", company_name)
            
            from src.services.custom_field_service import enrich_system_prompt
            system_prompt = await enrich_system_prompt(db, org_id, base_prompt)
        else:
            system_prompt = await build_system_prompt(db, org_id, company_name)
        
        system_prompt = normalize_system_prompt_template(system_prompt)
        technical_rules = (
            "\n\nCRITICAL: Always respond in valid JSON format. "
            "If you need to speak to the user, put your text in the \"message\" field of the JSON. "
            "Keep user-facing message concise: normally 1-4 short sentences."
        )
        identity_rules = IDENTITY_GUARDRAILS.format(company_name=company_name)
        system_prompt = f"{system_prompt}\n\n{identity_rules}{technical_rules}"
        if outside_business_hours:
            system_prompt = (
                f"{system_prompt}\n\n"
                "AFTER-HOURS CONTEXT: Сейчас команда не на связи. Все равно ответь клиенту полезно и по делу. "
                "Если нужен менеджер, скажи, что команда вернется в рабочее время; не исчезай и не отказывайся отвечать."
            )

        from src.services.lead_stage_context_service import lead_stage_context_service
        stage_context = await lead_stage_context_service.build_context(db=db, lead=lead)
        system_prompt = f"{system_prompt}\n\n{stage_context.prompt_block}\n\n{_build_ai_support_tools_prompt(stage_context)}"
        
        # Get conversation history (exclude the photo message we just saved — it's sent separately via vision)
        history_msgs, _ = await chat_service.get_chat_history(db, lead.id, page_size=20)
        
        formatted_history = []
        for m in reversed(history_msgs):
            # Skip the photo message we just saved (it'll be sent as an image)
            if m.telegram_message_id == message.message_id:
                continue
            role = "user" if m.direction == MessageDirection.INBOUND else "assistant"
            formatted_history.append({"role": role, "content": m.content})
        
        # Generate AI response — use vision if photo downloaded, fallback to text
        try:
            if image_base64:
                ai_response = await openrouter_service.generate_vision_response(
                    conversation_history=formatted_history,
                    system_prompt=system_prompt,
                    image_base64=image_base64,
                    image_caption=caption,
                    model=config.llm_model if config else None
                )
            else:
                # Fallback: tell AI about the photo via text
                formatted_history.append({
                    "role": "user",
                    "content": f"[Клиент прислал фото] {caption}" if caption else "[Клиент прислал фото объекта]"
                })
                ai_response = await openrouter_service.generate_response(
                    formatted_history,
                    system_prompt,
                    model=config.llm_model if config else None
                )
        except Exception as e:
            logger.error(f"Vision API failed, trying text fallback: {e}")
            formatted_history.append({
                "role": "user",
                "content": f"[Клиент прислал фото] {caption}" if caption else "[Клиент прислал фото объекта]"
            })
            ai_response = await openrouter_service.generate_response(
                formatted_history,
                system_prompt,
                model=config.llm_model if config else None
            )

        requested_tool_action = _extract_ai_tool_action(ai_response.get("extracted_data"))
        if requested_tool_action:
            if not _looks_like_support_question(caption) and await _execute_ai_tool_action(db, message, lead, requested_tool_action):
                return
        
        reply_text = ai_response["text"]
        await message.answer(reply_text)
        
        # Extract data and save
        extracted_data = ai_response.get("extracted_data")
        ai_metadata = {
            "usage": ai_response.get("usage"),
            "has_vision": bool(image_base64),
            "stage_context": stage_context.metadata,
        }
        update_fields = {}
        if extracted_data:
            if extracted_data.get("client_name") and not lead.full_name:
                update_fields["full_name"] = extracted_data.get("client_name")
            if extracted_data.get("phone") and not lead.phone:
                update_fields["phone"] = extracted_data.get("phone")
            
            ai_status = extracted_data.get("status")
            if ai_status and ai_status in [s.value for s in LeadStatus]:
                update_fields["status"] = ai_status
            
            if extracted_data.get("is_hot_lead"):
                update_fields["ai_qualification_status"] = "qualified"
                
            readiness_score = extracted_data.get("readiness_score")
            if readiness_score in ["A", "B", "C"]:
                update_fields["readiness_score"] = readiness_score
            
            update_fields["extracted_data"] = _merge_ai_extracted_data(lead.extracted_data, extracted_data)
        
        await chat_service.send_outbound_message(
            db, lead_id=lead.id, content=reply_text,
            sender_name="AI Agent", ai_metadata=ai_metadata
        )
        
        if update_fields:
            await lead_service.update_lead(db=db, lead_id=lead.id, **update_fields)


@router.business_message(F.document)
@router.message(F.document)
async def handle_lead_document(message: Message):
    """Save client files for estimate preparation and notify estimators."""
    if _is_business_author_message(message):
        logger.info(
            "Ignoring Telegram business author document: chat_id=%s user_id=%s connection=%s",
            getattr(message.chat, "id", None),
            getattr(message.from_user, "id", None),
            getattr(message, "business_connection_id", None),
        )
        return

    if not message.document:
        return

    async with AsyncSessionLocal() as db:
        org_id = await get_default_org_id(db)

        from src.services.quiz_service import quiz_service
        lead = await quiz_service.link_telegram_message(
            db=db,
            org_id=org_id,
            text=message.caption or "",
            telegram_id=message.from_user.id,
            full_name=message.from_user.full_name,
            username=message.from_user.username,
        )
        if not lead:
            lead = await quiz_service.link_telegram_identity(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )
        if not lead:
            lead = await lead_service.create_or_get_lead(
                db=db,
                org_id=org_id,
                telegram_id=message.from_user.id,
                full_name=message.from_user.full_name,
                username=message.from_user.username,
            )

        caption = (message.caption or "").strip()
        filename = message.document.file_name or "Файл для расчета"
        content = f"[Файл для расчета] {filename}"
        if caption:
            content += f"\n{caption}"

        await chat_service.save_incoming_message(
            db=db,
            lead_id=lead.id,
            content=content,
            telegram_message_id=message.message_id,
            media_url=f"tg://document/{message.document.file_id}",
            sender_name=message.from_user.full_name,
            ai_metadata={"source": "telegram_document", "file_name": filename},
        )

        try:
            url, display_name = await save_telegram_document(bot, message.document)
            from src.services.estimate_request_service import estimate_request_service

            await estimate_request_service.register_file(
                db=db,
                lead=lead,
                url=url,
                filename=display_name,
                source="telegram_document",
                telegram_file_id=message.document.file_id,
            )
        except ValueError as exc:
            text = (
                "Файл не получилось принять. Пришлите, пожалуйста, PDF, фото, архив, DWG или Excel до 50 МБ."
                if str(exc) in {"unsupported_file_type", "file_too_large"}
                else "Файл не получилось принять. Попробуйте отправить его еще раз."
            )
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="Bot",
                ai_metadata={"source": "telegram_document", "type": "estimate_file_rejected"},
            )
            return
        except Exception:
            logger.warning("Failed to save Telegram estimate document for lead %s", lead.id, exc_info=True)
            text = "Файл получили в чате, но не смогли сохранить в карточке. Менеджер проверит вручную."
            sent = await message.answer(text)
            await chat_service.send_outbound_message(
                db=db,
                lead_id=lead.id,
                content=text,
                telegram_message_id=sent.message_id,
                sender_name="Bot",
                ai_metadata={"source": "telegram_document", "type": "estimate_file_save_failed"},
            )
            return

        text = (
            "Файл получили, передали сметчику на просчет ✅\n"
            "Обычно расчет занимает до 24 часов."
        )
        sent = await message.answer(text)
        await chat_service.send_outbound_message(
            db=db,
            lead_id=lead.id,
            content=text,
            telegram_message_id=sent.message_id,
            sender_name="Bot",
            ai_metadata={"source": "telegram_document", "type": "estimate_file_received"},
        )


# Register router with dispatcher
dp.include_router(router)
