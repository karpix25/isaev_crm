"""Preliminary repair price calculation shared by quiz-like flows."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class QuizPrice:
    lo: int
    hi: int
    m2: int
    label: str

    def as_dict(self) -> dict[str, Any]:
        return {"lo": self.lo, "hi": self.hi, "m2": self.m2, "label": self.label}


def calculate_quiz_price(answers: dict[str, Any]) -> QuizPrice:
    area_mid = {"xs": 32, "sm": 55, "md": 85, "lg": 125}
    m2 = area_mid.get(str(answers.get("area") or ""), 55)
    wet_m2 = round(m2 * 0.15)

    if answers.get("rooms") == "partial":
        lo = _round_price(wet_m2 * 40000)
        hi = _round_price(wet_m2 * 60000)
        return QuizPrice(lo=lo, hi=hi, m2=wet_m2, label=f"{_format_price(lo)} – {_format_price(hi)}")

    if answers.get("rtype") == "cosm":
        rate_min, rate_max = 10000, 15000
    elif answers.get("rtype") == "finish":
        rate_min, rate_max = 18000, 23000
    else:
        rate_min, rate_max = 25000, 30000

    state_coef = {"rough": 1.0, "lived": 1.15, "demo": 1.3}
    rooms_coef = 0.7 if answers.get("rooms") == "several" else 1.0
    type_coef = {"flat": 1.0, "house": 1.2, "commercial": 1.1}

    coef = state_coef.get(str(answers.get("state") or ""), 1.0) * rooms_coef
    coef *= type_coef.get(str(answers.get("type") or ""), 1.0)

    lo = _round_price(m2 * rate_min * coef)
    hi = _round_price(m2 * rate_max * coef)
    return QuizPrice(lo=lo, hi=hi, m2=m2, label=f"{_format_price(lo)} – {_format_price(hi)}")


def _round_price(value: float) -> int:
    return round(value / 50000) * 50000


def _format_price(value: int) -> str:
    if value >= 1000000:
        return f"{value / 1000000:.1f}".replace(".", ",") + " млн ₽"
    return f"{round(value / 1000)} тыс. ₽"
