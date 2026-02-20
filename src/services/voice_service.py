import os
import logging
import aiohttp
import asyncio
import assemblyai as aai
from src.config import settings

logger = logging.getLogger(__name__)

# Configure AssemblyAI key if available in env
aai.settings.api_key = os.getenv("ASSEMBLYAI_API_KEY", "")

class VoiceService:
    def __init__(self):
        self.transcriber = aai.Transcriber()
    
    async def transcribe_audio(self, file_path: str) -> str | None:
        """
        Transcribe an audio file using AssemblyAI.
        Runs the synchronous SDK in a thread to avoid blocking the event loop.
        """
        if not aai.settings.api_key:
            logger.warning("No ASSEMBLYAI_API_KEY found in environment variables. Transcription skipped.")
            return None
            
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
