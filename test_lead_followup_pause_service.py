from datetime import datetime, timezone
import os
import json


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

from src.models import Lead, LeadStatus
from src.services.lead_followup_pause_service import lead_followup_pause_service


def test_detects_keys_pending_delay_from_month_range():
    lead = Lead(status=LeadStatus.MEASUREMENT_PENDING.value)
    now = datetime(2026, 6, 9, 10, 0, tzinfo=timezone.utc)

    decision = lead_followup_pause_service.build_decision(
        lead,
        "Добрый день. У нас еще не сдана квартира, ждём в течение 1-2 мес",
        now=now,
    )

    assert decision.should_pause
    assert decision.status == LeadStatus.KEYS_PENDING.value
    assert decision.reason == "keys_or_handover_wait"
    pause = decision.extracted_patch["followup_pause"]
    assert pause["delay_days"] == 30
    assert "сдачу" in pause["client_context"]
    assert "ключей" in pause["followup_goal"]


def test_ignores_neutral_client_reply():
    lead = Lead(status=LeadStatus.MEASUREMENT_PENDING.value)

    decision = lead_followup_pause_service.build_decision(lead, "Хорошо, спасибо")

    assert not decision.should_pause
    assert decision.extracted_patch == {}


def test_keeps_existing_pause_on_short_acknowledgement():
    lead = Lead(status=LeadStatus.KEYS_PENDING.value)
    lead.next_followup_at = datetime(2026, 8, 8, 10, 0, tzinfo=timezone.utc)
    lead.extracted_data = json.dumps({"followup_pause": {"reason": "keys_or_handover_wait"}})

    assert lead_followup_pause_service.should_keep_existing_pause(lead, "Хорошо, спасибо")
