from __future__ import annotations

from dataclasses import dataclass
from typing import Any


AREA_LABELS = {
    "xs": "до 40 м²",
    "sm": "40–70 м²",
    "md": "70–100 м²",
    "lg": "100+ м²",
}

BUDGET_LABELS = {
    "b1": "до 1 млн ₽",
    "b2": "1–2 млн ₽",
    "b3": "2–4 млн ₽",
    "b4": "от 4 млн ₽",
}

DEADLINE_LABELS = {
    "asap": "как можно скорее",
    "soon": "в течение 1–3 месяцев",
    "later": "не спешу",
}

OBJECT_LABELS = {
    "apt": "квартира",
    "house": "дом",
    "commercial": "коммерция",
}


@dataclass(frozen=True)
class QuizHotLeadDecision:
    is_hot: bool
    reason: str
    matched_rules: tuple[str, ...] = ()

    def as_dict(self) -> dict[str, Any]:
        return {
            "is_hot": self.is_hot,
            "reason": self.reason,
            "matched_rules": list(self.matched_rules),
        }


class QuizHotLeadService:
    """
    Deterministic hot-lead scoring for completed quiz answers.

    AI may still qualify free-form conversations, but quiz answers are already
    structured enough to trigger manager attention without waiting for a chat.
    """

    HIGH_VALUE_AREAS = {"sm", "md", "lg"}
    STRONG_AREAS = {"md", "lg"}
    HIGH_VALUE_BUDGETS = {"b2", "b3", "b4"}
    STRONG_BUDGETS = {"b3", "b4"}
    NEAR_DEADLINES = {"asap", "soon"}

    def evaluate(self, answers: dict[str, Any] | None) -> QuizHotLeadDecision:
        if not answers:
            return QuizHotLeadDecision(False, "Нет ответов квиза")

        area = self._value(answers.get("area") or answers.get("area_sqm"))
        budget = self._value(answers.get("budget") or answers.get("budget_range"))
        deadline = self._value(answers.get("deadline") or answers.get("start_time"))
        object_type = self._value(answers.get("type") or answers.get("object_type") or answers.get("property_type"))

        matched: list[str] = []
        if area in self.HIGH_VALUE_AREAS:
            matched.append(f"площадь {AREA_LABELS.get(area, area)}")
        if budget in self.HIGH_VALUE_BUDGETS:
            matched.append(f"бюджет {BUDGET_LABELS.get(budget, budget)}")
        if deadline in self.NEAR_DEADLINES:
            matched.append(f"срок {DEADLINE_LABELS.get(deadline, deadline)}")

        if area in self.HIGH_VALUE_AREAS and budget in self.HIGH_VALUE_BUDGETS and deadline in self.NEAR_DEADLINES:
            return QuizHotLeadDecision(True, f"Квиз: {', '.join(matched)}", tuple(matched))

        if area in self.STRONG_AREAS and budget in self.STRONG_BUDGETS:
            reason = f"Квиз: крупный объект и высокий бюджет ({', '.join(matched[:2])})"
            return QuizHotLeadDecision(True, reason, tuple(matched[:2]))

        if object_type == "commercial" and budget in self.STRONG_BUDGETS:
            object_label = OBJECT_LABELS.get(object_type, object_type)
            budget_label = BUDGET_LABELS.get(budget, budget)
            return QuizHotLeadDecision(
                True,
                f"Квиз: {object_label}, бюджет {budget_label}",
                (f"объект {object_label}", f"бюджет {budget_label}"),
            )

        if matched:
            return QuizHotLeadDecision(False, f"Есть признаки интереса: {', '.join(matched)}", tuple(matched))
        return QuizHotLeadDecision(False, "Нет горячих признаков по квизу")

    def _value(self, value: Any) -> str:
        return str(value or "").strip().lower()


quiz_hot_lead_service = QuizHotLeadService()
