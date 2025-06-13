import json
import re
import logging
from typing import Dict, Any, Optional, Type, List, Tuple, Union, cast

from pydantic import BaseModel
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
import instructor

from ciris_engine.adapters.base import Service
from ciris_engine.config.config_manager import get_config
from ciris_engine.schemas.config_schemas_v1 import OpenAIConfig, LLMServicesConfig
from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage

logger = logging.getLogger(__name__)


class OpenAICompatibleClient(Service):
    """Client for interacting with OpenAI-compatible APIs."""

    def __init__(self, config: Optional[OpenAIConfig] = None, telemetry_service: Optional[Any] = None) -> None:
        if config is None:
            app_cfg = get_config()
            self.openai_config = app_cfg.llm_services.openai
        else:
            self.openai_config = config
        
        self.telemetry_service = telemetry_service

        # Set up retry configuration specifically for OpenAI API calls
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": getattr(self.openai_config, 'max_retries', 5),
                    "base_delay": 1.0,
                    "max_delay": 60.0,
                },
                "api_call": {
                    "retryable_exceptions": (APIConnectionError, RateLimitError),
                    "non_retryable_exceptions": (APIStatusError,)  # Will be filtered by status code
                }
            }
        }
        super().__init__(config=retry_config)

        api_key = self.openai_config.api_key
        base_url = self.openai_config.base_url
        model_name = self.openai_config.model_name or 'gpt-4o-mini'
        self.model_name = model_name

        if not api_key and not base_url:
            logger.warning(
                "No API key or base URL configured for OpenAICompatibleClient. Calls may fail."
            )
        elif not api_key and base_url:
            logger.info("API key not found; assuming local model or keyless auth")
        elif api_key and not base_url:
            logger.info("Using OpenAI default base URL")
        else:
            logger.info("Using configured API key and base URL")

        self.client = AsyncOpenAI(
            api_key=api_key,
            base_url=base_url,
            timeout=self.openai_config.timeout_seconds,
            max_retries=0,  # Disable OpenAI client retries, we'll handle our own
        )

        try:
            mode_str = self.openai_config.instructor_mode.upper()
            if hasattr(instructor.Mode, mode_str):
                mode_enum = getattr(instructor.Mode, mode_str)
            else:
                logger.warning(f"Invalid instructor_mode '{self.openai_config.instructor_mode}'. Defaulting to TOOLS")
                mode_enum = instructor.Mode.TOOLS
            self.instruct_client = instructor.patch(self.client, mode=mode_enum)
        except Exception as e:  # pragma: no cover - patch errors rare
            logger.exception(f"Failed to patch OpenAI client: {e}")
            self.instruct_client = self.client

    async def start(self) -> None:
        """Start the client service."""
        await super().start()

    async def stop(self) -> None:
        """Stop the client service."""
        await super().stop()

    @staticmethod
    def extract_json(raw: str) -> Dict[str, Any]:
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
            parsed: Dict[str, Any] = json.loads(json_str)
            return parsed
        except json.JSONDecodeError:
            try:
                parsed_retry: Dict[str, Any] = json.loads(json_str.replace("'", '"'))
                return parsed_retry
            except json.JSONDecodeError:
                return {"error": f"Failed to parse JSON. Raw content snippet: {raw}"}

    async def call_llm_raw(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs: Any,
    ) -> Tuple[str, ResourceUsage]:
        logger.debug(f"Raw LLM call with messages: {messages}")
        
        async def _make_raw_call(
            msgs: List[Dict[str, str]],
            max_toks: int,
            temp: float,
            extra_kwargs: Dict[str, Any]
        ) -> Tuple[str, ResourceUsage]:
            # Convert messages to the format expected by OpenAI if needed
            if msgs and isinstance(msgs[0], dict):
                formatted_messages = [{"role": msg.get("role", "user"), "content": msg.get("content", "")} for msg in msgs]
            else:
                formatted_messages = msgs
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=cast(Any, formatted_messages),
                max_tokens=max_toks,
                temperature=temp,
                **extra_kwargs,
            )
            usage = getattr(response, "usage", None)
            usage_obj = ResourceUsage(
                tokens=getattr(usage, "total_tokens", 0)
            )
            
            # Record token usage in telemetry
            if self.telemetry_service and usage_obj.tokens > 0:
                await self.telemetry_service.record_metric("llm_tokens_used", usage_obj.tokens)
                await self.telemetry_service.record_metric("llm_api_call")
            
            content = response.choices[0].message.content
            return (content.strip() if content else "", usage_obj)
            
        # Create a wrapper function that matches the expected signature
        async def wrapped_call(*args: Any, **kwargs: Any) -> tuple[str, ResourceUsage]:
            return await _make_raw_call(*args, **kwargs)
        
        # Use base class retry with OpenAI-specific error handling
        return await self.retry_with_backoff(
            wrapped_call,
            messages,
            max_tokens,
            temperature,
            kwargs,
            **self.get_retry_config("api_call")
        )

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any,
    ) -> Tuple[BaseModel, ResourceUsage]:
        logger.debug(f"Structured LLM call for {response_model.__name__}")
        
        async def _make_structured_call(
            msgs: List[Dict[str, str]],
            resp_model: Type[BaseModel],
            max_toks: int,
            temp: float,
            extra_kwargs: Dict[str, Any]
        ) -> Tuple[BaseModel, ResourceUsage]:
            # Convert messages to the format expected by OpenAI  
            formatted_messages = [{"role": msg.get("role", "user"), "content": msg.get("content", "")} for msg in msgs]
            response = await self.instruct_client.chat.completions.create(
                model=self.model_name,
                messages=cast(Any, formatted_messages),
                response_model=resp_model,
                max_retries=0,  # Disable instructor retries, we handle our own
                max_tokens=max_toks,
                temperature=temp,
                **extra_kwargs,
            )
            usage = getattr(response, "usage", None)
            usage_obj = ResourceUsage(
                tokens=getattr(usage, "total_tokens", 0)
            )
            
            # Record token usage in telemetry
            if self.telemetry_service and usage_obj.tokens > 0:
                await self.telemetry_service.record_metric("llm_tokens_used", usage_obj.tokens)
                await self.telemetry_service.record_metric("llm_api_call_structured")
            
            return response, usage_obj
            
        # Create a wrapper function that matches the expected signature
        async def wrapped_structured_call(*args: Any, **kwargs: Any) -> tuple[BaseModel, ResourceUsage]:
            return await _make_structured_call(*args, **kwargs)
        
        # Use base class retry with OpenAI-specific error handling
        return await self.retry_with_backoff(
            wrapped_structured_call,
            messages,
            response_model,
            max_tokens,
            temperature,
            kwargs,
            **self.get_retry_config("api_call")
        )


class OpenAICompatibleLLM(Service):
    """Adapter that exposes an OpenAICompatibleClient through the Service interface."""

    def __init__(self, llm_config: Optional[LLMServicesConfig] = None, telemetry_service: Optional[Any] = None) -> None:
        retry_config = {
            "retry": {
                "global": {
                    "max_retries": 5,
                    "base_delay": 1.0,
                    "max_delay": 60.0,
                    "backoff_multiplier": 2.0,
                    "jitter_range": 0.25
                },
                "llm_call": {
                    "max_retries": 5,
                    "base_delay": 1.0,
                }
            }
        }
        super().__init__(config=retry_config)
        self.llm_config = llm_config
        self.telemetry_service = telemetry_service
        self._client: Optional[OpenAICompatibleClient] = None

    async def start(self) -> None:
        await super().start()
        openai_conf: Optional[OpenAIConfig] = None
        if self.llm_config:
            openai_conf = self.llm_config.openai
        self._client = OpenAICompatibleClient(config=openai_conf, telemetry_service=self.telemetry_service)

    async def stop(self) -> None:
        self._client = None
        await super().stop()

    def get_client(self) -> OpenAICompatibleClient:
        if self._client is None:
            raise RuntimeError("OpenAICompatibleLLM has not been started")
        return self._client
