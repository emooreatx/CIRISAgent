import os
import json
import re
import logging
from typing import Dict, Any, Optional, Type, List

from pydantic import BaseModel
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
import instructor

from ciris_engine.adapters.base import Service
from ciris_engine.config.config_manager import get_config
from ciris_engine.schemas.config_schemas_v1 import OpenAIConfig, LLMServicesConfig

logger = logging.getLogger(__name__)


class OpenAICompatibleClient:
    """Client for interacting with OpenAI-compatible APIs."""

    def __init__(self, config: Optional[OpenAIConfig] = None) -> None:
        if config is None:
            app_cfg = get_config()
            self.config = app_cfg.llm_services.openai
        else:
            self.config = config

        env_api_key = os.getenv("OPENAI_API_KEY") or os.getenv(self.config.api_key_env_var)
        env_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
        final_base_url = env_base_url if env_base_url is not None else self.config.base_url
        env_model_name = os.getenv("OPENAI_MODEL_NAME")
        self.model_name = env_model_name if env_model_name is not None else self.config.model_name

        if not env_api_key and not final_base_url:
            logger.warning(
                "No API key or base URL configured for OpenAICompatibleClient. Calls may fail."
            )
        elif not env_api_key and final_base_url:
            logger.info("API key not found; assuming local model or keyless auth")
        elif env_api_key and not final_base_url:
            logger.info("Using OpenAI default base URL")
        else:
            logger.info("Using configured API key and base URL")

        self.client = AsyncOpenAI(
            api_key=env_api_key,
            base_url=final_base_url,
            timeout=self.config.timeout_seconds,
            max_retries=0,
        )

        try:
            mode_str = self.config.instructor_mode.upper()
            if hasattr(instructor.Mode, mode_str):
                mode_enum = getattr(instructor.Mode, mode_str)
            else:
                logger.warning(f"Invalid instructor_mode '{self.config.instructor_mode}'. Defaulting to TOOLS")
                mode_enum = instructor.Mode.TOOLS
            self.instruct_client = instructor.patch(self.client, mode=mode_enum)
        except Exception as e:  # pragma: no cover - patch errors rare
            logger.exception(f"Failed to patch OpenAI client: {e}")
            self.instruct_client = self.client

    @staticmethod
    def extract_json(raw: str) -> Dict[str, Any]:
        if not isinstance(raw, str):
            logger.warning("extract_json received non-string input")
            return {"error": "Invalid input type"}
        match_markdown = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match_markdown:
            json_str = match_markdown.group(1)
        else:
            first_brace = raw.find('{')
            last_brace = raw.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = raw[first_brace:last_brace + 1]
            else:
                json_str = raw.strip()
        try:
            return json.loads(json_str)
        except json.JSONDecodeError:
            try:
                return json.loads(json_str.replace("'", '"'))
            except json.JSONDecodeError:
                return {"error": f"Failed to parse JSON. Raw content snippet: {raw[:250]}..."}

    async def call_llm_raw(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs,
    ) -> str:
        logger.debug(f"Raw LLM call with messages: {messages}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.exception(f"LLM API error: {e}")
            raise
        except Exception as e:
            logger.exception("Generic error in raw LLM call:")
            raise

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs,
    ) -> BaseModel:
        logger.debug(f"Structured LLM call for {response_model.__name__}")
        try:
            response = await self.instruct_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                response_model=response_model,
                max_retries=self.config.max_retries,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs,
            )
            return response
        except (APIConnectionError, RateLimitError, APIStatusError) as e:
            logger.exception(f"LLM API error: {e}")
            raise
        except Exception as e:
            logger.exception("Error in structured LLM call:")
            raise


class OpenAICompatibleLLM(Service):
    """Adapter that exposes an OpenAICompatibleClient through the Service interface."""

    def __init__(self, llm_config: Optional[LLMServicesConfig] = None) -> None:
        super().__init__()
        self.llm_config = llm_config
        self._client: Optional[OpenAICompatibleClient] = None

    async def start(self) -> None:
        await super().start()
        openai_conf: Optional[OpenAIConfig] = None
        if self.llm_config:
            openai_conf = self.llm_config.openai
        self._client = OpenAICompatibleClient(config=openai_conf)

    async def stop(self) -> None:
        self._client = None
        await super().stop()

    def get_client(self) -> OpenAICompatibleClient:
        if self._client is None:
            raise RuntimeError("OpenAICompatibleLLM has not been started")
        return self._client
