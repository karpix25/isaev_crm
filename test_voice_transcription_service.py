import os
import sys
import types
import asyncio


os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://user:pass@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("S3_ENDPOINT", "http://localhost:9000")
os.environ.setdefault("S3_ACCESS_KEY", "test")
os.environ.setdefault("S3_SECRET_KEY", "test")
os.environ.setdefault("JWT_SECRET_KEY", "test")
os.environ.setdefault("TELEGRAM_BOT_TOKEN", "test")

assemblyai_stub = types.ModuleType("assemblyai")


class _Transcriber:
    pass


class _Settings:
    api_key = ""


class _TranscriptionConfig:
    def __init__(self, **kwargs):
        self.kwargs = kwargs


class _SpeechModel:
    universal = "universal"


assemblyai_stub.Transcriber = _Transcriber
assemblyai_stub.settings = _Settings()
assemblyai_stub.TranscriptionConfig = _TranscriptionConfig
assemblyai_stub.SpeechModel = _SpeechModel
sys.modules.setdefault("assemblyai", assemblyai_stub)

import src.services.voice_service as voice_module
import src.services.whatsapp.audio_transcription_service as whatsapp_audio_module
from src.services.whatsapp.types import WhatsAppAttachment, WhatsAppIncomingMessage


def test_voice_service_uses_groq_provider(monkeypatch):
    async def fake_groq(file_path: str):
        assert file_path == "/tmp/audio.ogg"
        return "нужно перенести замер"

    monkeypatch.setattr(voice_module.settings, "audio_transcription_provider", "groq")
    monkeypatch.setattr(voice_module.groq_audio_service, "transcribe_audio", fake_groq)

    result = asyncio.run(voice_module.voice_service.transcribe_audio("/tmp/audio.ogg"))

    assert result == "нужно перенести замер"


def test_voice_service_auto_falls_back_to_assemblyai(monkeypatch):
    async def fake_groq(_file_path: str):
        return None

    async def fake_assembly(_file_path: str):
        return "хочу узнать цену ремонта"

    monkeypatch.setattr(voice_module.settings, "audio_transcription_provider", "auto")
    monkeypatch.setattr(voice_module.groq_audio_service, "transcribe_audio", fake_groq)
    monkeypatch.setattr(voice_module.voice_service, "_transcribe_assemblyai", fake_assembly)

    result = asyncio.run(voice_module.voice_service.transcribe_audio("/tmp/audio.ogg"))

    assert result == "хочу узнать цену ремонта"


def test_whatsapp_audio_service_transcribes_local_media(monkeypatch, tmp_path):
    audio_file = tmp_path / "voice.ogg"
    audio_file.write_bytes(b"fake audio")

    async def fake_transcribe(file_path: str):
        assert file_path == str(audio_file)
        return "адрес объекта химки 24"

    item = WhatsAppIncomingMessage(
        provider="evolution",
        chat_id="79991234567",
        message_id="m1",
        text="",
        attachment=WhatsAppAttachment(mimetype="audio/ogg"),
    )
    service = whatsapp_audio_module.WhatsAppAudioTranscriptionService()
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(whatsapp_audio_module.voice_service, "transcribe_audio", fake_transcribe)

    result = asyncio.run(service.transcribe(item=item, media_url="/voice.ogg"))

    assert result == "адрес объекта химки 24"
