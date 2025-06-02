from abc import ABC, abstractmethod
import aiohttp
import base64

class TTSService(ABC):
    @abstractmethod
    async def synthesize(self, text: str) -> bytes:
        pass

class OpenAITTSService(TTSService):
    def __init__(self, api_key: str, voice: str = "alloy", model: str = "tts-1", speed: float = 1.0):
        self.api_key = api_key
        self.voice = voice
        self.model = model
        self.speed = speed
        self.api_url = "https://api.openai.com/v1/audio/speech"

    async def synthesize(self, text: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": self.model,
                "input": text,
                "voice": self.voice,
                "speed": self.speed,
                "response_format": "opus"
            }
            async with session.post(self.api_url, headers=headers, json=payload) as response:
                if response.status == 200:
                    return await response.read()
                else:
                    error = await response.text()
                    raise Exception(f"OpenAI TTS error: {error}")

class GoogleTTSService(TTSService):
    def __init__(self, api_key: str, voice: str = "en-US-Standard-A"):
        self.api_key = api_key
        self.voice = voice
        self.api_url = f"https://texttospeech.googleapis.com/v1/text:synthesize?key={api_key}"

    async def synthesize(self, text: str) -> bytes:
        async with aiohttp.ClientSession() as session:
            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": self.voice[:5],
                    "name": self.voice
                },
                "audioConfig": {"audioEncoding": "OGG_OPUS"}
            }
            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    audio_content = result.get("audioContent", "")
                    return base64.b64decode(audio_content)
                else:
                    error = await response.text()
                    raise Exception(f"Google TTS error: {error}")

def create_tts_service(config) -> TTSService:
    if config.provider == "openai":
        return OpenAITTSService(config.api_key, config.voice, config.model, config.speed)
    elif config.provider == "google":
        return GoogleTTSService(config.api_key, config.voice)
    else:
        raise ValueError(f"Unknown TTS provider: {config.provider}")
