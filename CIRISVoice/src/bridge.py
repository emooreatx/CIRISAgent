import asyncio
import logging
import sys
from typing import Optional
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcript
from wyoming.tts import Synthesize
from wyoming.server import AsyncServer, AsyncEventHandler
from wyoming.info import Describe, Info, AsrModel, AsrProgram, TtsProgram, TtsVoice, Attribution
from wyoming.event import Event
from wyoming.ping import Ping, Pong
from wyoming.error import Error

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
        self._connection_info = writer.get_extra_info('peername')
        logger.info(f"Handler created for connection from {self._connection_info}")
    
    @property
    def closed(self):
        """Check if connection is closed."""
        return self.writer.is_closing() if hasattr(self.writer, 'is_closing') else False
    
    async def disconnect(self):
        """Handle disconnection cleanup."""
        logger.info(f"Connection closed from {self._connection_info}")
        if self._initialized and hasattr(self.ciris_client, 'voice_client'):
            try:
                await self.ciris_client.voice_client.close()
            except Exception as e:
                logger.error(f"Error closing CIRIS client: {e}")

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

    async def handle_event(self, event) -> bool:
        import time
        start_time = time.time()
        
        # Log event details
        logger.debug(f"Received event type: {type(event).__name__}")
        if hasattr(event, 'type'):
            logger.debug(f"Event.type: {event.type}")
        if hasattr(event, 'data'):
            logger.debug(f"Event.data: {event.data}")
        
        # For Describe events, return info immediately without initialization
        if isinstance(event, Describe) or (hasattr(event, 'type') and event.type == 'describe'):
            logger.info("Returning Wyoming info for discovery")
            info = self._get_info()
            logger.debug(f"Info response took {time.time() - start_time:.3f}s")
            logger.debug(f"Info content: {info}")
            # Write the info event and keep connection alive
            info_event = info.event()
            logger.debug(f"Sending info event: {info_event}")
            await self.write_event(info_event)
            logger.debug("Sent info event, keeping connection alive")
            return True  # Keep connection alive
        
        # Handle Ping events for health checks
        if isinstance(event, Ping):
            logger.debug("Received ping, sending pong")
            await self.write_event(Pong().event())
            return True
        
        # Initialize on first non-describe event if needed
        if not self._initialized:
            try:
                await self._ensure_initialized()
            except Exception as e:
                logger.error(f"Initialization failed: {e}", exc_info=True)
                # Continue anyway - Wyoming might just be probing
        
        if isinstance(event, AudioStart):
            logger.debug("Audio recording started")
            self.is_recording = True
            self.audio_buffer = bytearray()
            return True
        
        if isinstance(event, AudioChunk):
            if self.is_recording:
                self.audio_buffer.extend(event.audio)
            return True
        
        if isinstance(event, AudioStop):
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
                        
                        # Send transcript and synthesis events
                        await self.write_event(Transcript(text=text).event())
                        await self.write_event(Synthesize(text=response_text).event())
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    await self.write_event(Synthesize(text="I encountered an error processing your request.").event())
            self.audio_buffer = bytearray()
            return True
        
        if isinstance(event, Synthesize):
            try:
                audio_data = await self.tts_service.synthesize(event.text)
                # Send audio events for Wyoming
                await self.write_event(AudioStart(
                    rate=24000,
                    width=2,
                    channels=1
                ).event())
                await self.write_event(AudioChunk(audio=audio_data).event())
                await self.write_event(AudioStop().event())
            except Exception as e:
                logger.error(f"TTS error: {e}")
            return True
        
        if isinstance(event, Transcript):
            response = await self.ciris_client.send_message(event.text)
            await self.write_event(Synthesize(text=response.get("content", "Processing error")).event())
            return True
        
        # Log unknown event types
        logger.warning(f"Unhandled event type: {type(event).__name__}")
        return True  # Keep connection alive even for unknown events

    def _get_info(self):
        return Info(
            asr=[AsrProgram(
                name="ciris-stt",
                description=f"CIRIS STT using {self.config.stt.provider}",
                attribution=Attribution(
                    name="CIRIS AI",
                    url="https://ciris.ai"
                ),
                installed=True,
                models=[AsrModel(
                    name="ciris-stt-v1",  # Use simple model name
                    description=f"{self.config.stt.provider} speech recognition",
                    languages=["en_US", "en"],  # Include both language formats
                    attribution=Attribution(
                        name="CIRIS AI",
                        url="https://ciris.ai"
                    ),
                    installed=True
                )]
            )],
            tts=[TtsProgram(
                name="ciris-tts",
                description=f"CIRIS TTS using {self.config.tts.provider}",
                attribution=Attribution(
                    name="CIRIS AI",
                    url="https://ciris.ai"
                ),
                installed=True,
                voices=[TtsVoice(
                    name="en_US-ciris-medium",  # Use simpler voice name format
                    description=f"{self.config.tts.provider} voice",
                    languages=["en_US", "en"],  # Include both formats
                    attribution=Attribution(
                        name="CIRIS AI",
                        url="https://ciris.ai"
                    ),
                    installed=True
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
        logger.info(f"New connection from {writer.get_extra_info('peername')}")
        return CIRISWyomingHandler(reader, writer, config)
    
    # Create and run server
    server = AsyncServer.from_uri(f"tcp://{config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Starting CIRIS Wyoming bridge on {config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Using {config.ciris.timeout}s timeout for CIRIS interactions")
    logger.info(f"STT: {config.stt.provider}, TTS: {config.tts.provider}")
    
    try:
        await server.run(handler_factory)
    except KeyboardInterrupt:
        logger.info("Shutting down due to keyboard interrupt")
    except Exception as e:
        logger.error(f"Server error: {e}", exc_info=True)
    finally:
        logger.info("Server stopped")

if __name__ == "__main__":
    import signal
    
    # Handle SIGTERM gracefully
    def signal_handler(sig, frame):
        logger.info(f"Received signal {sig}, shutting down gracefully...")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    asyncio.run(main())
