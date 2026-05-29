import importlib.util
import ast
from pathlib import Path


def _load_prompts_module():
    module_path = Path(__file__).parent / "src" / "services" / "prompts.py"
    spec = importlib.util.spec_from_file_location("prompts_for_test", module_path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def _load_followup_constant(name: str):
    module_path = Path(__file__).parent / "src" / "services" / "followup_service.py"
    tree = ast.parse(module_path.read_text(encoding="utf-8"))

    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    return ast.literal_eval(node.value)

    raise AssertionError(f"{name} constant not found")


PROMPTS = _load_prompts_module()
MAX_FOLLOWUPS = _load_followup_constant("MAX_FOLLOWUPS")
STAGE_FOLLOWUP_THRESHOLDS = _load_followup_constant("STAGE_FOLLOWUP_THRESHOLDS")


def _compact(text: str) -> str:
    return " ".join(text.lower().split())


def test_core_prompts_contain_care_first_messenger_style_contract():
    prompt_bundle = _compact(
        "\n".join(
            [
                PROMPTS.SALES_AGENT_SYSTEM_PROMPT,
                PROMPTS.FOLLOWUP_PROMPT,
                PROMPTS.STAGE_FOLLOWUP_PROMPT,
            ]
        )
    )

    assert "care-first стиль" in prompt_bundle
    assert "через ясность, заботу" in prompt_bundle
    assert "пиши как живой человек" in prompt_bundle
    assert "пиши как живой человек в мессенджере" in prompt_bundle
    assert "коротко, спокойно, без давления" in prompt_bundle
    assert "не будь навязчивым" in prompt_bundle
    assert "как робот" in prompt_bundle
    assert "один вопрос за раз" in prompt_bundle
    assert "не повторяй вопросы" in prompt_bundle


def test_stage_followup_prompt_prefers_helpful_next_step_over_pressure():
    prompt = _compact(PROMPTS.STAGE_FOLLOWUP_PROMPT)

    assert "каждый follow-up должен давать пользу" in prompt
    assert "мягко предложи разобрать расчет" in prompt
    assert "не дави" in prompt
    assert "не пиши в лоб" in prompt
    assert "ну что решили?" in prompt
    assert "актуально?" in prompt
    assert "когда подпишем?" in prompt


def test_measurement_slot_followup_starts_without_stretching_deal():
    first_followup_hours = STAGE_FOLLOWUP_THRESHOLDS["awaiting_measurement_slot"][0]

    assert 2 <= first_followup_hours <= 3


def test_followup_contract_stops_after_three_touches():
    assert MAX_FOLLOWUPS == 3


def test_followup_prompts_keep_gentle_but_guided_conversation_contract():
    prompt_bundle = _compact(
        "\n".join(
            [
                PROMPTS.FOLLOWUP_PROMPT,
                PROMPTS.STAGE_FOLLOWUP_PROMPT,
            ]
        )
    )

    assert "не дави" in prompt_bundle
    assert "веди" in prompt_bundle
    assert "не оставляй диалог в воздухе" in prompt_bundle
    assert "после 3 касаний" in prompt_bundle
    assert "останов" in prompt_bundle or "пауз" in prompt_bundle
