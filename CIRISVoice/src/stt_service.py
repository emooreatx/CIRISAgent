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
        # api_key is actually the path to service account JSON
        self.credentials_path = api_key
        self.language = language
        # Import here to avoid dependency if not using Google
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        
        self.credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        self.api_url = "https://speech.googleapis.com/v1/speech:recognize"

    async def transcribe(self, audio_data: bytes, format: str = "wav") -> Optional[str]:
        # Refresh token if needed
        if self.credentials.expired:
            self.credentials.refresh(Request())
            
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.credentials.token}",
                "Content-Type": "application/json"
            }
            audio_content = base64.b64encode(audio_data).decode('utf-8')
            payload = {
                "config": {
                    "encoding": "WEBM_OPUS" if format == "webm" else "LINEAR16",
                    "sampleRateHertz": 16000,
                    "languageCode": self.language,
                },
                "audio": {"content": audio_content}
            }

            async with session.post(self.api_url, headers=headers, json=payload) as response:
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
        credentials_path = config.google_credentials_path or config.api_key
        return GoogleSTTService(credentials_path, config.google_language_code)
    else:
        raise ValueError(f"Unknown STT provider: {config.provider}")
