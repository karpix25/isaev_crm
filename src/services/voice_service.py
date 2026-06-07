import os
import logging
import asyncio
import assemblyai as aai
from src.config import settings
from src.services.groq_audio_service import groq_audio_service

logger = logging.getLogger(__name__)

class VoiceService:
    def __init__(self):
        self.transcriber = aai.Transcriber()
    
    async def transcribe_audio(self, file_path: str) -> str | None:
        """
        Transcribe an audio file for inbound messenger messages.

        Groq is the primary low-cost provider. AssemblyAI remains as a fallback
        for production resilience and backward compatibility.
        """
        provider = str(settings.audio_transcription_provider or "auto").strip().lower()
        if provider in {"groq", "auto"}:
            transcript = await self._transcribe_groq(file_path)
            if transcript:
                return transcript
            if provider == "groq":
                return None

        if provider in {"assemblyai", "auto"}:
            return await self._transcribe_assemblyai(file_path)

        logger.warning("Unknown audio transcription provider: %s", provider)
        return None

    async def _transcribe_groq(self, file_path: str) -> str | None:
        try:
            return await groq_audio_service.transcribe_audio(file_path)
        except Exception:
            logger.warning("Groq transcription failed for %s", file_path, exc_info=True)
            return None

    async def _transcribe_assemblyai(self, file_path: str) -> str | None:
        api_key = settings.assemblyai_api_key or os.getenv("ASSEMBLYAI_API_KEY", "")
        if not api_key:
            logger.warning("No ASSEMBLYAI_API_KEY found. AssemblyAI transcription skipped.")
            return None

        aai.settings.api_key = api_key
        try:
            logger.info(f"Starting AssemblyAI transcription for {file_path}")
            
            # Using asyncio.to_thread to run synchronous external API call
            config = aai.TranscriptionConfig(
                language_code="ru", 
                speech_models=[aai.SpeechModel.universal]
            )
            
            def do_transcribe():
                transcript = self.transcriber.transcribe(file_path, config=config)
                if transcript.error:
                    logger.error(f"AssemblyAI transcription error: {transcript.error}")
                    return None
                return transcript.text
                
            text = await asyncio.to_thread(do_transcribe)
            
            if text:
                logger.info(f"Transcription successful: {text[:50]}...")
            return text
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio file {file_path}: {e}", exc_info=True)
            return None


voice_service = VoiceService()
