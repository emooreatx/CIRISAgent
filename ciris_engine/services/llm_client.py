import os
import json
import re
import logging
from typing import Dict, Any, Optional, Type, List

from pydantic import BaseModel
from openai import AsyncOpenAI, APIConnectionError, RateLimitError, APIStatusError
import instructor

# Configuration
from ciris_engine.core.config_manager import get_config
from ciris_engine.schemas.config_schemas_v1 import OpenAIConfig # ERIC

logger = logging.getLogger(__name__)

class CIRISLLMClient:
    """
    Client for interacting with LLMs, primarily OpenAI-compatible APIs,
    with support for structured responses using the 'instructor' library.
    """

    def __init__(self, config: Optional[OpenAIConfig] = None):
        """
        Initializes the LLM client.
        Uses the provided OpenAIConfig or fetches it from the global config manager.
        """
        if config is None:
            app_cfg = get_config() # Fetches or loads global AppConfig
            self.config = app_cfg.llm_services.openai
        else:
            self.config = config

        # --- Prioritize Standard Environment Variables ---
        # Check standard OpenAI env vars first, then fall back to config file values.
        # Note: OpenAI library uses OPENAI_BASE_URL, not OPENAI_API_BASE by default.
        # We will check for both for flexibility, prioritizing OPENAI_BASE_URL.

        env_api_key = os.getenv("OPENAI_API_KEY") or os.getenv(self.config.api_key_env_var)
        # Prioritize OPENAI_BASE_URL, then OPENAI_API_BASE, then config file's base_url
        env_base_url = os.getenv("OPENAI_BASE_URL") or os.getenv("OPENAI_API_BASE")
        final_base_url = env_base_url if env_base_url is not None else self.config.base_url

        # Prioritize OPENAI_MODEL_NAME env var, then config file's model_name
        env_model_name = os.getenv("OPENAI_MODEL_NAME")
        self.model_name = env_model_name if env_model_name is not None else self.config.model_name

        if not env_api_key and not final_base_url:
            logger.warning(
                f"No API key found in env vars ('OPENAI_API_KEY' or '{self.config.api_key_env_var}') "
                "and no base_url found in env vars ('OPENAI_BASE_URL', 'OPENAI_API_BASE') or config file. "
                "OpenAI client may fail."
            )
        elif not env_api_key and final_base_url:
             logger.info(f"API key not found in environment, but using base_url: {final_base_url}. Assuming local model or keyless auth.")
        elif env_api_key and not final_base_url:
             logger.info(f"Using API key from environment, but no base_url configured. Will use OpenAI default.")
        else: # Both key and base_url might be set
             logger.info(f"Using API key from environment and base_url: {final_base_url}")

        logger.debug(f"Final API Key to use: {'*' * 5 if env_api_key else 'None'}")
        logger.debug(f"Final Base URL to use: {final_base_url}")
        logger.debug(f"Final Model Name to use: {self.model_name}")

        # Initialize the actual client using the determined values
        self.client = AsyncOpenAI(
            api_key=env_api_key, # Use the key found (or None)
            base_url=final_base_url, # Use the base_url found (or None)
            timeout=self.config.timeout_seconds, # Still use timeout/retries from config file
            max_retries=0 # Instructor handles retries, so set OpenAI client retries to 0
        )
        # self.model_name is already set above based on env/config priority
        logger.debug(f"CIRISLLMClient.__init__: self.client.base_url after AsyncOpenAI init: {self.client.base_url}")

        # Patch with instructor
        try:
            instructor_mode_str = self.config.instructor_mode.upper()
            # Ensure instructor_mode_str is one of the valid string representations of instructor.Mode
            # Valid modes as of instructor 0.5.2: 'TOOLS', 'JSON', 'MD_JSON', 'OPENAI_TOOLS', 'ANTHROPIC_TOOLS', 'GOOGLE_TOOLS'
            # instructor.Mode itself is an enum. getattr(instructor.Mode, "TOOLS") works.
            if hasattr(instructor.Mode, instructor_mode_str):
                instructor_mode_enum = getattr(instructor.Mode, instructor_mode_str)
            else:
                logger.warning(f"Invalid instructor_mode '{self.config.instructor_mode}'. Defaulting to TOOLS.")
                instructor_mode_enum = instructor.Mode.TOOLS
            
            self.instruct_client = instructor.patch(self.client, mode=instructor_mode_enum)
            # Check the base_url of the underlying client of the instructor-patched client
            if hasattr(self.instruct_client, "client") and hasattr(self.instruct_client.client, "base_url"):
                 logger.debug(f"CIRISLLMClient.__init__: self.instruct_client.client.base_url after patch: {self.instruct_client.client.base_url}")
            elif hasattr(self.instruct_client, "_client") and hasattr(self.instruct_client._client, "base_url"): # Common private attribute name
                 logger.debug(f"CIRISLLMClient.__init__: self.instruct_client._client.base_url after patch: {self.instruct_client._client.base_url}")
            else:
                 logger.debug(f"CIRISLLMClient.__init__: Could not determine base_url of instructor's underlying client directly. Patched client type: {type(self.instruct_client)}")

            logger.info(f"Instructor patched OpenAI client with mode: {instructor_mode_enum.name}")
        except Exception as e:
            logger.exception(f"Failed to patch OpenAI client with instructor: {e}. Client will operate without instructor features.")
            self.instruct_client = self.client # Fallback to unpatched client

    @staticmethod
    def extract_json(raw: str) -> Dict[str, Any]:
        """
        Extracts JSON from a string that may contain markdown formatting,
        newlines within the JSON structure, or other LLM artifacts.
        """
        if not isinstance(raw, str):
            logger.warning(f"extract_json received non-string input: {type(raw)}. Returning error dict.")
            return {"error": "Invalid input type to extract_json."}

        # Attempt to find JSON within markdown code blocks
        match_markdown = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", raw, re.DOTALL)
        if match_markdown:
            json_str = match_markdown.group(1)
        else:
            first_brace = raw.find('{')
            last_brace = raw.rfind('}')
            if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
                json_str = raw[first_brace : last_brace + 1]
            else:
                json_str = raw.strip()
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e1:
            logger.warning(f"Initial JSONDecodeError for string '{json_str[:200]}...': {e1}")
            try:
                json_str_fixed_quotes = json_str.replace("'", '"')
                return json.loads(json_str_fixed_quotes)
            except json.JSONDecodeError as e2:
                logger.error(f"Persistent JSONDecodeError for string '{json_str_fixed_quotes[:200]}...': {e2}")
                # Last resort: find any valid JSON object
                try:
                    best_match_obj = None
                    for match in re.finditer(r"\{(?:[^{}]|(?R))*\}", raw, re.DOTALL):
                        try:
                            candidate = json.loads(match.group(0))
                            if best_match_obj is None or len(match.group(0)) > len(json.dumps(best_match_obj)):
                                best_match_obj = candidate
                        except json.JSONDecodeError:
                            continue
                    if best_match_obj:
                        logger.warning("Successfully parsed JSON using recursive brace matching fallback.")
                        return best_match_obj
                except Exception as fallback_ex:
                     logger.error(f"Error during recursive brace matching fallback: {fallback_ex}")
                return {"error": f"Failed to parse JSON. Raw content snippet: {raw[:250]}..."}

    async def call_llm_raw(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1024,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """
        Makes a raw call to the LLM, returning the string content.
        """
        logger.debug(f"Raw LLM call to model {self.model_name} with messages: {messages}")
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            content = response.choices[0].message.content
            return content.strip() if content else ""
        except APIConnectionError as e:
            logger.exception(f"LLM APIConnectionError: {e}")
            raise
        except RateLimitError as e:
            logger.exception(f"LLM RateLimitError: {e}")
            raise
        except APIStatusError as e:
            logger.exception(f"LLM APIStatusError status={e.status_code} response={e.response}: {e}")
            raise
        except Exception as e:
            logger.exception("Generic error in raw LLM call:")
            raise

    async def call_llm_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        max_tokens: int = 1024,
        temperature: float = 0.0, # Lower temp for structured output
        **kwargs
    ) -> BaseModel:
        """
        Makes a call to the LLM expecting a response that conforms to the given Pydantic model,
        using the instructor-patched client.
        """
        logger.debug(f"Structured LLM call to model {self.model_name} for response_model {response_model.__name__} with messages: {messages}")
        try:
            # Use self.instruct_client which is the patched version
            response = await self.instruct_client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                response_model=response_model,
                max_retries=self.config.max_retries, # Instructor handles retries
                max_tokens=max_tokens,
                temperature=temperature,
                **kwargs
            )
            return response
        except APIConnectionError as e:
            logger.exception(f"LLM APIConnectionError (structured): {e}")
            raise
        except RateLimitError as e:
            logger.exception(f"LLM RateLimitError (structured): {e}")
            raise
        except APIStatusError as e:
            logger.exception(f"LLM APIStatusError (structured) status={e.status_code} response={e.response}: {e}")
            raise
        except Exception as e: # Catches validation errors from instructor too
            logger.exception(f"Error in structured LLM call for model {response_model.__name__}:")
            raise

# Example of how to get a client instance:
# from ciris_engine.services.llm_client import CIRISLLMClient
# client = CIRISLLMClient()
