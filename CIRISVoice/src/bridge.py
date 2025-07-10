import asyncio
import logging
import sys
import os
import json
from typing import Optional
from wyoming.audio import AudioChunk, AudioStart, AudioStop
from wyoming.asr import Transcript, Transcribe
from wyoming.tts import Synthesize
from wyoming.server import AsyncServer, AsyncEventHandler
from wyoming.info import Describe, Info, AsrModel, AsrProgram, TtsProgram, TtsVoice, TtsVoiceSpeaker, Attribution
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
        
        # Pre-create wyoming info event like faster-whisper does
        self.wyoming_info_event = self._get_info().event()
    
    @property
    def closed(self):
        """Check if connection is closed."""
        return self.writer.is_closing() if hasattr(self.writer, 'is_closing') else False
    
    async def disconnect(self):
        """Handle disconnection cleanup."""
        logger.info(f"=== DISCONNECT ===")
        logger.info(f"Connection closed from {self._connection_info}")
        logger.info(f"Total events received: {getattr(self, '_event_count', 0)}")
        logger.info(f"Handler initialized: {self._initialized}")
        
        # Log if connection was closed by remote
        if hasattr(self.writer, 'is_closing'):
            logger.info(f"Writer is_closing: {self.writer.is_closing()}")
        
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
        
        # Comprehensive event logging
        logger.info(f"=== EVENT #{getattr(self, '_event_count', 0) + 1} ===")
        self._event_count = getattr(self, '_event_count', 0) + 1
        
        # Log all event attributes
        event_attrs = {}
        for attr in dir(event):
            if not attr.startswith('_'):
                try:
                    value = getattr(event, attr)
                    if not callable(value):
                        event_attrs[attr] = str(value)
                except:
                    pass
        
        logger.info(f"Event type: {type(event).__name__}")
        logger.info(f"Event attributes: {event_attrs}")
        
        # Check if we have raw event data
        if hasattr(event, '__dict__'):
            logger.info(f"Event dict: {event.__dict__}")
        
        # Log event type in detail
        if hasattr(event, 'type'):
            logger.info(f"Event.type field: {event.type}")
        if hasattr(event, 'data'):
            logger.info(f"Event.data field: {event.data}")
        
        # For Describe events, return info immediately without initialization
        if Describe.is_type(event.type):
            logger.info("Describe event detected, sending info response")
            logger.info(f"Info event being sent: {self.wyoming_info_event}")
            
            # Log the actual JSON that will be sent
            import json
            if hasattr(self.wyoming_info_event, 'data'):
                logger.info(f"Info JSON: {json.dumps(self.wyoming_info_event.data, indent=2)}")
            
            try:
                await self.write_event(self.wyoming_info_event)
                logger.info("Info sent successfully, waiting for next event...")
            except ConnectionResetError:
                logger.warning("Connection reset by Home Assistant during info send")
                return False
            except Exception as e:
                logger.error(f"Error sending info: {e}")
                return False
            # CRITICAL: Must return True to keep connection open!
            return True
        
        # Handle Ping events for health checks
        if Ping.is_type(event.type):
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
        
        if Transcribe.is_type(event.type):
            # Wyoming might send language preference
            transcribe = Transcribe.from_event(event)
            if transcribe.language:
                logger.debug(f"Language set to {transcribe.language}")
            return True
        
        if AudioStart.is_type(event.type):
            logger.debug("Audio recording started")
            self.is_recording = True
            self.audio_buffer = bytearray()
            return True
        
        if AudioChunk.is_type(event.type):
            chunk = AudioChunk.from_event(event)
            if self.is_recording:
                self.audio_buffer.extend(chunk.audio)
            return True
        
        if AudioStop.is_type(event.type):
            logger.debug("Audio recording stopped")
            self.is_recording = False
            if len(self.audio_buffer) > 0:
                try:
                    # Don't send any events until we have actual content
                    # Home Assistant might close connection on early Transcript
                    
                    # Track total processing time
                    total_start = asyncio.get_event_loop().time()
                    
                    # Transcribe audio
                    stt_start = asyncio.get_event_loop().time()
                    text = await self.stt_service.transcribe(bytes(self.audio_buffer))
                    stt_time = asyncio.get_event_loop().time() - stt_start
                    
                    if text:
                        logger.info(f"Transcribed in {stt_time:.1f}s: {text}")
                        
                        # Send transcript event
                        await self.write_event(Transcript(text=text).event())
                        
                        # Immediately start audio stream to signal we're generating TTS
                        await self.write_event(AudioStart(
                            rate=24000,
                            width=2,
                            channels=1
                        ).event())
                        
                        # Start streaming silence while we process
                        silence_chunk = bytes(4800)  # 100ms of silence at 24kHz, 16-bit mono
                        silence_task = None
                        stop_silence = asyncio.Event()
                        
                        async def stream_silence():
                            """Stream silence to keep connection alive"""
                            while not stop_silence.is_set():
                                if self.closed:
                                    break
                                try:
                                    await self.write_event(AudioChunk(
                                        audio=silence_chunk,
                                        rate=24000,
                                        width=2,
                                        channels=1
                                    ).event())
                                    await asyncio.sleep(0.05)  # Send silence every 50ms
                                except (ConnectionResetError, BrokenPipeError):
                                    break
                        
                        # Start streaming silence
                        silence_task = asyncio.create_task(stream_silence())
                        
                        try:
                            # Add context for CIRIS to understand this is a voice command from HA
                            enhanced_message = f"{text}\n\n[This was received via API from Home Assistant, please SPEAK to service this authorized request, thank you!]"
                            
                            # Send to CIRIS
                            ciris_start = asyncio.get_event_loop().time()
                            response = await self.ciris_client.send_message(enhanced_message)
                            ciris_time = asyncio.get_event_loop().time() - ciris_start
                            
                            response_text = response.get("content", "I didn't understand that.")
                            logger.info(f"CIRIS responded in {ciris_time:.1f}s: {response_text[:50]}...")
                            
                            # Check total elapsed time
                            total_elapsed = asyncio.get_event_loop().time() - total_start
                            logger.info(f"Total elapsed before TTS: {total_elapsed:.1f}s (STT: {stt_time:.1f}s, CIRIS: {ciris_time:.1f}s)")
                            
                            # Only synthesize if we have a real response (not timeout message)
                            if "Still processing" not in response_text:
                                # Synthesize the response audio
                                if self.closed:
                                    logger.warning("Connection already closed, skipping TTS")
                                    return True
                                
                                logger.info(f"Synthesizing TTS response: {response_text[:50]}...")
                                
                                # Synthesize audio while silence is still streaming
                                tts_start = asyncio.get_event_loop().time()
                                audio_data = await self.tts_service.synthesize(response_text)
                                tts_time = asyncio.get_event_loop().time() - tts_start
                                logger.info(f"TTS synthesis completed in {tts_time:.1f}s")
                                
                                # Stop silence streaming
                                stop_silence.set()
                                if silence_task:
                                    await silence_task
                                
                                # Send the real audio data if connection still alive
                                if not self.closed:
                                    # Send audio in chunks
                                    chunk_size = 4800  # 100ms chunks at 24kHz
                                    for i in range(0, len(audio_data), chunk_size):
                                        if self.closed:
                                            logger.warning("Connection closed during audio streaming")
                                            break
                                        chunk = audio_data[i:i+chunk_size]
                                        await self.write_event(AudioChunk(
                                            audio=chunk,
                                            rate=24000,
                                            width=2,
                                            channels=1
                                        ).event())
                                    
                                    if not self.closed:
                                        await self.write_event(AudioStop().event())
                                        total_time = asyncio.get_event_loop().time() - total_start
                                        logger.info(f"TTS audio sent successfully. Total time: {total_time:.1f}s")
                                else:
                                    logger.warning("Connection closed before audio data could be sent")
                            else:
                                # For timeout messages, send a brief response
                                logger.info("CIRIS timed out, sending brief error response")
                                brief_response = "I need more time to process that request."
                                audio_data = await self.tts_service.synthesize(brief_response)
                                
                                # Stop silence streaming
                                stop_silence.set()
                                if silence_task:
                                    await silence_task
                                
                                if not self.closed:
                                    # Send audio in chunks
                                    chunk_size = 4800
                                    for i in range(0, len(audio_data), chunk_size):
                                        if self.closed:
                                            break
                                        chunk = audio_data[i:i+chunk_size]
                                        await self.write_event(AudioChunk(
                                            audio=chunk,
                                            rate=24000,
                                            width=2,
                                            channels=1
                                        ).event())
                                    await self.write_event(AudioStop().event())
                                    
                        finally:
                            # Ensure silence task is cleaned up
                            stop_silence.set()
                            if silence_task and not silence_task.done():
                                silence_task.cancel()
                                try:
                                    await silence_task
                                except asyncio.CancelledError:
                                    pass
                except Exception as e:
                    logger.error(f"Processing error: {e}")
                    # Don't try to send error messages if connection is broken
                    if not isinstance(e, (ConnectionResetError, BrokenPipeError)):
                        try:
                            await self.write_event(Synthesize(text="I encountered an error processing your request.").event())
                        except (ConnectionResetError, BrokenPipeError):
                            logger.warning("Connection lost while sending error message")
            self.audio_buffer = bytearray()
            return True
        
        if Synthesize.is_type(event.type):
            synthesize = Synthesize.from_event(event)
            try:
                audio_data = await self.tts_service.synthesize(synthesize.text)
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
        
        if Transcript.is_type(event.type):
            transcript = Transcript.from_event(event)
            response = await self.ciris_client.send_message(transcript.text)
            await self.write_event(Synthesize(text=response.get("content", "Processing error")).event())
            return True
        
        # Log unknown event types
        logger.warning(f"Unhandled event type: {type(event).__name__}")
        return True  # Keep connection alive even for unknown events

    def _get_info(self):
        # Advertise both STT and TTS capabilities
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
                    name="ciris-stt-v1",
                    description=f"{self.config.stt.provider} speech recognition",
                    languages=["en_US", "en"],
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
                    name=self.config.tts.voice if hasattr(self.config.tts, 'voice') else "default",
                    description=f"{self.config.tts.provider} voice synthesis",
                    languages=["en_US", "en"],
                    attribution=Attribution(
                        name="CIRIS AI",
                        url="https://ciris.ai"
                    ),
                    installed=True,
                    speakers=[TtsVoiceSpeaker(
                        name="default"
                    )]
                )]
            )]
        )

async def main():
    logging.basicConfig(
        level=logging.INFO,  # Changed to INFO for clearer output
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    logger.info("=== CIRIS WYOMING BRIDGE STARTING ===")
    
    # Pre-flight checks
    logger.info("Running pre-flight diagnostics...")
    
    # Check if we're in Home Assistant addon environment
    import os
    is_addon = os.path.exists('/data/options.json')
    logger.info(f"Running as Home Assistant addon: {is_addon}")
    
    if is_addon:
        try:
            import json
            with open('/data/options.json', 'r') as f:
                options = json.load(f)
                logger.info(f"Addon options: {json.dumps(options, indent=2)}")
        except Exception as e:
            logger.warning(f"Could not read addon options: {e}")
    
    # Check environment
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Working directory: {os.getcwd()}")
    logger.info(f"Process ID: {os.getpid()}")
    
    # Load configuration
    config = Config.from_yaml("config.yaml")
    logger.info(f"Configuration loaded successfully")
    
    # Test Wyoming info generation
    try:
        # Create a minimal test to verify info generation
        test_info = Info(
            asr=[AsrProgram(
                name="ciris-stt",
                description=f"CIRIS STT using {config.stt.provider}",
                attribution=Attribution(
                    name="CIRIS AI",
                    url="https://ciris.ai"
                ),
                installed=True,
                models=[AsrModel(
                    name="ciris-stt-v1",
                    description=f"{config.stt.provider} speech recognition",
                    languages=["en_US", "en"],
                    attribution=Attribution(
                        name="CIRIS AI",
                        url="https://ciris.ai"
                    ),
                    installed=True
                )]
            )]
        )
        logger.info(f"Wyoming info test successful")
        logger.info(f"Info event type: {test_info.event().type}")
        logger.info(f"Info event data keys: {list(test_info.event().data.keys())}")
    except Exception as e:
        logger.error(f"Failed to generate Wyoming info: {e}")
    
    # Create handler factory with debugging
    def handler_factory(reader, writer):
        peer = writer.get_extra_info('peername')
        logger.info(f"=== NEW CONNECTION ===")
        logger.info(f"Connection from: {peer}")
        logger.info(f"Socket info: {writer.get_extra_info('socket')}")
        return CIRISWyomingHandler(reader, writer, config)
    
    # Create and run server
    server = AsyncServer.from_uri(f"tcp://{config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Starting CIRIS Wyoming bridge on {config.wyoming.host}:{config.wyoming.port}")
    logger.info(f"Using {config.ciris.timeout}s timeout for CIRIS interactions")
    logger.info(f"STT: {config.stt.provider}, TTS: {config.tts.provider}")
    logger.info("=== READY FOR CONNECTIONS ===")
    
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
