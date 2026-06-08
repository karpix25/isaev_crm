from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.services.sales_intent_service import SalesIntent, sales_intent_service
from src.services.sales_strategy_service import SalesStrategy, sales_strategy_service


@dataclass(frozen=True)
class SalesTurnPlan:
    intent: SalesIntent
    strategy: SalesStrategy
    prompt_block: str
    metadata: dict[str, Any]


class SalesOrchestrationService:
    def plan_turn(self, *, lead, text: str) -> SalesTurnPlan | None:
        intent = sales_intent_service.classify(text)
        if not intent or intent.name == "do_not_contact":
            return None

        strategy = sales_strategy_service.select(lead=lead, intent=intent)
        metadata = self._metadata(intent=intent, strategy=strategy)
        prompt_block = self._prompt_block(intent=intent, strategy=strategy)
        return SalesTurnPlan(
            intent=intent,
            strategy=strategy,
            prompt_block=prompt_block,
            metadata=metadata,
        )

    def mark_lead(self, *, lead, plan: SalesTurnPlan, source_text: str) -> dict[str, Any]:
        data = self._lead_data(lead)
        now = datetime.now(timezone.utc).isoformat()
        sales_state = data.get("sales_state") if isinstance(data.get("sales_state"), dict) else {}
        objection_count = int(sales_state.get("objection_count") or 0)
        if plan.intent.name.endswith("objection") or plan.intent.name in {"budget_given", "competitor_comparison"}:
            objection_count += 1

        sales_state.update(
            {
                "current_intent": plan.intent.name,
                "current_objection": self._objection_name(plan.intent.name),
                "objection_count": objection_count,
                "client_budget_text": plan.intent.client_budget_text,
                "client_budget_rub": plan.intent.client_budget_rub,
                "budget_fit": plan.strategy.budget_fit,
                "last_strategy": plan.strategy.name,
                "next_best_action": plan.strategy.next_best_action,
                "followup_strategy": plan.strategy.name,
                "confidence": plan.intent.confidence,
                "updated_at": now,
            }
        )
        data["sales_state"] = sales_state
        data["conversation_mode"] = plan.intent.name
        data["conversation_mode_reason"] = source_text[:300]
        data["conversation_mode_updated_at"] = now
        lead.extracted_data = json.dumps(data, ensure_ascii=False)
        return data

    def _prompt_block(self, *, intent: SalesIntent, strategy: SalesStrategy) -> str:
        return (
            "SALES ORCHESTRATION CONTEXT:\n"
            f"- Detected client intent: {intent.name} (confidence {intent.confidence:.2f}).\n"
            f"- Client budget text: {intent.client_budget_text or 'unknown'}.\n"
            f"- Client budget rub: {intent.client_budget_rub or 'unknown'}.\n"
            f"- Budget fit: {strategy.budget_fit}.\n"
            f"- Selected strategy: {strategy.name}.\n"
            f"- Next best action: {strategy.next_best_action}.\n"
            f"- Allowed CTAs: {', '.join(strategy.allowed_ctas) or 'diagnose'}.\n"
            f"- Strategy instruction: {strategy.prompt_instruction}\n"
            "Rules for this turn:\n"
            "- Do not close the lead after one objection.\n"
            "- Ask no more than one question.\n"
            "- Do not promise a final price, discounts, exact deadlines, or no extra costs before measurement/estimate.\n"
            "- If the reason is unclear, diagnose before offering measurement slots.\n"
            "- If measurement is mentioned, frame it as a safe way to remove uncertainty, not as pressure."
        )

    def _metadata(self, *, intent: SalesIntent, strategy: SalesStrategy) -> dict[str, Any]:
        return {
            "intent": intent.name,
            "intent_confidence": intent.confidence,
            "client_budget_text": intent.client_budget_text,
            "client_budget_rub": intent.client_budget_rub,
            "strategy": strategy.name,
            "next_best_action": strategy.next_best_action,
            "budget_fit": strategy.budget_fit,
            "escalate": strategy.escalate,
        }

    def _objection_name(self, intent_name: str) -> str | None:
        if intent_name == "budget_given":
            return "price"
        if intent_name.endswith("_objection"):
            return intent_name.removesuffix("_objection")
        if intent_name in {"competitor_comparison", "scope_confusion", "hidden_cost_fear"}:
            return intent_name
        return None

    def _lead_data(self, lead) -> dict[str, Any]:
        raw = getattr(lead, "extracted_data", None)
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}


sales_orchestration_service = SalesOrchestrationService()
