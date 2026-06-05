import os


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

from src.services.whatsapp.evolution_client import EvolutionClient


def test_whatsapp_number_result_handles_official_numbers_wrapper():
    client = EvolutionClient()

    result = client._whatsapp_number_result(
        {"numbers": [{"number": "79991234567", "exists": True}]},
        requested_number="79991234567",
    )

    assert result["active"] is True
    assert result["wa_id"] == "79991234567"


def test_whatsapp_number_result_handles_jid_response():
    client = EvolutionClient()

    result = client._whatsapp_number_result(
        [{"exists": True, "jid": "79991234567@s.whatsapp.net", "number": "79991234567"}],
        requested_number="+7 999 123-45-67",
    )

    assert result["active"] is True
    assert result["wa_id"] == "79991234567@s.whatsapp.net"
