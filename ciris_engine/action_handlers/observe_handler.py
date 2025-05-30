import logging
import os
from typing import Dict, Any
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError
from .discord_observe_handler import handle_discord_observe_event
from ciris_engine.sinks.action_types import FetchMessagesAction
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from pydantic import BaseModel, ValidationError

logger = logging.getLogger(__name__)


class ObserveHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,  # Updated to v1 result schema
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"OBSERVE action for thought {thought_id}"

        # DEBUG: Log the incoming parameters
        logger.warning(f"OBSERVE HANDLER DEBUG: thought_id={thought_id}, params type={type(params)}, params={params}")

        # Always use schema internally
        if isinstance(params, dict):
            try:
                params = ObserveParams(**params)
                logger.warning(f"OBSERVE HANDLER DEBUG: Created ObserveParams from dict: {params}")
            except ValidationError as e:
                self.logger.error(f"OBSERVE action params dict could not be parsed: {e}. Thought ID: {thought_id}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"OBSERVE action failed: Invalid parameters dict for thought {thought_id}. Error: {e}"
                persistence.update_thought_status(
                    thought_id=thought_id,
                    status=final_thought_status,
                    final_action=None
                )
                raise FollowUpCreationError(f"OBSERVE action failed: Invalid parameters dict for thought {thought_id}. Error: {e}")
        elif not isinstance(params, ObserveParams):
            self.logger.error(f"OBSERVE action params are not ObserveParams model or dict. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"OBSERVE action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_thought_status,
                final_action=result.model_dump() if hasattr(result, 'model_dump') else result,
            )
            raise FollowUpCreationError(f"OBSERVE action failed: Invalid parameters type ({type(params)}) for thought {thought_id}.")
        
        # DEBUG: Log the processed parameters
        logger.warning(f"OBSERVE HANDLER DEBUG: processed params: active={params.active}, channel_id={params.channel_id}")
        
        logger.warning(f"OBSERVE HANDLER DEBUG: Processing {params.active} observation")
        logger.warning(f"OBSERVE HANDLER DEBUG: Channel ID: {params.channel_id}")
        logger.warning(f"OBSERVE HANDLER DEBUG: Memory service available: {self.dependencies.memory_service is not None}")

        if params.active:  # v1 uses 'active'
            # Use the new MultiServiceActionSink with FETCH_MESSAGES action
            try:
                target_channel_id = params.channel_id or dispatch_context.get("channel_id")
                if not target_channel_id:
                    target_channel_id = os.getenv("DISCORD_CHANNEL_ID")

                if not target_channel_id:
                    raise ValueError("No channel ID available for active observation")

                # Check if we have service registry for new action system
                if self.dependencies.service_registry:
                    # Use new action system with MultiServiceActionSink
                    action_sink = MultiServiceActionSink(
                        service_registry=self.dependencies.service_registry,
                        fallback_channel_id=target_channel_id
                    )
                    
                    # Create FETCH_MESSAGES action
                    fetch_action = FetchMessagesAction(
                        type=None,  # Will be set in __post_init__
                        handler_name="ObserveHandler",
                        metadata={
                            "thought_id": thought_id,
                            "observation_type": "active",
                            "dispatch_context": dispatch_context
                        },
                        channel_id=target_channel_id,
                        limit=getattr(params, 'limit', 10)
                    )
                    
                    # Start action sink and enqueue action
                    await action_sink.start()
                    try:
                        success = await action_sink.enqueue_action(fetch_action)
                        if success:
                            action_performed_successfully = True
                            follow_up_content_key_info = f"Active message fetch queued for channel: {target_channel_id}"
                        else:
                            raise Exception("Failed to enqueue FETCH_MESSAGES action")
                    finally:
                        await action_sink.stop()
                
                else:
                    # Fallback to legacy Discord observe handler
                    logger.warning("No service registry available, falling back to legacy Discord observe handler")
                    
                    # Build comprehensive context for active observation
                    observe_context = {
                        "default_channel_id": target_channel_id or os.getenv("DISCORD_CHANNEL_ID"),
                        "agent_id": dispatch_context.get("agent_id")
                    }
                    
                    # Try multiple sources for discord_service
                    discord_service = None
                    
                    # 1. From dependencies
                    if hasattr(self.dependencies, 'io_adapter') and hasattr(self.dependencies.io_adapter, 'client'):
                        discord_service = self.dependencies.io_adapter.client
                        logger.debug("Got discord_service from dependencies.io_adapter.client")
                    
                    # 2. From dispatch_context
                    if not discord_service:
                        discord_service = dispatch_context.get("discord_service")
                        if discord_service:
                            logger.debug("Got discord_service from dispatch_context")
                    
                    # 3. From services dict in dispatch_context
                    if not discord_service and "services" in dispatch_context:
                        services = dispatch_context["services"]
                        discord_service = services.get("discord_service") or services.get("discord_client")
                        if discord_service:
                            logger.debug("Got discord_service from dispatch_context.services")
                    
                    # 4. Try to get from global runtime state (last resort)
                    if not discord_service:
                        # This is a fallback - ideally context should provide it
                        logger.warning("discord_service not found in expected locations, active observation may fail")
                    
                    observe_context["discord_service"] = discord_service

                    await handle_discord_observe_event(
                        payload={
                            "channel_id": target_channel_id,
                            "offset": params.offset if hasattr(params, 'offset') else 0,
                            "limit": params.limit if hasattr(params, 'limit') else 10,
                            "include_agent": True
                        },
                        mode="active",
                        context=observe_context
                    )
                    action_performed_successfully = True
                    follow_up_content_key_info = f"Active Discord observe handler invoked for channel: {target_channel_id}"
            except Exception as e:
                self.logger.exception(f"Error during active Discord observe handler for thought {thought_id}: {e}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"Active Discord observe handler error: {str(e)}"
        else:  # Passive observe
            # Use the Discord observe handler in passive mode
            try:
                await handle_discord_observe_event(
                    payload={
                        "message_id": thought.thought_id,
                        "content": thought.content,
                        "context": getattr(thought, "context", {}),
                        "task_description": getattr(thought, "content", None)
                    },
                    mode="passive"
                )
                action_performed_successfully = True
                follow_up_content_key_info = "Passive Discord observe handler invoked"
            except Exception as e:
                self.logger.exception(f"Error during passive Discord observe handler for thought {thought_id}: {e}")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"Passive Discord observe handler error: {str(e)}"

        # v1 uses 'final_action' instead of 'final_action_result'
        result_data = result.model_dump() if hasattr(result, 'model_dump') else result
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result_data,  # v1 field
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after OBSERVE attempt.")

        # ALWAYS create a follow-up thought for OBSERVE actions
        # This ensures the DMA can see the results and continue reasoning
        should_create_standard_follow_up = True
        
        # DEBUG: Log the decision logic
        logger.warning(f"OBSERVE HANDLER DEBUG: Follow-up decision logic - params={params}, params.active={params.active if params else 'None'}, action_performed_successfully={action_performed_successfully}")
        logger.warning(f"OBSERVE HANDLER DEBUG: Always creating follow-up for OBSERVE actions")

        logger.warning(f"OBSERVE HANDLER DEBUG: should_create_standard_follow_up={should_create_standard_follow_up}")

        if should_create_standard_follow_up:
            follow_up_text = ""
            if action_performed_successfully:
                observation_type = "active" if (params and params.active) else "passive"
                follow_up_text = f"OBSERVE action ({observation_type}) for thought {thought_id} completed. Info: {follow_up_content_key_info}. Review if this completes the task or if further steps are needed."
            else:  # Failed
                follow_up_text = f"OBSERVE action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."

            try:
                new_follow_up = create_follow_up_thought(
                    parent=thought,
                    content=follow_up_text,
                )

                # v1 uses 'context' instead of 'processing_context'
                context_for_follow_up = {
                    "action_performed": HandlerActionType.OBSERVE.value
                }
                if final_thought_status == ThoughtStatus.FAILED:
                    context_for_follow_up["error_details"] = follow_up_content_key_info

                # When serializing for follow-up, convert to dict
                action_params_dump = params.model_dump(mode="json") if hasattr(params, "model_dump") else params
                context_for_follow_up["action_params"] = action_params_dump

                new_follow_up.context = context_for_follow_up  # v1 uses 'context'

                persistence.add_thought(new_follow_up)
                self.logger.info(
                    f"Created standard follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after OBSERVE action."
                )
                await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="success" if action_performed_successfully else "failed")
            except Exception as e:
                self.logger.critical(
                    f"Failed to create follow-up thought for {thought_id}: {e}",
                    exc_info=e,
                )
                await self._audit_log(HandlerActionType.OBSERVE, {**dispatch_context, "thought_id": thought_id}, outcome="failed_followup")
                raise FollowUpCreationError from e
        return result