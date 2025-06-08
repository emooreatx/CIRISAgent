import asyncio
from typing import Callable, Awaitable, Dict, Any, Optional, List
import os
import logging

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.schemas.graph_schemas_v1 import GraphScope, GraphNode, NodeType
from ciris_engine.utils.constants import DEFAULT_WA
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.secrets.service import SecretsService
from ciris_engine.adapters.base_observer import BaseObserver

logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10

class APIObserver(BaseObserver[IncomingMessage]):
    def __init__(
        self,
        on_observe: Callable[[Dict[str, Any]], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        multi_service_sink: Optional[MultiServiceActionSink] = None,
        api_adapter: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
    ) -> None:
        super().__init__(
            on_observe,
            memory_service,
            agent_id,
            multi_service_sink,
            None,
            secrets_service,
            origin_service="api",
        )
        self.api_adapter = api_adapter

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("APIObserver received non-IncomingMessage")
            return
        
        # Check if this is the agent's own message
        is_agent_message = self.agent_id and msg.author_id == self.agent_id
        
        # Process message for secrets detection and replacement (for all messages)
        processed_msg = await self._process_message_secrets(msg)
        
        # Add ALL messages to history (including agent's own)
        self._history.append(processed_msg)
        
        # If it's the agent's message, stop here (no task creation)
        if is_agent_message:
            logger.debug("Added agent's own message %s to history (no task created)", msg.message_id)
            return
        
        await self._handle_passive_observation(processed_msg)
        await self._recall_context(processed_msg)


    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        from ciris_engine.utils.constants import (
            API_CHANNEL_ID,
            API_DEFERRAL_CHANNEL_ID,
            WA_API_USER,
            DEFAULT_WA,
        )

        default_channel_id = API_CHANNEL_ID
        deferral_channel_id = API_DEFERRAL_CHANNEL_ID
        wa_api_user = WA_API_USER or DEFAULT_WA
        if msg.channel_id == default_channel_id and not self._is_agent_message(msg):
            await self._create_passive_observation_result(msg)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_api_user:
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring message from channel %s, author %s", msg.channel_id, msg.author_name)

    def _is_agent_message(self, msg: IncomingMessage) -> bool:
        if self.agent_id and msg.author_id == self.agent_id:
            return True
        return getattr(msg, "is_bot", False)

