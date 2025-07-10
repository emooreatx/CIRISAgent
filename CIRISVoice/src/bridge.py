import asyncio
import logging
from typing import Optional
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcript
from wyoming.tts import Synthesize
from wyoming.server import AsyncServer, AsyncEventHandler
from wyoming.info import Describe, Info, AsrModel, AsrProgram, TtsProgram, TtsVoice
from wyoming.event import Event

from .config import Config
from .stt_service import create_stt_service
from .tts_service import create_tts_service
from .ciris_sdk_client import CIRISClient

logger = logging.getLogger(__name__)

class CIRISWyomingHandler(AsyncEventHandler):
    def __init__(self, reader, writer, config: Config = None):
        super().__init__(reader, writer)
        self.config = config or Config.from_yaml("config.yaml")
        self.stt_service = create_stt_service(self.config.stt)
        self.tts_service = create_tts_service(self.config.tts)
        self.ciris_client = CIRISClient(self.config.ciris)
        self.audio_buffer = bytearray()
        self.is_recording = False
        self._initialized = False

    async def _ensure_initialized(self):
        """Initialize CIRIS client on first use."""
        if not self._initialized:
            try:
                await self.ciris_client.voice_client.initialize()
                self._initialized = True
                logger.info("CIRIS client initialized successfully")
            except Exception as e:
                logger.error(f"Failed to initialize CIRIS client: {e}")
                raise

    async def handle_event(self, event):
        import time
        start_time = time.time()
        logger.debug(f"Received event: {type(event).__name__}, {event}")
        
        # For Describe events, return info immediately without initialization
        if isinstance(event, Describe) or (hasattr(event, 'type') and event.type == 'describe'):
            logger.info("Returning Wyoming info for discovery")
            info = self._get_info()
            logger.debug(f"Info response took {time.time() - start_time:.3f}s")
            return info
        
        # Initialize on first non-describe event if needed
        if not self._initialized:
            try:
                await self._ensure_initialized()
            except Exception as e:
                logger.error(f"Initialization failed: {e}")
                # Continue anyway - Wyoming might just be probing
        elif isinstance(event, AudioStart):
            logger.debug("Audio recording started")
            self.is_recording = True
            self.audio_buffer = bytearray()
        elif isinstance(event, AudioChunk):
            if self.is_recording:
                self.audio_buffer.extend(event.audio)
        elif isinstance(event, AudioStop):
            logger.debug("Audio recording stopped")
            self.is_recording = False
            if len(self.audio_buffer) > 0:
                try:
                    text = await self.stt_service.transcribe(bytes(self.audio_buffer))
                    if text:
                        logger.info(f"Transcribed: {text}")
                        
                        # Track timing
                        start_time = asyncio.get_event_loop().time()
                        
                        # Send to CIRIS with extended timeout
                        response = await self.ciris_client.send_message(text)
                        
                        # Log response time
                        elapsed = asyncio.get_event_loop().time() - start_time
                        response_text = response.get("content", "I didn't understand that.")
                        
                        logger.info(f"CIRIS responded in {elapsed:.1f}s: {response_text[:50]}...")
                        
                        return [
                            Transcript(text=text),
                            Synthesize(text=response_text)
                        ]
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    return Synthesize(text="I encountered an error processing your request.")
            self.audio_buffer = bytearray()
        elif isinstance(event, Synthesize):
            try:
                audio_data = await self.tts_service.synthesize(event.text)
                # Return audio chunks directly for Wyoming
                return [
                    AudioStart(
                        rate=24000,
                        width=2,
                        channels=1
                    ),
                    AudioChunk(audio=audio_data),
                    AudioStop()
                ]
            except Exception as e:
                logger.error(f"TTS error: {e}")
                return None
        elif isinstance(event, Transcript):
            response = await self.ciris_client.send_message(event.text)
            return Synthesize(text=response.get("content", "Processing error"))
        return None

    def _get_info(self):
        return Info(
            asr=[AsrProgram(
                name="ciris-stt",
                description=f"CIRIS STT using {self.config.stt.provider}",
                models=[AsrModel(
                    name=self.config.stt.model,
                    description=f"{self.config.stt.provider} speech recognition",
                    languages=[self.config.stt.language]
                )]
            )],
            tts=[TtsProgram(
                name="ciris-tts",
                description=f"CIRIS TTS using {self.config.tts.provider}",
                voices=[TtsVoice(
                    name=self.config.tts.voice,
                    description=f"{self.config.tts.provider} voice",
                    languages=["en-US"]
                )]
            )]
        )

async def main():
    logging.basicConfig(
        level=logging.DEBUG,  # Use DEBUG to see all events
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Load configuration
    config = Config.from_yaml("config.yaml")
    
    # Create handler factory
    def handler_factory(reader, writer):
        return CIRISWyomingHandler(reader, writer, config)
    
    # Create and run server
    server = AsyncServer.from_uri(f"tcp://{config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Starting CIRIS Wyoming bridge on {config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Using {config.ciris.timeout}s timeout for CIRIS interactions")
    logger.info(f"STT: {config.stt.provider}, TTS: {config.tts.provider}")
    
    try:
        await server.run(handler_factory)
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        logger.info("Server stopped")

if __name__ == "__main__":
    asyncio.run(main())
