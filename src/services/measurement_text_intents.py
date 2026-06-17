"""Natural-language helpers for measurement booking flow."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable
from zoneinfo import ZoneInfo


MOSCOW_TZ = ZoneInfo("Europe/Moscow")

WEEKDAY_ALIASES = {
    0: ("понедельник", "понедельника", "пн"),
    1: ("вторник", "вторника", "вт"),
    2: ("среда", "среду", "ср"),
    3: ("четверг", "четверга", "чт"),
    4: ("пятница", "пятницу", "пт"),
    5: ("суббота", "субботу", "сб"),
    6: ("воскресенье", "воскресение", "воскрес", "вс"),
}


@dataclass(frozen=True)
class MeasurementDateMatch:
    date_key: str
    human_label: str
    source: str


def normalize_client_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").casefold().replace("ё", "е")).strip()


def looks_like_etiquette_complaint(text: str) -> bool:
    normalized = normalize_client_text(text)
    if not normalized:
        return False

    if "поздор" in normalized:
        return True

    complaint_words = ("грубо", "резко", "невеж", "культур", "уважен", "робот")
    identity_words = ("кто вы", "представ", "как вас зовут")
    return any(word in normalized for word in complaint_words + identity_words)


def build_etiquette_recovery_reply() -> str:
    return (
        "Здравствуйте. Вы правы, я слишком резко перешел к записи.\n\n"
        "Меня зовут Александр, я менеджер ISAEV GROUP. Помогу спокойно сориентироваться по ремонту.\n\n"
        "Если завтра вам удобно, подберу время замера. Напишите примерное время или выберите окно выше."
    )


def build_measurement_day_prompt() -> str:
    return (
        "Здравствуйте. Меня зовут Александр, я менеджер ISAEV GROUP.\n\n"
        "По вашим ответам уже вижу предварительный ориентир. Чтобы не гадать по деталям, лучше "
        "спокойно посмотреть объект на бесплатном замере. Это ни к чему не обязывает.\n\n"
        "Выберите, пожалуйста, удобный день."
    )


def build_measurement_time_prompt(match: MeasurementDateMatch, date_label: str) -> str:
    human_label = _capitalize_first(match.human_label)
    return (
        "Здравствуйте, Александр на связи.\n\n"
        f"{human_label} подойдет. Выберите, пожалуйста, удобное время на {date_label} — "
        "я закреплю окно за вами."
    )


def resolve_measurement_date_from_text(
    text: str,
    slots: Iterable[object],
    *,
    now: datetime | None = None,
) -> MeasurementDateMatch | None:
    normalized = normalize_client_text(text)
    if not normalized:
        return None

    offered_keys = _offered_date_keys(slots)
    if not offered_keys:
        return None

    current = (now or datetime.now(MOSCOW_TZ)).astimezone(MOSCOW_TZ)
    today = current.date()

    relative_match = _resolve_relative_date(normalized, today)
    if relative_match:
        date_key, label, source = relative_match
        return _match_offered_key(offered_keys, date_key, label, source)

    explicit_key = _extract_explicit_date_key(normalized, current.year)
    if explicit_key:
        return _match_offered_key(offered_keys, explicit_key, explicit_key, "explicit_date")

    weekday = _extract_weekday(normalized)
    if weekday is not None:
        for date_key in offered_keys:
            parsed = _parse_date_key(date_key)
            if parsed and parsed >= today and parsed.weekday() == weekday:
                return MeasurementDateMatch(date_key=date_key, human_label=date_key, source="weekday")

    return None


def _resolve_relative_date(normalized: str, today) -> tuple[str, str, str] | None:
    if "послезавтра" in normalized:
        target = today + timedelta(days=2)
        return target.isoformat(), "послезавтра", "relative_date"
    if "завтра" in normalized:
        target = today + timedelta(days=1)
        return target.isoformat(), "завтра", "relative_date"
    if "сегодня" in normalized:
        return today.isoformat(), "сегодня", "relative_date"
    return None


def _extract_explicit_date_key(normalized: str, year: int) -> str | None:
    match = re.search(r"\b([0-3]?\d)[./-]([01]?\d)\b", normalized)
    if not match:
        return None
    day = int(match.group(1))
    month = int(match.group(2))
    try:
        return datetime(year, month, day, tzinfo=MOSCOW_TZ).date().isoformat()
    except ValueError:
        return None


def _extract_weekday(normalized: str) -> int | None:
    for weekday, aliases in WEEKDAY_ALIASES.items():
        for alias in aliases:
            if re.search(rf"(?<![а-яa-z]){re.escape(alias)}(?![а-яa-z])", normalized):
                return weekday
    return None


def _offered_date_keys(slots: Iterable[object]) -> list[str]:
    keys: list[str] = []
    seen: set[str] = set()
    for slot in slots:
        start = getattr(slot, "start", None)
        if start is None and isinstance(slot, dict):
            start = slot.get("start")
        key = _slot_date_key(str(start or ""))
        if key and key not in seen:
            seen.add(key)
            keys.append(key)
    return keys


def _slot_date_key(value: str) -> str:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value[:10] if re.match(r"\d{4}-\d{2}-\d{2}", value) else ""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(MOSCOW_TZ).date().isoformat()


def _parse_date_key(date_key: str):
    try:
        return datetime.fromisoformat(date_key).date()
    except ValueError:
        return None


def _match_offered_key(
    offered_keys: list[str],
    date_key: str,
    label: str,
    source: str,
) -> MeasurementDateMatch | None:
    if date_key not in offered_keys:
        return None
    return MeasurementDateMatch(date_key=date_key, human_label=label, source=source)


def _capitalize_first(text: str) -> str:
    if not text:
        return text
    return text[:1].upper() + text[1:]
