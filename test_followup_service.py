import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

sys.modules.setdefault(
    "src.services.openrouter_service",
    SimpleNamespace(openrouter_service=SimpleNamespace()),
)

from src.services import followup_service


class FakeScalars:
    def __init__(self, leads):
        self._leads = leads

    def unique(self):
        return self

    def all(self):
        return self._leads


class FakeExecuteResult:
    def __init__(self, leads):
        self._leads = leads

    def scalars(self):
        return FakeScalars(self._leads)


class FakeDb:
    def __init__(self, leads):
        self.leads = leads
        self.statement = None

    async def execute(self, statement):
        self.statement = statement
        return FakeExecuteResult(self.leads)


def test_followup_eligibility_query_requires_automated_last_outbound(monkeypatch):
    lead = SimpleNamespace(
        id="lead-1",
        telegram_id=100500,
        last_message_at=datetime.now(timezone.utc) - timedelta(hours=30),
        followup_count=0,
        last_followup_at=None,
        next_followup_at=None,
        extracted_data=None,
    )
    db = FakeDb([lead])

    async def fake_build_stage_context(_db, _lead):
        return "general_consultation", {}, ""

    monkeypatch.setattr(followup_service, "_build_stage_context", fake_build_stage_context)

    eligible = asyncio.run(followup_service.get_leads_needing_followup(db))

    assert eligible == [lead]
    assert db.statement is not None
    sender_params = [
        value
        for key, value in db.statement.compile().params.items()
        if "sender_name" in key
    ]
    assert sender_params
    allowed_senders = set(sender_params[0])
    assert allowed_senders == followup_service.AUTOMATED_OUTBOUND_SENDERS
    assert "Admin" not in allowed_senders
    assert "Оператор" not in allowed_senders
