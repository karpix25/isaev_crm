import os
import sys
import types


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

langfuse_stub = types.ModuleType("langfuse")
langfuse_stub.Langfuse = object
sys.modules.setdefault("langfuse", langfuse_stub)

from src.services.analytics_service import messenger_click_event_names


def test_messenger_click_event_names_include_legacy_quiz_events():
    assert messenger_click_event_names("telegram") == (
        "telegram_clicked",
        "telegram_opened_after_submit",
        "telegram_clicked_from_result",
    )
    assert messenger_click_event_names("whatsapp") == (
        "whatsapp_clicked",
        "whatsapp_opened_after_submit",
        "whatsapp_clicked_from_result",
    )
