import logging
from ciris_engine.utils.logging_config import setup_basic_logging
setup_basic_logging(level=logging.INFO)

import os
import asyncio
from typing import Optional

from ciris_engine.runtime.base_runtime import BaseRuntime, DiscordAdapter
from ciris_engine.core.ports import ActionSink
from ciris_engine.adapters.discord_event_source import DiscordEventSource
from ciris_engine.core.event_router import handle_observation_event
from ciris_engine.core import persistence
from ciris_engine.core.config_manager import get_config_async
from ciris_engine.core.agent_processor import AgentProcessor
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
import instructor # Added import for instructor.Mode
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.services.llm_service import LLMService
from ciris_engine.services.discord_graph_memory import DiscordGraphMemory, MemoryOpStatus # Import MemoryOpStatus
from ciris_engine.core.agent_core_schemas import (
    HandlerActionType,
    SpeakParams,
    DeferParams,
    RejectParams,
    MemorizeParams,
    RememberParams,
    ForgetParams,
    ActParams,
    ActionSelectionPDMAResult,
    ObserveParams,
    Thought,
)
from ciris_engine.core.foundational_schemas import ThoughtStatus, TaskStatus # Added TaskStatus
from pydantic import BaseModel
import uuid
from ciris_engine.utils.constants import DEFAULT_WA, WA_USER_ID
from ciris_engine.core.action_handlers.helpers import create_follow_up_thought
from datetime import datetime, timezone, timedelta # Added timedelta
import json # Added json for archiving
from pathlib import Path # Added Path for directory creation

logger = logging.getLogger(__name__)

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNORE_CHANNEL_ID = os.getenv("SNORE_CHANNEL_ID")
PROFILE_PATH = os.path.join("ciris_profiles", "teacher.yaml")


class DiscordActionSink(ActionSink):
    def __init__(self, runtime: BaseRuntime):
        self.runtime = runtime
    async def start(self) -> None: pass
    async def stop(self) -> None: pass
    async def send_message(self, channel_id: str, content: str) -> None:
        await self.runtime.io_adapter.send_output(channel_id, content)
    async def run_tool(self, tool_name: str, arguments: dict) -> None: return None

async def _discord_handler(runtime: BaseRuntime, sink: ActionSink, result: ActionSelectionPDMAResult, ctx: dict, services: dict) -> None:
    thought_id = ctx.get("thought_id")
    channel_id = ctx.get("channel_id")
    action = result.selected_handler_action
    params = result.action_parameters

    final_thought_status = ThoughtStatus.COMPLETED
    action_performed_successfully = False
    follow_up_content = ""

    try:
        if action == HandlerActionType.SPEAK:
            speak_content = None
            target_channel_id_from_params = None

            if isinstance(params, SpeakParams):
                speak_content = params.content
                target_channel_id_from_params = params.target_channel
            elif isinstance(params, dict): # Handle raw dict if Pydantic parsing failed
                speak_content = params.get("content")
                target_channel_id_from_params = params.get("target_channel")
            else:
                logger.error(f"DiscordHandler: SPEAK action params are neither SpeakParams nor dict. Type: {type(params)}. Thought ID: {thought_id}")
                final_thought_status = ThoughtStatus.FAILED # Mark as failed
                action_performed_successfully = False
                follow_up_content = f"SPEAK action failed: Invalid parameters type ({type(params)})."

            if final_thought_status != ThoughtStatus.FAILED: # Proceed only if params type was okay
                # Determine the channel to speak in. channel_id is from ctx.get("channel_id")
                final_channel_id_to_speak = target_channel_id_from_params or channel_id 
                
                if not final_channel_id_to_speak and SNORE_CHANNEL_ID:
                    logger.info(f"DiscordHandler: No target_channel in params or channel_id in context for SPEAK. Using SNORE_CHANNEL_ID: {SNORE_CHANNEL_ID}. Thought ID: {thought_id}")
                    final_channel_id_to_speak = SNORE_CHANNEL_ID

                if speak_content and final_channel_id_to_speak:
                    try:
                        # Ensure channel ID is just the number string
                        numeric_channel_id_str = str(final_channel_id_to_speak).lstrip('#')
                        await sink.send_message(numeric_channel_id_str, speak_content)
                        action_performed_successfully = True
                        follow_up_content = f"Spoke: '{str(speak_content)[:50]}...' in channel #{numeric_channel_id_str}"
                        # final_thought_status remains COMPLETED (default)
                    except Exception as send_ex:
                        logger.exception(f"DiscordHandler: Error sending SPEAK message to channel {final_channel_id_to_speak}. Thought ID: {thought_id}: {send_ex}")
                        final_thought_status = ThoughtStatus.FAILED
                        action_performed_successfully = False
                        follow_up_content = f"SPEAK action failed during send: {str(send_ex)}"
                else:
                    logger.error(f"DiscordHandler: SPEAK action failed. Content available: {speak_content is not None}, Channel determined: {final_channel_id_to_speak is not None}. Thought ID: {thought_id}")
                    final_thought_status = ThoughtStatus.FAILED
                    action_performed_successfully = False
                    if not speak_content:
                        follow_up_content = "SPEAK action failed: Missing content."
                    elif not final_channel_id_to_speak:
                        follow_up_content = "SPEAK action failed: Missing channel."
                    else:
                        follow_up_content = "SPEAK action failed: Unknown reason (missing content or channel)."
        elif action == HandlerActionType.DEFER and isinstance(params, DeferParams) and channel_id:
            await sink.send_message(channel_id, f"Deferred: {params.reason}")
            final_thought_status = ThoughtStatus.DEFERRED
            action_performed_successfully = True
            follow_up_content = f"Deferred thought. Reason: {params.reason}"
        elif action == HandlerActionType.REJECT and isinstance(params, RejectParams) and channel_id:
            await sink.send_message(channel_id, f"Unable to proceed. Reason: {params.reason}")
            action_performed_successfully = True
            follow_up_content = f"Rejected thought. Reason: {params.reason}"
        elif action == HandlerActionType.TOOL and isinstance(params, ActParams):
            await sink.run_tool(params.tool_name, params.arguments)
            action_performed_successfully = True
            follow_up_content = f"Executed tool: {params.tool_name} with args {params.arguments}."
        elif action == HandlerActionType.OBSERVE and isinstance(params, ObserveParams):
            logger.info(f"DiscordHandler: Handling OBSERVE action. Perform active look: {params.perform_active_look}")
            if params.perform_active_look:
                active_look_channel_id_str = os.getenv("DISCORD_CHANNEL_ID")
                if params.sources and isinstance(params.sources, list) and len(params.sources) > 0:
                    potential_channel_id = params.sources[0].lstrip('#')
                    if potential_channel_id.isdigit(): active_look_channel_id_str = potential_channel_id
                if not active_look_channel_id_str:
                    logger.error("DiscordHandler: Active look channel ID not configured."); final_thought_status = ThoughtStatus.FAILED; follow_up_content = "Active look failed: Channel ID not configured."; action_performed_successfully = False
                else:
                    try:
                        channel_id_int = int(active_look_channel_id_str)
                        if not hasattr(runtime.io_adapter, 'client') or not runtime.io_adapter.client:
                            logger.error("DiscordHandler: Discord client unavailable."); final_thought_status = ThoughtStatus.FAILED; follow_up_content = "Active look failed: Discord client unavailable."; action_performed_successfully = False
                        else:
                            target_channel = runtime.io_adapter.client.get_channel(channel_id_int)
                            if not target_channel:
                                logger.error(f"DiscordHandler: Channel {active_look_channel_id_str} not found."); final_thought_status = ThoughtStatus.FAILED; follow_up_content = f"Active look failed: Channel {active_look_channel_id_str} not found."; action_performed_successfully = False
                            else:
                                fetched_messages_data = [{"id": str(m.id), "content": m.content, "author_id": str(m.author.id), "author_name": m.author.name, "timestamp": m.created_at.isoformat()} async for m in target_channel.history(limit=10)]
                                logger.info(f"DiscordHandler: Fetched {len(fetched_messages_data)} messages for active look.")
                                original_thought_for_active_look = persistence.get_thought_by_id(thought_id)
                                if original_thought_for_active_look:
                                    now_iso = datetime.now(timezone.utc).isoformat()
                                    res_content = f"Active look from channel {active_look_channel_id_str}: Found {len(fetched_messages_data)} messages. Review to determine next steps. If task complete, use TASK_COMPLETE."
                                    if not fetched_messages_data: res_content = f"Active look from channel {active_look_channel_id_str}: No recent messages. Consider if task complete."
                                    res_thought = Thought(thought_id=f"th_active_obs_{str(uuid.uuid4())[:8]}", source_task_id=original_thought_for_active_look.source_task_id, thought_type="active_observation_result", status=ThoughtStatus.PENDING, created_at=now_iso, updated_at=now_iso, round_created=ctx.get("current_round_number", original_thought_for_active_look.round_created + 1), content=res_content, processing_context={"is_active_look_result": True, "original_observe_thought_id": thought_id, "source_observe_action_params": params.model_dump(mode="json"), "fetched_messages_details": fetched_messages_data}, priority=original_thought_for_active_look.priority)
                                    persistence.add_thought(res_thought)
                                    logger.info(f"DiscordHandler: Created result thought {res_thought.thought_id} for active look.")
                                    action_performed_successfully = True; follow_up_content = f"Active look on {params.sources} created result thought {res_thought.thought_id}."
                                else:
                                    logger.error(f"DiscordHandler: Original thought {thought_id} not found for active look."); final_thought_status = ThoughtStatus.FAILED; follow_up_content = "Active look failed: original thought missing."; action_performed_successfully = False
                    except ValueError: logger.error(f"DiscordHandler: Invalid active look channel ID '{active_look_channel_id_str}'."); final_thought_status = ThoughtStatus.FAILED; follow_up_content = "Active look failed: Invalid channel ID."; action_performed_successfully = False
                    except Exception as e_al: logger.exception(f"DiscordHandler: Error in active look: {e_al}"); final_thought_status = ThoughtStatus.FAILED; follow_up_content = f"Active look error: {e_al}"; action_performed_successfully = False
            else: # Passive observe
                action_performed_successfully = True
                follow_up_content = f"Passive observation initiated for sources: {params.sources}. System will monitor. Consider if task is complete."
        elif action == HandlerActionType.MEMORIZE and isinstance(params, MemorizeParams):
            logger.info(f"DiscordHandler: Handling MEMORIZE action for thought {thought_id}. Attempting to dispatch to 'memory' service.")
            original_thought_for_dispatch = persistence.get_thought_by_id(thought_id)

            if not original_thought_for_dispatch:
                logger.error(f"DiscordHandler: Cannot dispatch MEMORIZE for thought {thought_id}. Original thought not found.")
                # Let the main error handling of _discord_handler manage this failure.
                # Set status and content for the follow-up thought.
                final_thought_status = ThoughtStatus.FAILED
                action_performed_successfully = False # The dispatch action itself failed
                follow_up_content = f"Failed to dispatch MEMORIZE for thought {thought_id}: Original thought data not found."
                # Do NOT return here; allow the standard status update and follow-up creation to occur.
            else:
                memory_dispatch_ctx = ctx.copy()
                memory_dispatch_ctx["origin_service"] = "memory" # Set origin for the memory service call
                
                await runtime.dispatcher.dispatch(
                    action_selection_result=result,
                    thought=original_thought_for_dispatch,
                    dispatch_context=memory_dispatch_ctx,
                    services=services
                )
                # The dispatched 'memory' handler is now responsible for the lifecycle of this thought's MEMORIZE action.
                # So, _discord_handler should not create a follow-up or update status for this specific MEMORIZE action.
                return # Exit _discord_handler
        elif action == HandlerActionType.TASK_COMPLETE:
            logger.info(f"DiscordHandler: Handling TASK_COMPLETE for thought {thought_id}.")
            action_performed_successfully = True # The action of deciding to complete is successful
            final_thought_status = ThoughtStatus.COMPLETED # Current thought is completed
            follow_up_content = "Task marked as complete by agent."
            if thought_id:
                current_thought_for_task_complete = persistence.get_thought_by_id(thought_id)
                if current_thought_for_task_complete and current_thought_for_task_complete.source_task_id:
                    parent_task_id = current_thought_for_task_complete.source_task_id
                    logger.info(f"DiscordHandler: Marking parent task {parent_task_id} as COMPLETED due to TASK_COMPLETE action on thought {thought_id}.")
                    persistence.update_task_status(parent_task_id, TaskStatus.COMPLETED)
                else:
                    logger.error(f"DiscordHandler: Could not find parent task for thought {thought_id} to mark as complete.")
        else:
            logger.error("DiscordHandler: Unhandled action %s for thought %s", action.value, thought_id)
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content = f"Attempted unhandled action: {action.value}"

    except Exception as e:
        logger.exception(f"DiscordHandler: Error processing action {action.value} for thought {thought_id}: {e}")
        final_thought_status = ThoughtStatus.FAILED
        follow_up_content = f"Error during action {action.value}: {str(e)}"

    if thought_id:
        original_thought = persistence.get_thought_by_id(thought_id)
        if original_thought:
            try:
                persistence.update_thought_status(
                    thought_id=thought_id,
                    new_status=final_thought_status,
                    final_action_result=result.model_dump(),
                )
                logger.debug(f"DiscordHandler: Updated original thought {thought_id} to status {final_thought_status.value}")

                if action_performed_successfully or final_thought_status == ThoughtStatus.FAILED:
                    if action != HandlerActionType.TASK_COMPLETE: # TASK_COMPLETE is terminal, no standard follow-up from here
                        
                        current_follow_up_text = follow_up_content or f"Follow-up to {action.value} for thought {thought_id}"
                        if action == HandlerActionType.SPEAK and action_performed_successfully:
                            current_follow_up_text = f"Successfully spoke: '{params.content[:70]}...'. The original user request may now be addressed. Consider if any further memory operations or actions are needed. If the task is complete, the next action should be TASK_COMPLETE."
                        elif action_performed_successfully and \
                             not (action == HandlerActionType.OBSERVE and isinstance(params, ObserveParams) and params.perform_active_look and action_performed_successfully):
                            # Add general guidance for other successful actions, but not for active OBSERVE that creates its own result thought.
                            current_follow_up_text += " Review if this completes the task or if further steps (like TASK_COMPLETE) are needed."
                        
                        new_follow_up = create_follow_up_thought(
                            parent=original_thought,
                            content=current_follow_up_text
                        )
                        
                        processing_ctx_for_follow_up = {"action_performed": action.value}
                        if final_thought_status == ThoughtStatus.FAILED:
                            processing_ctx_for_follow_up["error_details"] = follow_up_content
                        
                        current_action_params = result.action_parameters # Already a Pydantic model or dict
                        if isinstance(current_action_params, BaseModel):
                            processing_ctx_for_follow_up["action_params"] = current_action_params.model_dump(mode="json")
                        else:
                            processing_ctx_for_follow_up["action_params"] = current_action_params
                        
                        new_follow_up.processing_context = processing_ctx_for_follow_up
                        
                        persistence.add_thought(new_follow_up)
                        logger.info(f"DiscordHandler: Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after action {action.value}")
            except Exception as db_error:
                logger.error(f"DiscordHandler: Failed to update thought {thought_id} status or create follow-up in DB: {db_error}")
        else:
            logger.error(f"DiscordHandler: Could not retrieve original thought {thought_id} for status update/follow-up.")

async def main() -> None:
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return

    persistence.initialize_database()
    await _startup_db_cleanup_and_log() # Call the new cleanup function

    from ciris_engine.runtime.base_runtime import IncomingMessage
    from ciris_engine.services.discord_event_queue import DiscordEventQueue
    discord_message_queue = DiscordEventQueue[IncomingMessage]()

    runtime = BaseRuntime(
        io_adapter=DiscordAdapter(TOKEN, message_queue=discord_message_queue),
        profile_path=PROFILE_PATH,
        snore_channel_id=SNORE_CHANNEL_ID,
    )

    discord_sink = DiscordActionSink(runtime)
    runtime.dispatcher.register_service_handler(
        "discord", lambda res, d_ctx: _discord_handler(runtime, discord_sink, res, d_ctx, services_dict)
    )

    app_config = await get_config_async()
    profile = await runtime._load_profile()

    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    memory_service = DiscordGraphMemory()
    
    from ciris_engine.services.discord_observer import DiscordObserver

    discord_observer = DiscordObserver(
        on_observe=handle_observation_event,
        message_queue=discord_message_queue,
        monitored_channel_id=os.getenv("DISCORD_CHANNEL_ID")
    )

    await llm_service.start()
    await memory_service.start()

    async def _get_user_nick_for_memory(params: MemorizeParams, ctx: dict, thought_id: Optional[str]) -> Optional[str]:
        user_nick: Optional[str] = None
        if isinstance(params.knowledge_data, dict):
            user_nick = params.knowledge_data.get("nick")
            if user_nick: return user_nick
            user_nick = params.knowledge_data.get("user_id")
            if user_nick: return user_nick
        user_nick = ctx.get("author_name")
        if user_nick: return user_nick
        if thought_id:
            try:
                current_thought = persistence.get_thought_by_id(thought_id)
                if current_thought and current_thought.source_task_id:
                    parent_task = persistence.get_task_by_id(current_thought.source_task_id)
                    if parent_task and isinstance(parent_task.context, dict):
                        user_nick = parent_task.context.get("author_name")
                        if user_nick: return user_nick
            except Exception as e_fetch: logger.error(f"Error fetching parent task for thought {thought_id}: {e_fetch}")
        logger.warning(f"Could not determine user_nick for thought {thought_id}.")
        return None

    async def _memory_handler(result: ActionSelectionPDMAResult, ctx: dict):
        thought_id = ctx.get("thought_id")
        action = result.selected_handler_action
        params = result.action_parameters
        final_thought_status = ThoughtStatus.COMPLETED
        try:
            if not isinstance(params, BaseModel):
                 logger.error(f"MemoryHandler: Params not BaseModel. Type: {type(params)}."); final_thought_status = ThoughtStatus.FAILED
            elif action == HandlerActionType.MEMORIZE and isinstance(params, MemorizeParams):
                user_nick = await _get_user_nick_for_memory(params, ctx, thought_id)
                channel = params.channel_metadata.get("channel") if isinstance(params.channel_metadata, dict) else ctx.get("channel_id")
                metadata = params.knowledge_data if isinstance(params.knowledge_data, dict) else {"data": str(params.knowledge_data)}
                if not user_nick or not channel:
                     logger.error(f"MemoryHandler: MEMORIZE missing user_nick/channel."); final_thought_status = ThoughtStatus.FAILED
                else:
                    mem_result = await memory_service.memorize(
                        user_nick=str(user_nick), channel=str(channel), metadata=metadata,
                        channel_metadata=params.channel_metadata, is_correction=ctx.get("is_wa_correction", False)
                    )
                    if mem_result.status != MemoryOpStatus.SAVED:
                        logger.error(f"MemoryHandler: MEMORIZE {mem_result.status.name}. Reason: {mem_result.reason}")
                        final_thought_status = ThoughtStatus.FAILED if mem_result.status == MemoryOpStatus.FAILED else ThoughtStatus.DEFERRED
            elif action == HandlerActionType.REMEMBER and isinstance(params, RememberParams):
                 logger.warning(f"MemoryHandler: REMEMBER action pending implementation.") 
            elif action == HandlerActionType.FORGET and isinstance(params, ForgetParams):
                 logger.warning(f"MemoryHandler: FORGET action pending implementation.") 
            else:
                logger.error(f"MemoryHandler: Unexpected action/params type: {action}/{type(params)}."); final_thought_status = ThoughtStatus.FAILED
        except Exception as e:
            logger.exception(f"MemoryHandler: Error processing {action.value}: {e}"); final_thought_status = ThoughtStatus.FAILED
        if thought_id:
            try:
                persistence.update_thought_status(thought_id, final_thought_status, final_action_result=result.model_dump())
                logger.debug(f"MemoryHandler: Updated original thought {thought_id} to status {final_thought_status.value}")

                if final_thought_status == ThoughtStatus.COMPLETED and action == HandlerActionType.MEMORIZE:
                    original_thought_for_follow_up = persistence.get_thought_by_id(thought_id)
                    if original_thought_for_follow_up:
                        follow_up_content_text = (
                            f"Memorization successful for original thought {thought_id} (Task: {original_thought_for_follow_up.source_task_id}). "
                            f"Knowledge: '{str(params.knowledge_data)[:70]}...'. "
                            "Consider informing the user with SPEAK or select TASK_COMPLETE if the overall task is finished."
                        )
                        new_follow_up = create_follow_up_thought(
                            parent=original_thought_for_follow_up,
                            content=follow_up_content_text
                        )
                        processing_ctx_for_follow_up = {
                            "action_performed": "MEMORIZE_SUCCESS",
                            "original_memorize_params": params.model_dump(mode="json") if isinstance(params, BaseModel) else params
                        }
                        new_follow_up.processing_context = processing_ctx_for_follow_up
                        persistence.add_thought(new_follow_up)
                        logger.info(f"MemoryHandler: Created follow-up thought {new_follow_up.thought_id} for successful MEMORIZE on {thought_id}")
                    else:
                        logger.error(f"MemoryHandler: Could not retrieve original thought {thought_id} to create MEMORIZE success follow-up.")
                elif final_thought_status == ThoughtStatus.FAILED:
                    # Potentially create a more specific "failed memory op" follow-up if needed
                    pass

            except Exception as db_error: logger.error(f"MemoryHandler: DB error for {thought_id}: {db_error}")

    runtime.dispatcher.register_service_handler("memory", _memory_handler)

    async def _observer_service_handler(runtime_ref: BaseRuntime, result: ActionSelectionPDMAResult, ctx: dict):
        logger.info(f"Generic _observer_service_handler: Received OBSERVE. Params: {result.action_parameters}")
        thought_id_for_status = ctx.get("thought_id")
        if thought_id_for_status:
            persistence.update_thought_status(thought_id_for_status, ThoughtStatus.COMPLETED, final_action_result=result.model_dump(mode="json"))
            original_thought = persistence.get_thought_by_id(thought_id_for_status)
            if original_thought:
                follow_up = create_follow_up_thought(original_thought, "Generic observer service processed OBSERVE action.")
                persistence.add_thought(follow_up)
        logger.warning("_observer_service_handler: Placeholder. Active Discord look is in _discord_handler.")

    runtime.dispatcher.register_service_handler("observer", lambda res, c: _observer_service_handler(runtime, res, c))

    llm_client = llm_service.get_client()
    ethical_pdma = EthicalPDMAEvaluator(
        aclient=llm_client.instruct_client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )
    csdma = CSDMAEvaluator(
        aclient=llm_client.client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries
    )
    action_pdma = ActionSelectionPDMAEvaluator(
        aclient=llm_client.client, model_name=llm_client.model_name,
        max_retries=app_config.llm_services.openai.max_retries,
        prompt_overrides=profile.action_selection_pdma_overrides,
        instructor_mode=instructor.Mode[app_config.llm_services.openai.instructor_mode.upper()]
    )
    guardrails = EthicalGuardrails(
        llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name
    )
    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client, ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma, action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails, app_config=app_config,
        dsdma_evaluators={}, memory_service=memory_service,
    )
    services_dict = {
        "llm_client": llm_service.get_client(), "memory_service": memory_service,
        "discord_service": runtime.io_adapter, "observer_service": discord_observer,
    }
    processor = AgentProcessor(
        app_config=app_config, workflow_coordinator=workflow_coordinator,
        action_dispatcher=runtime.dispatcher, services=services_dict,
        startup_channel_id=SNORE_CHANNEL_ID,
    )
    event_source = DiscordEventSource(discord_observer)

    async def main_loop():
        await event_source.start()
        await discord_sink.start()
        try:
            await asyncio.gather(runtime._main_loop(), processor.start_processing())
        finally:
            await discord_sink.stop()
            await event_source.stop()
    try:
        await main_loop()
    finally:
        await asyncio.gather(llm_service.stop(), memory_service.stop())

async def _startup_db_cleanup_and_log():
    """
    Performs database cleanup at startup:
    1. Removes orphaned active tasks and thoughts.
    2. Archives tasks and thoughts older than 24 hours.
    Logs actions taken.
    """
    logger.info("--- Starting Startup Database Cleanup ---")
    
    # --- 1. Remove orphaned active tasks and thoughts ---
    orphaned_tasks_deleted_count = 0
    orphaned_thoughts_deleted_count = 0

    # Check active tasks
    active_tasks = persistence.get_tasks_by_status(TaskStatus.ACTIVE)
    task_ids_to_delete = []
    valid_root_task_ids = {"WAKEUP_ROOT", "job-discord-monitor"} 

    for task in active_tasks:
        is_orphan = False
        if task.task_id in valid_root_task_ids and task.parent_goal_id is None:
            # These are allowed to be active root tasks initially
            pass
        elif task.parent_goal_id:
            parent_task = persistence.get_task_by_id(task.parent_goal_id)
            if not parent_task or parent_task.status not in [TaskStatus.ACTIVE, TaskStatus.COMPLETED]:
                is_orphan = True
        elif task.task_id not in valid_root_task_ids: # Non-root, non-wakeup/job task that is active
             logger.info(f"Task {task.task_id} ('{task.description[:30]}...') is active but not a recognized root task. Marking as orphaned for cleanup.")
             is_orphan = True


        if is_orphan:
            logger.info(f"Orphaned active task found: {task.task_id} ('{task.description[:30]}...'). Parent missing or not active/completed. Marking for deletion.")
            task_ids_to_delete.append(task.task_id)

    if task_ids_to_delete:
        # Deleting tasks will cascade delete their thoughts due to FOREIGN KEY ON DELETE CASCADE
        orphaned_tasks_deleted_count = persistence.delete_tasks_by_ids(task_ids_to_delete)
        logger.info(f"Deleted {orphaned_tasks_deleted_count} orphaned active tasks (and their thoughts).")

    # Check active/processing thoughts for tasks that might have been missed or are not active
    pending_thoughts_for_orphan_check = persistence.get_thoughts_by_status(ThoughtStatus.PENDING)
    processing_thoughts_for_orphan_check = persistence.get_thoughts_by_status(ThoughtStatus.PROCESSING)
    all_potentially_orphaned_thoughts = pending_thoughts_for_orphan_check + processing_thoughts_for_orphan_check
    thought_ids_to_delete = []

    for thought in all_potentially_orphaned_thoughts:
        source_task = persistence.get_task_by_id(thought.source_task_id)
        if not source_task or source_task.status != TaskStatus.ACTIVE:
            # If source task doesn't exist, or isn't active (and wasn't caught by task deletion cascade)
            logger.info(f"Orphaned thought found: {thought.thought_id} (Task: {thought.source_task_id} not found or not active). Marking for deletion.")
            thought_ids_to_delete.append(thought.thought_id)
    
    if thought_ids_to_delete:
        # Remove duplicates just in case, though task cascade should handle most
        unique_thought_ids_to_delete = list(set(thought_ids_to_delete))
        count = persistence.delete_thoughts_by_ids(unique_thought_ids_to_delete)
        orphaned_thoughts_deleted_count += count
        logger.info(f"Deleted {count} additional orphaned active/processing thoughts.")

    logger.info(f"Orphan cleanup: {orphaned_tasks_deleted_count} tasks, {orphaned_thoughts_deleted_count} thoughts removed.")

    # --- 2. Archive tasks/thoughts older than 24 hours ---
    archived_tasks_count = 0
    archived_thoughts_count = 0
    
    archive_dir = Path("data_archive")
    archive_dir.mkdir(parents=True, exist_ok=True)
    
    now = datetime.now(timezone.utc)
    archive_timestamp_str = now.strftime("%Y%m%d_%H%M%S")
    older_than_timestamp = (now - timedelta(hours=24)).isoformat()

    # Archive and delete old tasks
    tasks_to_archive = persistence.get_tasks_older_than(older_than_timestamp)
    if tasks_to_archive:
        task_archive_file = archive_dir / f"archive_tasks_{archive_timestamp_str}.jsonl"
        task_ids_to_delete_archive = []
        with open(task_archive_file, "w") as f:
            for task in tasks_to_archive:
                # Do not archive WAKEUP_ROOT or job-discord-monitor
                if task.task_id not in valid_root_task_ids:
                    f.write(task.model_dump_json() + "\n")
                    task_ids_to_delete_archive.append(task.task_id)
        
        if task_ids_to_delete_archive:
            archived_tasks_count = persistence.delete_tasks_by_ids(task_ids_to_delete_archive)
            logger.info(f"Archived and deleted {archived_tasks_count} tasks older than 24 hours to {task_archive_file}.")
        else:
            logger.info("No non-essential tasks older than 24 hours to archive.")
    else:
        logger.info("No tasks older than 24 hours found for archiving.")

    # Archive and delete old thoughts
    thoughts_to_archive = persistence.get_thoughts_older_than(older_than_timestamp)
    if thoughts_to_archive:
        thought_archive_file = archive_dir / f"archive_thoughts_{archive_timestamp_str}.jsonl"
        thought_ids_to_delete_archive = []
        
        # Filter out thoughts belonging to WAKEUP_ROOT or job-discord-monitor if those tasks were not archived
        # This avoids orphaning thoughts if their root tasks are preserved.
        # A simpler approach for now: if a thought's task was archived, it's fine. If not, keep the thought.
        # This means we only archive thoughts whose tasks were also eligible for archiving (and not special tasks).
        
        # Get IDs of tasks that were actually archived (or would have been if not special)
        archivable_task_ids = {t.task_id for t in tasks_to_archive if t.task_id not in valid_root_task_ids}

        with open(thought_archive_file, "w") as f:
            for thought in thoughts_to_archive:
                if thought.source_task_id in archivable_task_ids: # Only archive thoughts of archived tasks
                    f.write(thought.model_dump_json() + "\n")
                    thought_ids_to_delete_archive.append(thought.thought_id)
        
        if thought_ids_to_delete_archive:
            archived_thoughts_count = persistence.delete_thoughts_by_ids(thought_ids_to_delete_archive)
            logger.info(f"Archived and deleted {archived_thoughts_count} thoughts (linked to archived tasks) older than 24 hours to {thought_archive_file}.")
        else:
            logger.info("No thoughts (linked to archivable tasks) older than 24 hours to archive.")

    else:
        logger.info("No thoughts older than 24 hours found for archiving.")
    
    logger.info(f"Archival: {archived_tasks_count} tasks, {archived_thoughts_count} thoughts archived and removed.")
    logger.info("--- Finished Startup Database Cleanup ---")


if __name__ == "__main__":
    asyncio.run(main())
