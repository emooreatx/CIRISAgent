import logging
import os
import uuid
from typing import Dict, Any
from datetime import datetime, timezone

from pydantic import BaseModel

from ciris_engine.core.agent_core_schemas import ActionSelectionPDMAResult, ObserveParams, Thought
from ciris_engine.core.foundational_schemas import ThoughtStatus, HandlerActionType # HandlerActionType should be imported here
from ciris_engine.core import persistence
from .base_handler import BaseActionHandler, ActionHandlerDependencies
from .helpers import create_follow_up_thought

logger = logging.getLogger(__name__)

class ObserveHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionPDMAResult,
        thought: Thought,
        dispatch_context: Dict[str, Any]
    ) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        
        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"OBSERVE action for thought {thought_id}"

        if not isinstance(params, ObserveParams):
            self.logger.error(f"OBSERVE action params are not ObserveParams model. Type: {type(params)}. Thought ID: {thought_id}")
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = f"OBSERVE action failed: Invalid parameters type ({type(params)}) for thought {thought_id}."
        elif params.perform_active_look:
            # Active Look Logic
            active_look_channel_id_str = os.getenv("DISCORD_CHANNEL_ID") # Default channel
            if params.sources and isinstance(params.sources, list) and len(params.sources) > 0:
                potential_channel_id = params.sources[0].lstrip('#')
                if potential_channel_id.isdigit():
                    active_look_channel_id_str = potential_channel_id
            
            if not active_look_channel_id_str:
                self.logger.error(f"Active look channel ID not configured for thought {thought_id}.")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = "Active look failed: Channel ID not configured."
            # Check for io_adapter and if it's a DiscordAdapter (or has a 'client' attribute)
            elif not self.dependencies.io_adapter or not hasattr(self.dependencies.io_adapter, 'client') or not self.dependencies.io_adapter.client:
                self.logger.error(f"Discord client (via io_adapter) for active look unavailable for thought {thought_id}.")
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = "Active look failed: Discord client (via io_adapter) unavailable."
            else:
                # Assuming io_adapter is DiscordAdapter here for simplicity of access
                # A more robust way would be to check type or use a specific interface
                discord_client = self.dependencies.io_adapter.client
                try:
                    channel_id_int = int(active_look_channel_id_str)
                    target_channel = discord_client.get_channel(channel_id_int)
                    if not target_channel:
                        self.logger.error(f"Active look channel {active_look_channel_id_str} not found using io_adapter.client for thought {thought_id}.")
                        final_thought_status = ThoughtStatus.FAILED
                        follow_up_content_key_info = f"Active look failed: Channel {active_look_channel_id_str} not found."
                    else:
                        fetched_messages_data = [
                            {"id": str(m.id), "content": m.content, "author_id": str(m.author.id), "author_name": m.author.name, "timestamp": m.created_at.isoformat()}
                            async for m in target_channel.history(limit=10) # TODO: Make limit configurable?
                        ]
                        self.logger.info(f"Fetched {len(fetched_messages_data)} messages for active look on thought {thought_id}.")
                        
                        now_iso = datetime.now(timezone.utc).isoformat()
                        res_content = f"Active look from channel #{active_look_channel_id_str}: Found {len(fetched_messages_data)} messages. Review to determine next steps. If task complete, use TASK_COMPLETE."
                        if not fetched_messages_data:
                            res_content = f"Active look from channel #{active_look_channel_id_str}: No recent messages. Consider if task complete."
                        
                        active_look_result_thought = Thought(
                            thought_id=f"th_active_obs_{str(uuid.uuid4())[:8]}",
                            source_task_id=thought.source_task_id,
                            thought_type="active_observation_result",
                            status=ThoughtStatus.PENDING, # This new thought will be processed
                            created_at=now_iso,
                            updated_at=now_iso,
                            round_created=dispatch_context.get("current_round_number", thought.round_created + 1),
                            content=res_content,
                            processing_context={
                                "is_active_look_result": True,
                                "original_observe_thought_id": thought_id,
                                "source_observe_action_params": params.model_dump(mode="json"),
                                "fetched_messages_details": fetched_messages_data
                            },
                            priority=thought.priority # Inherit priority
                        )
                        persistence.add_thought(active_look_result_thought)
                        self.logger.info(f"Created active look result thought {active_look_result_thought.thought_id} for original thought {thought_id}.")
                        action_performed_successfully = True
                        follow_up_content_key_info = f"Active look on {params.sources} created result thought {active_look_result_thought.thought_id}."
                        # The original OBSERVE thought is now COMPLETED. The new result thought takes over.
                except ValueError:
                    self.logger.error(f"Invalid active look channel ID '{active_look_channel_id_str}' for thought {thought_id}.")
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = "Active look failed: Invalid channel ID format."
                except Exception as e_al:
                    self.logger.exception(f"Error during active look for thought {thought_id}: {e_al}")
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"Active look error: {str(e_al)}"
        else: # Passive observe
            action_performed_successfully = True
            follow_up_content_key_info = f"Passive observation initiated for sources: {params.sources}. System will monitor. Consider if task is complete."
            # For passive observe, the original thought is completed. No special result thought.

        persistence.update_thought_status(
            thought_id=thought_id,
            new_status=final_thought_status,
            final_action_result=result.model_dump(),
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after OBSERVE attempt.")

        # Create a follow-up thought ONLY if it's not an active look that successfully created its own result thought.
        # Or if any OBSERVE action failed.
        should_create_standard_follow_up = True
        if params and params.perform_active_look and action_performed_successfully:
            should_create_standard_follow_up = False # Active look created its own specific follow-up

        if final_thought_status == ThoughtStatus.FAILED: # Always create follow-up for failures
             should_create_standard_follow_up = True

        if should_create_standard_follow_up:
            follow_up_text = ""
            if action_performed_successfully: # This implies passive observe success
                follow_up_text = f"OBSERVE action ({'passive' if params else 'unknown type'}) for thought {thought_id} completed. Info: {follow_up_content_key_info}. Review if this completes the task or if further steps are needed."
            else: # Failed
                follow_up_text = f"OBSERVE action failed for thought {thought_id}. Reason: {follow_up_content_key_info}. Review and determine next steps."

            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=follow_up_text,
                priority_offset= 1 if action_performed_successfully else 0 # Higher if passive success, normal if fail
            )
            
            processing_ctx_for_follow_up = {"action_performed": HandlerActionType.OBSERVE.value}
            if final_thought_status == ThoughtStatus.FAILED:
                processing_ctx_for_follow_up["error_details"] = follow_up_content_key_info
            
            action_params_dump = result.action_parameters
            if isinstance(action_params_dump, BaseModel):
                action_params_dump = action_params_dump.model_dump(mode="json")
            processing_ctx_for_follow_up["action_params"] = action_params_dump
            
            new_follow_up.processing_context = processing_ctx_for_follow_up
            
            persistence.add_thought(new_follow_up)
            self.logger.info(f"Created standard follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after OBSERVE action.")
