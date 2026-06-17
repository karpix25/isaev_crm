from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from src.services.measurement_text_intents import (
    build_etiquette_recovery_reply,
    build_measurement_day_prompt,
    build_measurement_time_prompt,
    looks_like_etiquette_complaint,
    resolve_measurement_date_from_text,
)


@dataclass
class Slot:
    start: str


def test_resolves_tomorrow_to_offered_measurement_date():
    slots = [
        Slot("2026-06-17T10:00:00+03:00"),
        Slot("2026-06-18T14:00:00+03:00"),
    ]

    match = resolve_measurement_date_from_text(
        "завтра",
        slots,
        now=datetime(2026, 6, 17, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    assert match is not None
    assert match.date_key == "2026-06-18"
    assert match.human_label == "завтра"


def test_resolves_weekday_to_first_matching_offered_date():
    slots = [
        Slot("2026-06-18T10:00:00+03:00"),
        Slot("2026-06-19T14:00:00+03:00"),
    ]

    match = resolve_measurement_date_from_text(
        "давайте в пятницу",
        slots,
        now=datetime(2026, 6, 17, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    assert match is not None
    assert match.date_key == "2026-06-19"


def test_detects_etiquette_complaint_about_greeting():
    assert looks_like_etiquette_complaint("могли бы и поздороваться для начала")


def test_measurement_prompts_are_polite_and_identified():
    day_prompt = build_measurement_day_prompt()
    recovery_prompt = build_etiquette_recovery_reply()

    assert "Здравствуйте" in day_prompt
    assert "Александр" in day_prompt
    assert "ни к чему не обязывает" in day_prompt
    assert "Александр" in recovery_prompt


def test_measurement_time_prompt_keeps_date_and_polite_tone():
    match = resolve_measurement_date_from_text(
        "завтра",
        [Slot("2026-06-18T14:00:00+03:00")],
        now=datetime(2026, 6, 17, 9, 0, tzinfo=ZoneInfo("Europe/Moscow")),
    )

    assert match is not None
    prompt = build_measurement_time_prompt(match, "18.06 чт")

    assert "Здравствуйте" in prompt
    assert "Александр" in prompt
    assert "Завтра подойдет" in prompt
    assert "18.06 чт" in prompt
