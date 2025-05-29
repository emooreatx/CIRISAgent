import logging
from typing import Optional

from .base import Service
from ciris_engine.services.llm_client import CIRISLLMClient
from ciris_engine.schemas.config_schemas_v1 import OpenAIConfig, LLMServicesConfig

logger = logging.getLogger(__name__)

class LLMService(Service):
    """
    Service responsible for providing access to the LLM client.
    It initializes the CIRISLLMClient based on configuration.
    """

    def __init__(self, llm_config: Optional[LLMServicesConfig] = None):
        """
        Initializes the LLMService.

        Args:
            llm_config: Optional LLMServicesConfig. If not provided, it will be
                        fetched from the global AppConfig.
        """
        super().__init__() # No specific service config dict needed for base Service
        
        self._llm_client: Optional[CIRISLLMClient] = None
        self.llm_config = llm_config
        
        # Initialization of the client is deferred to start() to ensure
        # global config is loaded if llm_config is not provided.
        logger.info("LLMService initialized. Client will be created on start().")

    async def start(self):
        """Initializes the CIRISLLMClient."""
        await super().start() # Call parent's start method
        if self._llm_client is None:
            try:
                openai_conf: Optional[OpenAIConfig] = None
                if self.llm_config:
                    openai_conf = self.llm_config.openai
                # If openai_conf is still None, CIRISLLMClient will fetch from global config
                self._llm_client = CIRISLLMClient(config=openai_conf)
                logger.info("CIRISLLMClient created successfully within LLMService.")
            except Exception as e:
                logger.exception(f"LLMService: Failed to initialize CIRISLLMClient: {e}")
                # Depending on desired behavior, could re-raise or set a failed state
                raise # Re-raise to prevent service from starting in a bad state
        else:
            logger.info("LLMService: CIRISLLMClient already initialized.")
            
    async def stop(self):
        """Stops the LLM service (currently a no-op for the client itself)."""
        # The AsyncOpenAI client doesn't have an explicit close/stop method.
        # Resources are managed by its internal HTTPX client, which should be
        # handled by garbage collection or when the event loop closes.
        logger.info("LLMService stopping. No explicit client cleanup required.")
        self._llm_client = None # Allow re-initialization if started again
        await super().stop() # Call parent's stop method

    def get_client(self) -> CIRISLLMClient:
        """
        Returns the initialized CIRISLLMClient instance.

        Raises:
            RuntimeError: If the client has not been initialized (start() not called or failed).
        """
        if self._llm_client is None:
            raise RuntimeError("LLMService: CIRISLLMClient has not been initialized. Call start() first.")
        return self._llm_client
