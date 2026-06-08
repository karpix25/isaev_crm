import json
from types import SimpleNamespace

from src.services.sales_intent_service import sales_intent_service
from src.services.sales_orchestration_service import sales_orchestration_service
from src.services.sales_reply_guardrail_service import sales_reply_guardrail_service
from src.services.sales_strategy_service import sales_strategy_service


def _lead_with_price(lo=900_000, hi=1_100_000):
    return SimpleNamespace(
        id="lead-1",
        extracted_data=json.dumps(
            {
                "quiz": {
                    "price": {
                        "lo": lo,
                        "hi": hi,
                        "label": "900 тыс. ₽ – 1,1 млн ₽",
                    }
                }
            },
            ensure_ascii=False,
        ),
    )


def test_sales_intent_does_not_treat_negated_price_as_objection():
    assert sales_intent_service.classify("Не дорого, нормально") is None


def test_budget_near_range_selects_two_path_strategy():
    lead = _lead_with_price()
    intent = sales_intent_service.classify("Ориентир до миллиона рублей")

    assert intent
    strategy = sales_strategy_service.select(lead=lead, intent=intent)

    assert strategy.name == "near_budget_two_paths"
    assert strategy.budget_fit == "inside_range"
    assert "два пути" in strategy.prompt_instruction
    assert "Не обещай уложиться" in strategy.prompt_instruction


def test_orchestration_marks_sales_state_for_followups_and_metrics():
    lead = _lead_with_price()
    plan = sales_orchestration_service.plan_turn(
        lead=lead,
        text="Стоимость не подходит, у нас до миллиона",
    )

    assert plan
    sales_orchestration_service.mark_lead(
        lead=lead,
        plan=plan,
        source_text="Стоимость не подходит, у нас до миллиона",
    )

    data = json.loads(lead.extracted_data)
    sales_state = data["sales_state"]
    assert sales_state["current_intent"] == "budget_given"
    assert sales_state["current_objection"] == "price"
    assert sales_state["budget_fit"] == "inside_range"
    assert sales_state["next_best_action"] == "offer_budget_paths"
    assert data["conversation_mode"] == "budget_given"


def test_sales_prompt_requires_diagnosis_before_measurement_push():
    lead = _lead_with_price()
    plan = sales_orchestration_service.plan_turn(
        lead=lead,
        text="Дорого, спасибо",
    )

    assert plan
    assert "If the reason is unclear, diagnose before offering measurement slots" in plan.prompt_block
    assert "Ask no more than one question" in plan.prompt_block


def test_guardrail_blocks_price_promises_and_uses_safe_fallback():
    lead = _lead_with_price()
    plan = sales_orchestration_service.plan_turn(
        lead=lead,
        text="Ориентир до миллиона рублей",
    )

    result = sales_reply_guardrail_service.validate(
        text="Точно уложимся в миллион без доплат. Запишем на замер?",
        plan=plan,
    )

    assert result.blocked
    assert result.reason == "price_promise"
    assert "Точно уложимся" not in result.text
    assert "Что для вас важнее?" in result.text


def test_thinking_strategy_keeps_diagnostic_control():
    lead = _lead_with_price()
    plan = sales_orchestration_service.plan_turn(
        lead=lead,
        text="не знаю я подумаю",
    )

    assert plan
    assert plan.strategy.name == "clarify_thinking_barrier"
    assert "не отпускай диалог" in plan.strategy.prompt_instruction
    assert "бюджет, состав работ, материалы или сам замер" in plan.strategy.prompt_instruction
    assert "дайте сигнал" in plan.strategy.prompt_instruction


def test_guardrail_blocks_passive_wait_after_thinking_reply():
    lead = _lead_with_price()
    plan = sales_orchestration_service.plan_turn(
        lead=lead,
        text="не знаю я подумаю",
    )

    result = sales_reply_guardrail_service.validate(
        text=(
            "Понимаю, спешить не стоит. Если сейчас есть вопросы, дайте знать. "
            "А когда будете готовы двигаться дальше, просто дайте сигнал."
        ),
        plan=plan,
    )

    assert result.blocked
    assert result.reason == "passive_wait"
    assert "дайте сигнал" not in result.text
    assert "что сейчас больше смущает" in result.text
