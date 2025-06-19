from typing import Callable, Awaitable, Dict, Any, Optional
import logging

from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.message_buses import BusManager
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
        bus_manager: Optional[BusManager] = None,
        api_adapter: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
    ) -> None:
        super().__init__(
            on_observe,
            bus_manager=bus_manager,
            memory_service=memory_service,
            agent_id=agent_id,
            filter_service=None,
            secrets_service=secrets_service,
            origin_service="api",
        )
        self.api_adapter = api_adapter

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("APIObserver received non-IncomingMessage")  # type: ignore[unreachable]
            return
        
        is_agent_message = self.agent_id and msg.author_id == self.agent_id
        
        processed_msg = await self._process_message_secrets(msg)
        
        self._history.append(processed_msg)
        
        if is_agent_message:
            logger.debug("Added agent's own message %s to history (no task created)", msg.message_id)
            return
        
        await self._handle_passive_observation(processed_msg)
        await self._recall_context(processed_msg)


    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        from ciris_engine.utils.constants import (
            API_DEFERRAL_CHANNEL_ID,
            WA_API_USER,
            DEFAULT_WA,
        )

        deferral_channel_id = API_DEFERRAL_CHANNEL_ID
        wa_api_user = WA_API_USER or DEFAULT_WA
        
        if not self._is_agent_message(msg):
            if msg.channel_id != deferral_channel_id:
                await self._create_passive_observation_result(msg)
            else:
                logger.debug("Ignoring message from non-deferral channel %s", msg.channel_id)
        elif msg.channel_id == deferral_channel_id and msg.author_name == wa_api_user:
            await self._add_to_feedback_queue(msg)
        else:
            logger.debug("Ignoring agent message from channel %s, author %s", msg.channel_id, msg.author_name)

    def _is_agent_message(self, msg: IncomingMessage) -> bool:
        if self.agent_id and msg.author_id == self.agent_id:
            return True
        return getattr(msg, "is_bot", False)

