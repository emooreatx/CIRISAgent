#!/usr/bin/env python3
"""Test Wyoming compatibility with Home Assistant by mimicking known working services."""
import asyncio
import logging
from wyoming.info import AsrModel, AsrProgram, Attribution, Info, TtsProgram, TtsVoice
from wyoming.server import AsyncServer, AsyncEventHandler
from wyoming.event import Event

_LOGGER = logging.getLogger(__name__)

class TestHandler(AsyncEventHandler):
    """Test different Info configurations."""
    
    def __init__(self, *args, test_case="whisper", **kwargs):
        super().__init__(*args, **kwargs)
        self.test_case = test_case
        
        if test_case == "whisper":
            # Mimic wyoming-faster-whisper
            self.wyoming_info = Info(
                asr=[
                    AsrProgram(
                        name="faster-whisper",
                        description="Faster Whisper transcription",
                        attribution=Attribution(
                            name="Guillaume Klein",
                            url="https://github.com/guillaumekln/faster-whisper",
                        ),
                        installed=True,
                        models=[
                            AsrModel(
                                name="tiny-int8",
                                description="Tiny model (39M parameters)",
                                attribution=Attribution(
                                    name="Guillaume Klein",
                                    url="https://github.com/guillaumekln/faster-whisper",
                                ),
                                installed=True,
                                languages=[
                                    "af", "am", "ar", "as", "az", "ba", "be", "bg", "bn", "bo",
                                    "br", "bs", "ca", "cs", "cy", "da", "de", "el", "en", "es",
                                    "et", "eu", "fa", "fi", "fo", "fr", "gl", "gu", "ha", "haw",
                                    "he", "hi", "hr", "ht", "hu", "hy", "id", "is", "it", "ja",
                                    "jw", "ka", "kk", "km", "kn", "ko", "la", "lb", "ln", "lo",
                                    "lt", "lv", "mg", "mi", "mk", "ml", "mn", "mr", "ms", "mt",
                                    "my", "ne", "nl", "nn", "no", "oc", "pa", "pl", "ps", "pt",
                                    "ro", "ru", "sa", "sd", "si", "sk", "sl", "sn", "so", "sq",
                                    "sr", "su", "sv", "sw", "ta", "te", "tg", "th", "tk", "tl",
                                    "tr", "tt", "uk", "ur", "uz", "vi", "yi", "yo", "zh",
                                ],
                            )
                        ],
                    )
                ],
            )
        elif test_case == "piper":
            # Mimic wyoming-piper
            self.wyoming_info = Info(
                tts=[
                    TtsProgram(
                        name="piper",
                        description="A fast, local neural text to speech engine",
                        attribution=Attribution(
                            name="Michael Hansen",
                            url="https://github.com/rhasspy/piper",
                        ),
                        installed=True,
                        voices=[
                            TtsVoice(
                                name="en_US-ryan-high",
                                description="English (US) - Ryan (high quality)",
                                attribution=Attribution(
                                    name="Michael Hansen",
                                    url="https://github.com/rhasspy/piper",
                                ),
                                installed=True,
                                languages=["en_US", "en"],
                            )
                        ],
                    )
                ],
            )
        else:  # minimal
            # Minimal valid info
            self.wyoming_info = Info(
                asr=[
                    AsrProgram(
                        name="test",
                        description="Test ASR",
                        installed=True,
                        models=[
                            AsrModel(
                                name="test",
                                description="Test model",
                                installed=True,
                                languages=["en"],
                            )
                        ],
                    )
                ],
            )

    async def handle_event(self, event: Event) -> bool:
        """Handle events."""
        if event.type == "describe":
            _LOGGER.info(f"Sending {self.test_case} info response")
            await self.write_event(self.wyoming_info.event())
            return True
        
        _LOGGER.warning(f"Unexpected event: {event}")
        return True


async def main():
    """Run test cases."""
    logging.basicConfig(level=logging.INFO)
    
    import sys
    test_case = sys.argv[1] if len(sys.argv) > 1 else "whisper"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 10301
    
    _LOGGER.info(f"Starting {test_case} test on port {port}")
    
    server = AsyncServer.from_uri(f"tcp://0.0.0.0:{port}")
    await server.run(lambda r, w: TestHandler(r, w, test_case=test_case))


if __name__ == "__main__":
    asyncio.run(main())