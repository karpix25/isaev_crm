from types import SimpleNamespace
import os


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

from src.models.lead import LeadStatus
from src.services.lead_stage_engine_service import LeadStageEngineService


def test_post_contract_events_follow_payment_and_keys_flow():
    service = LeadStageEngineService()
    lead = SimpleNamespace(extracted_data=None)

    assert service.decide(lead, None, {"contract_signed"}).status == LeadStatus.PAYMENT_PENDING
    assert service.decide(lead, None, {"payment_received"}).status == LeadStatus.KEYS_PENDING
    assert service.decide(lead, None, {"keys_received"}).status == LeadStatus.READY_TO_START
    assert service.decide(lead, None, {"work_started"}).status == LeadStatus.WON
