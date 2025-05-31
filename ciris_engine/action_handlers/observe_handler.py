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
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class ObserveHandler(BaseActionHandler):
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

        if isinstance(params, dict):
            try:
                params = ObserveParams(**params)
            except ValidationError as e:
                logger.error(
                    "OBSERVE params invalid for %s: %s", thought_id, e
                )
                final_status = ThoughtStatus.FAILED
                follow_up_info = str(e)
                persistence.update_thought_status(
                    thought_id=thought_id,
                    status=final_status,
                    final_action=None,
                )
                raise FollowUpCreationError from e
        elif not isinstance(params, ObserveParams):
            logger.error(
                "OBSERVE params wrong type %s for thought %s", type(params), thought_id
            )
            final_status = ThoughtStatus.FAILED
            follow_up_info = "invalid params"
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_status,
                final_action=None,
            )
            raise FollowUpCreationError("Invalid params type")

        channel_id = (
            params.channel_id
            or dispatch_context.get("channel_id")
            or getattr(thought, "context", {}).get("channel_id")
            or getattr(self.dependencies.observer_service, "monitored_channel_id", None)
        )
        params.channel_id = channel_id

        # Get services with better logging
        comm_service = await self.get_communication_service()
        logger.debug(f"ObserveHandler: Got communication service: {type(comm_service).__name__ if comm_service else 'None'}")
        
        observer_service = await self.get_observer_service()
        logger.debug(f"ObserveHandler: Got observer service: {type(observer_service).__name__ if observer_service else 'None'}")
        
        # Fallback to legacy observer service if needed
        if not observer_service and hasattr(self.dependencies, 'observer_service'):
            observer_service = self.dependencies.observer_service
            logger.info(f"ObserveHandler: Using legacy observer service from dependencies")
        
        memory_service = await self.get_memory_service()
        logger.debug(f"ObserveHandler: Got memory service: {type(memory_service).__name__ if memory_service else 'None'}")

        try:
            if params.active:
                logger.info(f"ObserveHandler: Performing active observation for channel {channel_id}")
                if not comm_service or not channel_id:
                    raise RuntimeError(f"No communication service ({comm_service}) or channel_id ({channel_id})")
                messages = await comm_service.fetch_messages(
                    str(channel_id).lstrip("#"), getattr(params, "limit", 10)
                )
                if not messages and observer_service and hasattr(observer_service, "get_recent_messages"):
                    messages = await observer_service.get_recent_messages(getattr(params, "limit", 10))
                await self._recall_from_messages(memory_service, channel_id, messages)
                action_performed = True
                follow_up_info = f"Fetched {len(messages)} messages from {channel_id}"
                logger.info(f"ObserveHandler: Active observation complete - {follow_up_info}")
            else:
                logger.info(f"ObserveHandler: Performing passive observation")
                if not observer_service:
                    logger.error(f"ObserveHandler: Observer service unavailable for passive observation")
                    raise RuntimeError("Observer service unavailable")
                incoming = IncomingMessage(
                    message_id=thought.thought_id,
                    author_id=thought.context.get("author_id", "unknown"),
                    author_name=thought.context.get("author_name", "unknown"),
                    content=thought.content,
                    channel_id=channel_id,
                )
                if hasattr(observer_service, "handle_incoming_message"):
                    await observer_service.handle_incoming_message(incoming)
                elif hasattr(observer_service, "observe"):
                    await observer_service.observe({"message": incoming})
                else:
                    raise RuntimeError("Observer service missing method")
                action_performed = True
                follow_up_info = "Observation forwarded"
        except Exception as e:
            logger.exception(f"ObserveHandler error for {thought_id}: {e}")
            final_status = ThoughtStatus.FAILED
            follow_up_info = str(e)

        final_action_dump = (
            result.model_dump(mode="json") if hasattr(result, "model_dump") else result
        )
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_status,
            final_action=final_action_dump,
        )

        follow_up_text = (
            f"OBSERVE action completed. Info: {follow_up_info}"
            if action_performed
            else f"OBSERVE action failed: {follow_up_info}"
        )
        try:
            new_follow_up = create_follow_up_thought(parent=thought, content=follow_up_text)
            ctx = {
                "action_performed": HandlerActionType.OBSERVE.value,
                "action_params": params.model_dump(mode="json"),
            }
            if final_status == ThoughtStatus.FAILED:
                ctx["error_details"] = follow_up_info
            new_follow_up.context = ctx
            persistence.add_thought(new_follow_up)
            await self._audit_log(
                HandlerActionType.OBSERVE,
                {**dispatch_context, "thought_id": thought_id},
                outcome="success" if action_performed else "failed",
            )
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
