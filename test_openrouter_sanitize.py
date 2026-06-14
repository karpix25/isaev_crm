import importlib.util
import os
import sys
import types
from pathlib import Path

import httpx
import pytest


os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test.db")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379")
os.environ.setdefault("S3_ENDPOINT", "http://localhost")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "12345678901:abcdefghijklmnopqrstuvwxyz")

langfuse_stub = types.ModuleType("langfuse")
langfuse_stub.Langfuse = object
sys.modules.setdefault("langfuse", langfuse_stub)

module_path = Path(__file__).parent / "src" / "services" / "openrouter_service.py"
spec = importlib.util.spec_from_file_location("openrouter_service_for_test", module_path)
openrouter_module = importlib.util.module_from_spec(spec)
assert spec and spec.loader
spec.loader.exec_module(openrouter_module)
OpenRouterService = openrouter_module.OpenRouterService
should_retry_api_error = openrouter_module.should_retry_api_error


def test_sanitize_lead_message_unescapes_newlines():
    service = OpenRouterService()

    text = service._sanitize_lead_message("Цена 4,0 – 4,9 млн рублей.\\n\\nЧтобы составить точную смету, нужен замер.")

    assert "\\n" not in text
    assert "\n\n" in text


def test_extract_user_facing_text_blocks_markdown_json_artifacts():
    service = OpenRouterService()

    text = service._extract_user_facing_text(
        "Let's format this as JSON.\\n\\n4. **Refining the JSON:**\\n```json\\n{\\n\"message\": \"Отлично! Завтра",
        None,
    )

    assert text == "Здравствуйте. Чем могу помочь по ремонту?"


def test_extract_user_facing_text_uses_message_without_tool_action_leak():
    service = OpenRouterService()

    text = service._extract_user_facing_text(
        '{"message": "Подберу удобное время.", "tool_action": "show_measurement_slots"}',
        {"message": "Подберу удобное время.", "tool_action": "show_measurement_slots"},
    )

    assert text == "Подберу удобное время."
    assert "tool_action" not in text
    assert "show_measurement_slots" not in text


def test_extract_user_facing_text_blocks_tool_action_only_payload():
    service = OpenRouterService()

    text = service._extract_user_facing_text(
        '{"tool_action": "handoff_to_manager", "status": "CONSULTING"}',
        {"tool_action": "handoff_to_manager", "status": "CONSULTING"},
    )

    assert text == "Здравствуйте. Чем могу помочь по ремонту?"
    assert "tool_action" not in text
    assert "handoff_to_manager" not in text


def test_extract_user_facing_text_blocks_tool_action_artifact_in_message_value():
    service = OpenRouterService()

    text = service._extract_user_facing_text(
        "",
        {
            "message": 'Подберу время. {"tool_action": "show_measurement_slots"}',
            "tool_action": "show_measurement_slots",
        },
    )

    assert text == "Здравствуйте. Чем могу помочь по ремонту?"
    assert "tool_action" not in text
    assert "show_measurement_slots" not in text


def test_extract_user_facing_text_blocks_raw_tool_action_artifact():
    service = OpenRouterService()

    text = service._extract_user_facing_text(
        'message: Подберу время\n"tool_action": "show_measurement_slots"',
        None,
    )

    assert text == "Здравствуйте. Чем могу помочь по ремонту?"
    assert "tool_action" not in text
    assert "show_measurement_slots" not in text


def test_should_retry_api_error_handles_httpx_exceptions_directly():
    request = httpx.Request("POST", "https://openrouter.ai/api/v1/chat/completions")
    response_402 = httpx.Response(402, request=request)
    response_429 = httpx.Response(429, request=request)

    assert should_retry_api_error(httpx.HTTPStatusError("credits", request=request, response=response_402)) is False
    assert should_retry_api_error(httpx.HTTPStatusError("rate limit", request=request, response=response_429)) is True
    assert should_retry_api_error(httpx.ConnectTimeout("timeout", request=request)) is True


def test_resolve_chat_model_maps_expensive_gemini_flash_to_lite_default():
    service = OpenRouterService()

    assert service.resolve_chat_model("") == "google/gemini-3.1-flash-lite"
    assert service.resolve_chat_model("google/gemini-3.5-flash") == "google/gemini-3.1-flash-lite"
    assert service.resolve_chat_model("deepseek/deepseek-v4-flash") == "deepseek/deepseek-v4-flash"


@pytest.mark.asyncio
async def test_generate_vision_response_sends_multiple_images_in_one_turn():
    service = OpenRouterService()
    captured = {}

    class FakeResponse:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                "choices": [{"message": {"content": '{"message": "Ок"}'}}],
                "usage": {},
            }

    class FakeClient:
        async def post(self, *args, **kwargs):
            captured["json"] = kwargs["json"]
            return FakeResponse()

    service.client = FakeClient()

    await service.generate_vision_response(
        conversation_history=[],
        system_prompt="system",
        image_base64=["image-1", "image-2", "image-3"],
        image_caption="[Фото] [Фото] в таком стиле",
        model="deepseek/deepseek-v4-flash",
    )

    content = captured["json"]["messages"][-1]["content"]
    image_items = [item for item in content if item["type"] == "image_url"]

    assert len(image_items) == 3
    assert content[-1]["type"] == "text"
    assert "в таком стиле" in content[-1]["text"]
