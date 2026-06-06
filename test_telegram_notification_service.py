import os

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:password@localhost:5432/crm")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "1234567890:test-token")

from src.config import settings
from src.services.telegram_notification_service import telegram_notification_service


def test_parse_topic_link_recipient(monkeypatch):
    monkeypatch.setattr(settings, "manager_telegram_ids", "")
    monkeypatch.setattr(settings, "hot_lead_telegram_ids", "https://t.me/c/3734786933/12")

    resolution = telegram_notification_service.resolve_recipients("hot_lead")

    assert resolution.source == "topic"
    assert len(resolution.recipients) == 1
    recipient = resolution.recipients[0]
    assert recipient.chat_id == -1003734786933
    assert recipient.message_thread_id == 12


def test_topic_resolution_reports_manager_fallback(monkeypatch):
    monkeypatch.setattr(settings, "manager_telegram_ids", "-1003734786933:1")
    monkeypatch.setattr(settings, "measurement_telegram_ids", "")

    resolution = telegram_notification_service.resolve_recipients("measurement")

    assert resolution.source == "fallback"
    assert len(resolution.recipients) == 1
    assert resolution.recipients[0].message_thread_id == 1
