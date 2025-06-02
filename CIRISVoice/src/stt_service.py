import asyncio
from abc import ABC, abstractmethod
from typing import Optional
import aiohttp
import base64

class STTService(ABC):
    @abstractmethod
    async def transcribe(self, audio_data: bytes, format: str = "wav") -> Optional[str]:
        pass

class OpenAISTTService(STTService):
    def __init__(self, api_key: str, model: str = "whisper-1"):
        self.api_key = api_key
        self.model = model
        self.api_url = "https://api.openai.com/v1/audio/transcriptions"

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            headers = {"Authorization": f"Bearer {self.api_key}"}
            form = aiohttp.FormData()
            form.add_field('file', audio_data, filename=f'audio.{format}', content_type=f'audio/{format}')
            form.add_field('model', self.model)

            async with session.post(self.api_url, headers=headers, data=form) as response:
                if response.status == 200:
                    result = await response.json()
                    return result.get("text")
                else:
                    error = await response.text()
                    raise Exception(f"OpenAI STT error: {error}")

class GoogleSTTService(STTService):
    def __init__(self, api_key: str, language: str = "en-US"):
        self.api_key = api_key
        self.language = language
        self.api_url = f"https://speech.googleapis.com/v1/speech:recognize?key={api_key}"

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> Optional[str]:
        async with aiohttp.ClientSession() as session:
            audio_content = base64.b64encode(audio_data).decode('utf-8')
            payload = {
                "config": {
                    "encoding": "WEBM_OPUS" if format == "webm" else "LINEAR16",
                    "sampleRateHertz": 16000,
                    "languageCode": self.language,
                },
                "audio": {"content": audio_content}
            }

            async with session.post(self.api_url, json=payload) as response:
                if response.status == 200:
                    result = await response.json()
                    if result.get("results"):
                        return result["results"][0]["alternatives"][0]["transcript"]
                else:
                    error = await response.text()
                    raise Exception(f"Google STT error: {error}")

def create_stt_service(config) -> STTService:
    if config.provider == "openai":
        return OpenAISTTService(config.api_key, config.model)
    elif config.provider == "google":
        return GoogleSTTService(config.api_key, config.language)
    else:
        raise ValueError(f"Unknown STT provider: {config.provider}")
