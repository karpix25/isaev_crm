from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class SalesReplyGuardrailResult:
    text: str
    blocked: bool
    reason: str | None = None


_PRICE_PROMISE_PATTERNS = (
    re.compile(r"\bточно\s+улож", re.I),
    re.compile(r"\bгарантир\w*\s+цен", re.I),
    re.compile(r"\bбез\s+доплат\b", re.I),
    re.compile(r"\bточная\s+стоимость\b", re.I),
)

_EARLY_CLOSE_PATTERNS = (
    re.compile(r"всего\s+добр", re.I),
    re.compile(r"больше\s+не\s+будем\s+беспокоить", re.I),
)


class SalesReplyGuardrailService:
    def validate(self, *, text: str, plan) -> SalesReplyGuardrailResult:
        normalized = str(text or "").strip()
        if not plan or not normalized:
            return SalesReplyGuardrailResult(text=normalized, blocked=False)

        if any(pattern.search(normalized) for pattern in _PRICE_PROMISE_PATTERNS):
            return self._fallback(plan, "price_promise")
        if any(pattern.search(normalized) for pattern in _EARLY_CLOSE_PATTERNS):
            return self._fallback(plan, "early_close")
        if normalized.count("?") > 1:
            return self._fallback(plan, "too_many_questions")
        if self._pushes_only_measurement(normalized, plan):
            return self._fallback(plan, "measurement_only_push")

        return SalesReplyGuardrailResult(text=normalized, blocked=False)

    def _pushes_only_measurement(self, text: str, plan) -> bool:
        lowered = text.lower()
        if "замер" not in lowered:
            return False
        return plan.strategy.next_best_action in {
            "ask_budget_or_comparison",
            "offer_budget_paths",
            "ask_measurement_concern",
        } and not any(word in lowered for word in ("путь", "вариант", "уточню", "сравн", "бюджет"))

    def _fallback(self, plan, reason: str) -> SalesReplyGuardrailResult:
        strategy = plan.strategy.name
        if strategy == "near_budget_two_paths":
            text = (
                f"Понимаю, ориентир {plan.intent.client_budget_text} рядом с нашей вилкой. "
                "Тут обычно два пути: держаться ближе к нижней границе за счет решений попроще или разбить часть работ на этапы. "
                "Что для вас важнее?"
            )
        elif strategy == "below_budget_honest_options":
            text = (
                f"Понимаю, ориентир {plan.intent.client_budget_text}. "
                "Чтобы не уговаривать вслепую, лучше сначала понять приоритет: важнее уложиться в бюджет или сохранить полный объем работ?"
            )
        elif strategy == "diagnose_price_objection":
            text = (
                "Понимаю, бюджет важный момент. Уточню, чтобы не уговаривать вслепую: "
                "вопрос больше в общем бюджете, в том, что непонятно, что входит, или есть с чем сравниваете?"
            )
        else:
            text = "Понимаю. Уточню один момент, чтобы ответить точнее: что сейчас больше всего смущает в следующем шаге?"
        return SalesReplyGuardrailResult(text=text, blocked=True, reason=reason)


sales_reply_guardrail_service = SalesReplyGuardrailService()
