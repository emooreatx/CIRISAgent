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
        # api_key is actually the path to service account JSON
        self.credentials_path = api_key
        self.voice = voice
        # Import here to avoid dependency if not using Google
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        
        self.credentials = service_account.Credentials.from_service_account_file(
            self.credentials_path,
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        self.api_url = "https://texttospeech.googleapis.com/v1/text:synthesize"

    async def synthesize(self, text: str) -> bytes:
        # Refresh token if needed
        if self.credentials.expired:
            self.credentials.refresh(Request())
            
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.credentials.token}",
                "Content-Type": "application/json"
            }
            payload = {
                "input": {"text": text},
                "voice": {
                    "languageCode": self.voice[:5] if len(self.voice) >= 5 else "en-US",
                    "name": self.voice
                },
                "audioConfig": {"audioEncoding": "OGG_OPUS"}
            }
            async with session.post(self.api_url, headers=headers, json=payload) as response:
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
        credentials_path = config.google_credentials_path or config.api_key
        voice_name = config.google_voice_name or config.voice
        return GoogleTTSService(credentials_path, voice_name)
    else:
        raise ValueError(f"Unknown TTS provider: {config.provider}")
