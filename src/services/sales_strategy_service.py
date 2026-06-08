from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from src.services.sales_intent_service import SalesIntent


@dataclass(frozen=True)
class SalesStrategy:
    name: str
    next_best_action: str
    budget_fit: str = "unknown"
    prompt_instruction: str = ""
    allowed_ctas: tuple[str, ...] = ()
    escalate: bool = False


class SalesStrategyService:
    def select(self, *, lead, intent: SalesIntent) -> SalesStrategy:
        price = self._price_data(lead)
        budget_fit = self._budget_fit(
            budget_rub=intent.client_budget_rub,
            price_lo=self._positive_int(price.get("lo")),
            price_hi=self._positive_int(price.get("hi")),
        )

        if intent.name in {"price_objection", "budget_given"}:
            return self._price_strategy(intent=intent, budget_fit=budget_fit)
        if intent.name == "competitor_comparison":
            return SalesStrategy(
                name="compare_equal_scope",
                next_best_action="ask_competitor_scope",
                prompt_instruction=(
                    "Не спорь с конкурентами. Попроси сравнить одинаковый объем работ: что включено, "
                    "есть ли демонтаж, черновые работы, гарантия и фиксация сметы."
                ),
                allowed_ctas=("compare_scope", "manager_handoff"),
                escalate=True,
            )
        if intent.name == "scope_confusion":
            return SalesStrategy(
                name="explain_scope",
                next_best_action="explain_price_scope",
                prompt_instruction="Коротко объясни, что вилка предварительная и зависит от состава работ. Задай один вопрос о том, что именно непонятно.",
                allowed_ctas=("explain_scope", "measurement_after_clarity"),
            )
        if intent.name == "hidden_cost_fear":
            return SalesStrategy(
                name="reduce_hidden_cost_risk",
                next_best_action="explain_estimate_process",
                prompt_instruction="Сними страх скрытых доплат: скажи, что после замера фиксируют объем и становится ясно, где риски.",
                allowed_ctas=("explain_process", "offer_measurement_slots"),
            )
        if intent.name == "measurement_objection":
            return SalesStrategy(
                name="diagnose_measurement_objection",
                next_best_action="ask_measurement_concern",
                prompt_instruction="Не дави на замер. Уточни, что смущает: время, обязательства, доверие или желание сначала понять состав работ.",
                allowed_ctas=("diagnose", "manager_handoff"),
            )
        if intent.name == "decision_maker_needed":
            return SalesStrategy(
                name="support_decision_maker",
                next_best_action="help_prepare_summary",
                prompt_instruction="Предложи коротко сформулировать для человека, с кем клиент советуется: бюджет, этапы, что уточнит замер.",
                allowed_ctas=("send_summary", "follow_up_later"),
            )
        if intent.name == "thinking":
            return SalesStrategy(
                name="clarify_thinking_barrier",
                next_best_action="ask_one_uncertainty",
                prompt_instruction=(
                    "Не подгоняй, но не отпускай диалог в пассивное ожидание. "
                    "Признай, что подумать нормально, и задай один диагностический вопрос: "
                    "что сейчас больше смущает — бюджет, состав работ, материалы или сам замер? "
                    "Не пиши в стиле 'когда будете готовы, дайте сигнал'."
                ),
                allowed_ctas=("diagnose_budget", "explain_scope", "diagnose_measurement"),
            )

        return SalesStrategy(
            name="diagnose",
            next_best_action="ask_one_question",
            prompt_instruction="Задай один спокойный уточняющий вопрос и не закрывай диалог.",
            allowed_ctas=("diagnose",),
        )

    def _price_strategy(self, *, intent: SalesIntent, budget_fit: str) -> SalesStrategy:
        if not intent.client_budget_rub:
            return SalesStrategy(
                name="diagnose_price_objection",
                next_best_action="ask_budget_or_comparison",
                budget_fit=budget_fit,
                prompt_instruction=(
                    "Признай, что бюджет важен. Не веди сразу на замер. Задай один диагностический вопрос: "
                    "вопрос в общем бюджете, непонятно что входит, или клиент сравнивает с другим предложением?"
                ),
                allowed_ctas=("diagnose_budget", "explain_scope", "compare_scope"),
            )
        if budget_fit in {"inside_range", "near_low"}:
            return SalesStrategy(
                name="near_budget_two_paths",
                next_best_action="offer_budget_paths",
                budget_fit=budget_fit,
                prompt_instruction=(
                    "Зафиксируй, что ориентир клиента рядом с нашей вилкой. Не обещай уложиться. "
                    "Предложи два пути: держаться ближе к нижней границе за счет решений проще или разбить часть работ на этапы. "
                    "Задай один вопрос, какой путь для клиента важнее."
                ),
                allowed_ctas=("optimize_budget", "stage_project", "offer_measurement_slots_after_answer"),
            )
        if budget_fit == "below_range":
            return SalesStrategy(
                name="below_budget_honest_options",
                next_best_action="offer_scope_optimization",
                budget_fit=budget_fit,
                prompt_instruction=(
                    "Честно скажи, что бюджет может быть ниже комплексного ремонта. Не прощайся. "
                    "Предложи понять, какие работы можно перенести на второй этап или упростить, и задай один вопрос о приоритете."
                ),
                allowed_ctas=("stage_project", "reduce_scope", "manager_handoff"),
                escalate=True,
            )
        return SalesStrategy(
            name="budget_needs_clarity",
            next_best_action="diagnose_budget",
            budget_fit=budget_fit,
            prompt_instruction="Уточни бюджетный ориентир и что для клиента важнее: цена, сроки или понятный состав работ.",
            allowed_ctas=("diagnose_budget",),
        )

    def _price_data(self, lead) -> dict[str, Any]:
        data = self._lead_data(lead)
        quiz = data.get("quiz") if isinstance(data.get("quiz"), dict) else {}
        price = quiz.get("price") if isinstance(quiz.get("price"), dict) else {}
        return price

    def _lead_data(self, lead) -> dict[str, Any]:
        raw = getattr(lead, "extracted_data", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    def _budget_fit(self, *, budget_rub: int | None, price_lo: int | None, price_hi: int | None) -> str:
        if not budget_rub:
            return "unknown"
        if price_lo and price_hi and price_lo <= budget_rub <= price_hi:
            return "inside_range"
        if price_lo and budget_rub >= int(price_lo * 0.85):
            return "near_low"
        if price_lo and budget_rub < int(price_lo * 0.85):
            return "below_range"
        return "unknown"

    def _positive_int(self, value: Any) -> int | None:
        try:
            parsed = int(value)
            return parsed if parsed > 0 else None
        except Exception:
            return None


sales_strategy_service = SalesStrategyService()
