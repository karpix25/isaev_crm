import ast
import asyncio
import importlib.util
import inspect
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock
from zoneinfo import ZoneInfo


def _load_quiz_value_normalizer():
    module_path = Path(__file__).parent / "src" / "services" / "quiz_value_normalizer.py"
    spec = importlib.util.spec_from_file_location("quiz_value_normalizer_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module.normalize_quiz_design_answer


normalize_quiz_design_answer = _load_quiz_value_normalizer()


def _load_lead_handler_functions():
    module_path = Path(__file__).parent / "src" / "bot" / "handlers" / "lead_handler.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    function_nodes = [
        node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    for node in function_nodes:
        node.decorator_list = []
    module = ast.Module(body=function_nodes, type_ignores=[])
    ast.fix_missing_locations(module)

    namespace = {
        "asyncio": asyncio,
        "json": json,
        "re": re,
        "datetime": datetime,
        "timezone": timezone,
        "timedelta": object,
        "ZoneInfo": ZoneInfo,
        "AsyncSession": object,
        "Message": object,
        "normalize_quiz_design_answer": normalize_quiz_design_answer,
        "QUIZ_SUMMARY_FIELDS": (
            ("type", "Объект"),
            ("area", "Площадь"),
            ("rtype", "Ремонт"),
            ("design", "Дизайн"),
        ),
        "QUIZ_LABELS": {
            "type": {"commercial": "Коммерция"},
            "area": {"md": "70–100 м²"},
            "rtype": {"full": "Под ключ"},
            "design": {"no": "Проекта нет"},
        },
        "LeadStatus": SimpleNamespace(
            NEW=SimpleNamespace(value="NEW"),
            QUIZ_COMPLETED=SimpleNamespace(value="QUIZ_COMPLETED"),
            MESSENGER_PENDING=SimpleNamespace(value="MESSENGER_PENDING"),
            CONSULTING=SimpleNamespace(value="CONSULTING"),
            QUALIFIED=SimpleNamespace(value="QUALIFIED"),
            MEASUREMENT_PENDING=SimpleNamespace(value="MEASUREMENT_PENDING"),
            MEASUREMENT_BOOKED=SimpleNamespace(value="MEASUREMENT_BOOKED"),
            MEASUREMENT=SimpleNamespace(value="MEASUREMENT"),
            LOST=SimpleNamespace(value="LOST"),
        ),
        "chat_service": SimpleNamespace(send_outbound_message=AsyncMock()),
        "measurement_analytics_service": SimpleNamespace(record_event=AsyncMock()),
    }
    exec(compile(module, str(module_path), "exec"), namespace)
    return namespace


LEAD_HANDLER = _load_lead_handler_functions()


def _patch_outbound_helpers(monkeypatch):
    calls = {}

    async def fake_outbound(*args, **kwargs):
        return True

    for name, value in list(LEAD_HANDLER.items()):
        if name.startswith(("_send_", "_answer_")) and inspect.iscoroutinefunction(value):
            mock = AsyncMock(side_effect=fake_outbound)
            monkeypatch.setitem(LEAD_HANDLER, name, mock)
            calls[name] = mock

    return calls


async def _route_text(text, monkeypatch, *, measurement_booked=True, next_action="general_consultation", lead=None):
    calls = _patch_outbound_helpers(monkeypatch)
    monkeypatch.setitem(
        LEAD_HANDLER,
        "_lead_measurement_data",
        lambda lead: {"start": "2026-06-01T10:00:00+03:00"} if measurement_booked else {},
    )
    lead = lead or SimpleNamespace(
        id=1,
        status="MEASUREMENT_BOOKED" if measurement_booked else "CONSULTING",
        ai_qualification_status="in_progress",
    )
    stage_context = SimpleNamespace(metadata={"next_action": next_action})

    message = SimpleNamespace(answer=AsyncMock())
    db = SimpleNamespace(commit=AsyncMock())
    routed = await LEAD_HANDLER["_try_route_scenario_before_ai"](
        db,
        message,
        lead,
        text,
        stage_context,
    )

    return routed, calls, lead, message, db


def test_routes_measurement_cancellation_before_ai(monkeypatch):
    routed, calls, lead, message, db = asyncio.run(
        _route_text(
            "Отмените замер, пожалуйста. Запись больше не нужна.",
            monkeypatch,
            measurement_booked=True,
        )
    )

    assert routed is True
    assert calls["_send_measurement_slot_dates"].await_count == 0
    assert calls["_send_measurement_reschedule_slot_dates"].await_count == 0
    assert calls["_send_measurement_change_choices"].await_count == 0
    assert message.answer.await_count == 1
    assert db.commit.await_count == 1
    extracted_data = json.loads(lead.extracted_data)
    assert extracted_data["measurement"]["status"] in {"cancelled", "cancel_requested"}


def test_routes_do_not_contact_abusive_and_not_interested_before_ai(monkeypatch):
    examples = [
        "Не пишите мне больше и удалите мой номер из базы.",
        "Да пошли вы, больше не звоните.",
        "Неинтересно, ремонт уже сделали с другой компанией.",
    ]

    for text in examples:
        routed, calls, lead, message, db = asyncio.run(_route_text(text, monkeypatch, measurement_booked=False))

        assert routed is True, text
        assert message.answer.await_count == 1, text
        assert db.commit.await_count == 1, text
        assert lead.status == "LOST", text
        assert lead.ai_qualification_status == "not_interested", text


def test_routes_reactivation_before_ai(monkeypatch):
    lead = SimpleNamespace(
        id=2,
        status="LOST",
        ai_qualification_status="not_interested",
    )

    routed, calls, lead, message, db = asyncio.run(
        _route_text(
            "Здравствуйте, снова актуально. Хотим вернуться к расчету ремонта.",
            monkeypatch,
            measurement_booked=False,
            lead=lead,
        )
    )

    assert routed is True
    assert message.answer.await_count == 1
    assert db.commit.await_count == 1
    assert lead.status == "MEASUREMENT_PENDING"
    assert lead.ai_qualification_status == "in_progress"


def test_routes_measurement_acknowledgement_before_ai(monkeypatch):
    routed, calls, lead, message, db = asyncio.run(
        _route_text(
            "хорошо",
            monkeypatch,
            measurement_booked=True,
            next_action="confirm_measurement",
        )
    )

    calls["_answer_measurement_question_if_possible"].side_effect = None
    calls["_answer_measurement_question_if_possible"].return_value = False

    routed = asyncio.run(
        LEAD_HANDLER["_try_route_scenario_before_ai"](
            db,
            message,
            lead,
            "хорошо",
            SimpleNamespace(metadata={"next_action": "confirm_measurement"}),
        )
    )

    assert routed is True
    assert calls["_send_measurement_acknowledgement"].await_count == 1
    assert calls["_send_measurement_slot_dates"].await_count == 0


def test_extract_ai_tool_action_normalizes_aliases_and_none():
    extract_tool_action = LEAD_HANDLER["_extract_ai_tool_action"]

    assert extract_tool_action({"tool_action": "calendar"}) == "show_measurement_slots"
    assert extract_tool_action({"tool_action": "cancel_booking"}) == "cancel_measurement"
    assert extract_tool_action({"requested_tool": {"name": "manager_handoff"}}) == "handoff_to_manager"
    assert extract_tool_action({"tool_action": "none"}) == ""
    assert extract_tool_action({"message": "Просто ответ клиенту"}) == ""


def test_ai_support_tools_prompt_keeps_orchestration_off_client_text():
    build_prompt = LEAD_HANDLER["_build_ai_support_tools_prompt"]
    stage_context = SimpleNamespace(metadata={"next_action": "awaiting_measurement_slot"})

    prompt = build_prompt(stage_context)

    assert "SCENARIO_ORCHESTRATION" in prompt
    assert "Главный сценарий ведет бот" in prompt
    assert "ИИ только отвечает на вопросы поддержки" in prompt
    assert "не обещай выполнить его текстом" in prompt
    assert "Верни tool_action в JSON" in prompt
    assert "Не выводи клиенту названия инструментов, JSON, markdown-блоки или рассуждения" in prompt
    assert "Текущий next_action CRM: awaiting_measurement_slot" in prompt
    assert '"message": "короткий ответ клиенту' in prompt
    assert '"tool_action": "none"' in prompt


def test_ai_support_tools_prompt_routes_pressure_sensitive_states_gently():
    build_prompt = LEAD_HANDLER["_build_ai_support_tools_prompt"]

    prompt = build_prompt(SimpleNamespace(metadata={"next_action": "lost_or_paused"}))

    assert 'tool_action = "none", status = "LOST"' in prompt
    assert "message должен быть коротким без продолжения продажи" in prompt
    assert "Если клиент сам вернулся после отказа" in prompt


def test_quiz_design_normalizer_handles_codes_and_rendered_labels():
    assert normalize_quiz_design_answer("no") == "no"
    assert normalize_quiz_design_answer("Проекта нет") == "no"
    assert normalize_quiz_design_answer("Нет — хочу в подарок!") == "no"
    assert normalize_quiz_design_answer("В процессе разработки") == "wip"
    assert normalize_quiz_design_answer("Да, уже готов") == "yes"


def test_quiz_estimate_text_uses_normalized_design_answer():
    build_estimate = LEAD_HANDLER["_build_quiz_estimate_text"]
    lead = SimpleNamespace(
        extracted_data=json.dumps(
            {
                "quiz": {
                    "price": {"label": "3,0 млн ₽ – 3,6 млн ₽"},
                    "answers": {"type": "commercial", "area": "md", "rtype": "full", "design": "Проекта нет"},
                }
            },
            ensure_ascii=False,
        )
    )

    text = build_estimate(lead)

    assert "Предварительная цена по работам без стройматериалов" in text
    assert "лучше выбрать удобное время бесплатного замера" in text
    assert "Если пришлете сюда дизайн-проект" not in text


def test_unavailable_measurement_calendar_is_handled_by_bot_template(monkeypatch):
    send_outbound = AsyncMock()
    monkeypatch.setitem(
        LEAD_HANDLER,
        "chat_service",
        SimpleNamespace(send_outbound_message=send_outbound),
    )
    monkeypatch.setitem(
        LEAD_HANDLER,
        "cal_pro_service",
        SimpleNamespace(is_configured=lambda: False),
    )

    message = SimpleNamespace(answer=AsyncMock(return_value=SimpleNamespace(message_id=10)))
    db = SimpleNamespace()
    lead = SimpleNamespace(id=123)

    handled = asyncio.run(LEAD_HANDLER["_send_measurement_slot_dates"](message, db, lead))

    assert handled is True
    assert message.answer.await_count == 1
    kwargs = send_outbound.await_args.kwargs
    assert kwargs["sender_name"] == "Bot"
    assert kwargs["ai_metadata"]["engine"] == "bot_template"
    assert kwargs["ai_metadata"]["type"] == "measurement_slots_unavailable"
