"""Shared Telegram keyboards and labels for measurement slot selection."""

from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


RU_WEEKDAYS_SHORT = ["пн", "вт", "ср", "чт", "пт", "сб", "вс"]


def slot_local_datetime(value: str) -> datetime | None:
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(ZoneInfo("Europe/Moscow"))


def slot_date_key(value: str) -> str:
    dt = slot_local_datetime(value)
    return dt.strftime("%Y-%m-%d") if dt else value[:10]


def slot_date_button_label(date_key: str) -> str:
    try:
        dt = datetime.fromisoformat(date_key).replace(tzinfo=ZoneInfo("Europe/Moscow"))
    except ValueError:
        return date_key
    return f"{dt.strftime('%d.%m')} {RU_WEEKDAYS_SHORT[dt.weekday()]}"


def slot_time_label(value: str) -> str:
    dt = slot_local_datetime(value)
    return dt.strftime("%H:%M") if dt else value


def build_measurement_date_keyboard(slots) -> InlineKeyboardMarkup:
    grouped: dict[str, list] = {}
    for slot in slots:
        grouped.setdefault(slot_date_key(slot.start), []).append(slot)

    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for date_key in list(grouped.keys())[:7]:
        row.append(
            InlineKeyboardButton(
                text=slot_date_button_label(date_key),
                callback_data=f"quiz_measure_date:{date_key}",
            )
        )
        if len(row) == 2:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def build_measurement_time_keyboard(slots, date_key: str) -> InlineKeyboardMarkup:
    matching_slots = [slot for slot in slots if slot_date_key(slot.start) == date_key]
    buttons: list[list[InlineKeyboardButton]] = []
    row: list[InlineKeyboardButton] = []
    for slot in matching_slots[:10]:
        row.append(
            InlineKeyboardButton(
                text=slot_time_label(slot.start),
                callback_data=f"quiz_measure_time:{slot.start}",
            )
        )
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton(text="← Выбрать другой день", callback_data="quiz_measure_back")])
    return InlineKeyboardMarkup(inline_keyboard=buttons)
