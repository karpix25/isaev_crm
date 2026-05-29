from __future__ import annotations

from typing import Any


def normalize_quiz_design_answer(value: Any) -> str:
    """
    Normalize quiz design-project answers that may arrive as internal codes
    or already rendered labels from older quiz/client versions.
    """
    raw = str(value or "").strip().lower().replace("ё", "е")
    if not raw:
        return ""

    if raw in {"yes", "ready", "done"}:
        return "yes"
    if raw in {"wip", "process", "in_progress", "in progress"}:
        return "wip"
    if raw in {"no", "none", "not", "missing"}:
        return "no"

    if any(marker in raw for marker in ("в процессе", "разработ", "позже", "пока делаем")):
        return "wip"
    if any(marker in raw for marker in ("нет", "без проект", "проекта нет", "проект отсутств", "хочу в подарок")):
        return "no"
    if any(marker in raw for marker in ("да", "готов", "есть проект", "проект есть")):
        return "yes"

    return raw
