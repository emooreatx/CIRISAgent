import logging
from typing import Dict, Any, List, Optional

from pydantic import ValidationError

from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import (
    ThoughtStatus,
    HandlerActionType,
    IncomingMessage,
)
from ciris_engine.schemas.graph_schemas_v1 import GraphScope
from ciris_engine.schemas.service_actions_v1 import FetchMessagesAction
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

PASSIVE_OBSERVE_LIMIT = 10  # number of messages to fetch for passive context
ACTIVE_OBSERVE_LIMIT = 50   # number of messages to fetch for active context

logger = logging.getLogger(__name__)


class ObserveHandler(BaseActionHandler):

#TODO break into handler for active and passive observation, and break out handling thoughts from the guardrails/DMAs from handling thoughts from the runtime detecting incoming messages in the fetchmessage queue
#We request observations by putting actions in the fetch message queue, but we also need to handle incoming messages that were put in the queue by different adapter observers
#If the source is the DMAs/guardrails, we are creating an action request for an active observation to be handled by the adapters
#If the source is the runtime, we are creating a task from the result to be processed (mark it PENDING)
#No dicts, only schemas and ENUMs and models and dataclasses


    async def _recall_from_messages(
        self,
        memory_service: Optional[Any],
        channel_id: Optional[str],
        messages: List[Dict[str, Any]],
    ) -> None:
        if not memory_service:
            return
        recall_ids = set()
        if channel_id:
            recall_ids.add(f"channel/{channel_id}")
        for msg in messages or []:
            aid = msg.get("author_id")
            if aid:
                recall_ids.add(f"user/{aid}")
        for rid in recall_ids:
            for scope in (
                GraphScope.IDENTITY,
                GraphScope.ENVIRONMENT,
                GraphScope.LOCAL,
            ):
                try:
                    await memory_service.recall(rid, scope)
                except Exception:
                    continue

    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: Dict[str, Any],
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        
        logger.info(f"ObserveHandler: Starting handle for thought {thought_id}")
        logger.debug(f"ObserveHandler: Parameters: {params}")
        logger.debug(f"ObserveHandler: Dispatch context keys: {list(dispatch_context.keys())}")
        
        await self._audit_log(
            HandlerActionType.OBSERVE,
            {**dispatch_context, "thought_id": thought_id},
            outcome="start",
        )
        
        final_status = ThoughtStatus.COMPLETED
        action_performed = False
        follow_up_info = f"OBSERVE action for thought {thought_id}"

        try:
            params = await self._validate_and_convert_params(params, ObserveParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.OBSERVE, dispatch_context, thought_id, e)
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.FAILED,
                final_action=result,
            )
            follow_up_text = f"OBSERVE action failed for thought {thought_id}. Reason: {e}"
            try:
                fu = create_follow_up_thought(parent=thought, content=follow_up_text)
                fu.context = {
                    "action_performed": HandlerActionType.OBSERVE.value,
                    "error_details": str(e),
                    "action_params": result.action_parameters,
                }
                persistence.add_thought(fu)
            except Exception as fe:
                await self._handle_error(HandlerActionType.OBSERVE, dispatch_context, thought_id, fe)
                raise FollowUpCreationError from fe
            return

        # Passive observations are already handled at the adapter level
        if not params.active:
            logger.debug(f"Passive observation for thought {thought_id} - no action needed")
            persistence.update_thought_status(
                thought_id=thought_id,
                status=ThoughtStatus.COMPLETED,
                final_action=result,
            )
            return

        channel_id = (
            params.channel_id
            or dispatch_context.get("channel_id")
            or getattr(thought, "context", {}).get("channel_id")
        )
        params.channel_id = channel_id

        # Get services with better logging
        multi_service_sink = self.get_multi_service_sink()
        logger.debug(f"ObserveHandler: Got multi-service sink: {type(multi_service_sink).__name__ if multi_service_sink else 'None'}")
        
        memory_service = await self.get_memory_service()
        logger.debug(f"ObserveHandler: Got memory service: {type(memory_service).__name__ if memory_service else 'None'}")

        try:
            logger.info(f"ObserveHandler: Performing active observation for channel {channel_id}")
            if not multi_service_sink or not channel_id:
                raise RuntimeError(f"No multi-service sink ({multi_service_sink}) or channel_id ({channel_id})")
            messages = await multi_service_sink.fetch_messages_sync(
                handler_name="ObserveHandler",
                channel_id=str(channel_id).lstrip("#"),
                limit=ACTIVE_OBSERVE_LIMIT,
                metadata={"active_observation": True}
            )
            if messages is None:
                raise RuntimeError("Failed to fetch messages via multi-service sink")
            # Note: Observer adapters handle observation at adapter level, not service level
            await self._recall_from_messages(memory_service, channel_id, messages)
            action_performed = True
            follow_up_info = f"Fetched {len(messages)} messages from {channel_id}"
            logger.info(f"ObserveHandler: Active observation complete - {follow_up_info}")
        except Exception as e:
            logger.exception(f"ObserveHandler error for {thought_id}: {e}")
            final_status = ThoughtStatus.FAILED
            follow_up_info = str(e)

        # Pass ActionSelectionResult directly to persistence - it handles serialization
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_status,
            final_action=result,
        )

        follow_up_text = (
            f"OBSERVE action completed. Info: {follow_up_info}"
            if action_performed
            else f"OBSERVE action failed: {follow_up_info}"
        )
        try:
            logger.info(f"ObserveHandler: Creating follow-up thought for {thought_id}")
            new_follow_up = create_follow_up_thought(parent=thought, content=follow_up_text)
            ctx = {
                "action_performed": HandlerActionType.OBSERVE.value,
                "action_params": params,
            }
            if final_status == ThoughtStatus.FAILED:
                ctx["error_details"] = follow_up_info
            new_follow_up.context = ctx
            persistence.add_thought(new_follow_up)
            logger.info(f"ObserveHandler: Follow-up thought created for {thought_id}")
            #TODO: Fix auditing
#            await self._audit_log(
#                HandlerActionType.OBSERVE,
#                {**dispatch_context, "thought_id": thought_id},
#                outcome="success" if action_performed else "failed",
#            )

        except Exception as e:
            logger.critical(
                "Failed to create follow-up for %s: %s", thought_id, e, exc_info=e
            )
            await self._audit_log(
                HandlerActionType.OBSERVE,
                {**dispatch_context, "thought_id": thought_id},
                outcome="failed_followup",
            )
            raise FollowUpCreationError from e

