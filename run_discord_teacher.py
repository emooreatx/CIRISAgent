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
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.services.llm_service import LLMService
from ciris_engine.services.discord_graph_memory import DiscordGraphMemory, MemoryOpStatus # Import MemoryOpStatus
from ciris_engine.core.agent_core_schemas import (
    HandlerActionType,
    SpeakParams,
    DeferParams,
    RejectParams,
    MemorizeParams,  # Keep MemorizeParams
    RememberParams,  # Keep RememberParams
    ForgetParams,  # Keep ForgetParams
    ActParams,
    ActionSelectionPDMAResult,
    ObserveParams,  # Added ObserveParams
    Thought,        # Added Thought
)
from ciris_engine.core.foundational_schemas import ThoughtStatus
from pydantic import BaseModel # Import BaseModel for type checking
import uuid # Added uuid import
from ciris_engine.utils.constants import DEFAULT_WA, WA_USER_ID

logger = logging.getLogger(__name__) # Get logger

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNORE_CHANNEL_ID = os.getenv("SNORE_CHANNEL_ID")
PROFILE_PATH = os.path.join("ciris_profiles", "teacher.yaml")


class DiscordActionSink(ActionSink):
    """Use the runtime adapter to send Discord actions."""

    def __init__(self, runtime: BaseRuntime):
        self.runtime = runtime

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(self, channel_id: str, content: str) -> None:
        await self.runtime.io_adapter.send_output(channel_id, content)

    async def run_tool(self, tool_name: str, arguments: dict) -> None:
        return None



async def _discord_handler(runtime: BaseRuntime, sink: ActionSink, result: ActionSelectionPDMAResult, ctx: dict) -> None:
    """Minimal handler forwarding actions through an ActionSink."""
    thought_id = ctx.get("thought_id")
    channel_id = ctx.get("channel_id")
    action = result.selected_handler_action
    params = result.action_parameters

    final_thought_status = ThoughtStatus.COMPLETED

    try:
        if action == HandlerActionType.SPEAK and isinstance(params, SpeakParams) and channel_id:
            await sink.send_message(channel_id, params.content)
        elif action == HandlerActionType.DEFER and isinstance(params, DeferParams) and channel_id:
            await sink.send_message(channel_id, f"Deferred: {params.reason}")
            final_thought_status = ThoughtStatus.DEFERRED
        elif action == HandlerActionType.REJECT and isinstance(params, RejectParams) and channel_id:
            await sink.send_message(channel_id, f"Unable to proceed. Reason: {params.reason}")
        elif action == HandlerActionType.TOOL and isinstance(params, ActParams):
            await sink.run_tool(params.tool_name, params.arguments)
        else:
            logger.error("DiscordHandler: Unhandled action %s", action.value)
            final_thought_status = ThoughtStatus.FAILED
    except Exception as e:
        logger.exception(
            "DiscordHandler: Error processing action %s for thought %s: %s", action.value, thought_id, e
        )
        final_thought_status = ThoughtStatus.FAILED

    if thought_id:
        try:
            persistence.update_thought_status(
                thought_id=thought_id,

                new_status=final_thought_status,
                final_action_result=result.model_dump(),
            )
        except Exception as db_error:
            logger.error(
                "DiscordHandler: Failed to update thought %s status to %s in DB: %s",
                thought_id,
                final_thought_status.value,
                db_error,
            )
async def main() -> None:
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return

    persistence.initialize_database()

    # Import IncomingMessage and the generic DiscordEventQueue
    from ciris_engine.runtime.base_runtime import IncomingMessage
    from ciris_engine.services.discord_event_queue import DiscordEventQueue

    # Create the typed DiscordEventQueue for IncomingMessage objects
    discord_message_queue = DiscordEventQueue[IncomingMessage]()

    runtime = BaseRuntime(
        io_adapter=DiscordAdapter(TOKEN, message_queue=discord_message_queue),
        profile_path=PROFILE_PATH,
        snore_channel_id=SNORE_CHANNEL_ID,
    )

    discord_sink = DiscordActionSink(runtime)
    runtime.dispatcher.register_service_handler(
        "discord", lambda result, ctx: _discord_handler(runtime, discord_sink, result, ctx)
    )

    app_config = await get_config_async()
    profile = await runtime._load_profile()

    # Ensure the loaded profile is available to the workflow coordinator.
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    # Instantiate DiscordGraphMemory - this is the actual memory service
    memory_service = DiscordGraphMemory()
    
    # Instantiate DiscordObserver and wire it to the transport-agnostic router
    from ciris_engine.services.discord_observer import DiscordObserver
    from datetime import datetime, timezone  # Ensure datetime and timezone are imported if not already

    discord_observer = DiscordObserver(
        on_observe=handle_observation_event,
        message_queue=discord_message_queue, # The same queue used by DiscordAdapter
        monitored_channel_id=os.getenv("DISCORD_CHANNEL_ID") # Optional: if you want to monitor a specific channel
    )

    # Start services
    await llm_service.start()
    await memory_service.start()

    # --- Helper function to retrieve user_nick for memory operations ---
    async def _get_user_nick_for_memory(params: MemorizeParams, ctx: dict, thought_id: Optional[str]) -> Optional[str]:
        """
        Retrieves the user_nick for a memory operation by checking:
        1. params.knowledge_data['nick']
        2. params.knowledge_data['user_id']
        3. ctx['author_name']
        4. Parent task's context via persistence lookup if thought_id is available.
        """
        user_nick: Optional[str] = None
        # 1. Try to get 'nick' or 'user_id' from knowledge_data in params
        if isinstance(params.knowledge_data, dict):
            user_nick = params.knowledge_data.get("nick")
            if user_nick:
                logger.debug(f"_get_user_nick_for_memory: Found user_nick '{user_nick}' in MemorizeParams.knowledge_data.nick for thought {thought_id}.")
                return user_nick
            
            user_nick = params.knowledge_data.get("user_id")
            if user_nick:
                logger.debug(f"_get_user_nick_for_memory: Found user_nick '{user_nick}' (from user_id) in MemorizeParams.knowledge_data.user_id for thought {thought_id}.")
                return user_nick

        # 2. If not found, try to get 'author_name' from the thought's direct context (ctx)
        user_nick = ctx.get("author_name")
        if user_nick:
            logger.debug(f"_get_user_nick_for_memory: Found user_nick '{user_nick}' in thought context (ctx.author_name) for thought {thought_id}.")
            return user_nick

        # 3. If still not found, and thought_id is available, try to get from parent task's context
        if thought_id:
            logger.debug(f"_get_user_nick_for_memory: user_nick not in params or thought context for {thought_id}. Attempting to fetch from parent task.")
            try:
                current_thought = persistence.get_thought_by_id(thought_id)
                if current_thought and current_thought.source_task_id:
                    parent_task = persistence.get_task_by_id(current_thought.source_task_id)
                    if parent_task and isinstance(parent_task.context, dict):
                        user_nick = parent_task.context.get("author_name")
                        if user_nick:
                            logger.info(f"_get_user_nick_for_memory: Fetched user_nick '{user_nick}' from parent task '{current_thought.source_task_id}' context.author_name for thought {thought_id}.")
                            return user_nick
                        else:
                            logger.warning(f"_get_user_nick_for_memory: Parent task '{current_thought.source_task_id}' context for thought {thought_id} does not contain 'author_name'. Task context: {parent_task.context}")
                    elif parent_task:
                        logger.warning(f"_get_user_nick_for_memory: Parent task '{current_thought.source_task_id}' for thought {thought_id} has no context or context is not a dict. Task context type: {type(parent_task.context)}")
                    else:
                        logger.warning(f"_get_user_nick_for_memory: Parent task '{current_thought.source_task_id}' not found for thought {thought_id}.")
                elif current_thought:
                    logger.warning(f"_get_user_nick_for_memory: Thought {thought_id} found but has no source_task_id.")
                else:
                    logger.warning(f"_get_user_nick_for_memory: Thought {thought_id} not found in persistence for user_nick retrieval.")
            except Exception as e_fetch:
                logger.error(f"_get_user_nick_for_memory: Error fetching parent task details for thought {thought_id}: {e_fetch}")
        
        if not user_nick:
            logger.warning(f"_get_user_nick_for_memory: Could not determine user_nick for thought {thought_id} after all fallbacks.")
        return user_nick

    # --- Dedicated Handler for Memory Actions ---
    async def _memory_handler(result: ActionSelectionPDMAResult, ctx: dict): # Added type hints
        thought_id = ctx.get("thought_id")
        action = result.selected_handler_action
        params = result.action_parameters # This should be a validated Pydantic model

        final_thought_status = ThoughtStatus.COMPLETED # Default status

        try:
            # Ensure params is a Pydantic model before type checking against Param classes
            if not isinstance(params, BaseModel):
                 logger.error(f"MemoryHandler: Received action '{action.value}' for thought {thought_id} with parameters not as BaseModel. Type: {type(params)}. Cannot process memory operation.")
                 final_thought_status = ThoughtStatus.FAILED # Mark as failed

            elif action == HandlerActionType.MEMORIZE and isinstance(params, MemorizeParams):
                user_nick = await _get_user_nick_for_memory(params, ctx, thought_id)
                
                # Extract other necessary data
                channel = params.channel_metadata.get("channel") if isinstance(params.channel_metadata, dict) else ctx.get("channel_id")
                
                # Ensure metadata is a dictionary. If knowledge_data is not a dict (e.g. a string), wrap it.
                if isinstance(params.knowledge_data, dict):
                    metadata = params.knowledge_data
                else:
                    metadata = {"data": str(params.knowledge_data)} # Convert to string to be safe

                if not user_nick or not channel:
                     logger.error(f"MemoryHandler: MEMORIZE action for thought {thought_id} is missing required user_nick ('{user_nick}') or channel ('{channel}') after all fallbacks. Cannot perform memory operation.")
                     final_thought_status = ThoughtStatus.FAILED # Mark as failed
                else:
                     # Call the actual memory service method
                    mem_result = await memory_service.memorize(
                        user_nick=str(user_nick), # Ensure user_nick is a string
                        channel=str(channel),     # Ensure channel is a string
                        metadata=metadata, # Pass the extracted/formatted metadata
                        channel_metadata=params.channel_metadata,
                        is_correction=ctx.get("is_wa_correction", False) # Pass correction flag if applicable
                    )
                    if mem_result.status == MemoryOpStatus.SAVED:
                        logger.info(f"MemoryHandler: Successfully MEMORIZED data for thought {thought_id}.")
                        final_thought_status = ThoughtStatus.COMPLETED # Explicitly set to completed on success
                    elif mem_result.status == MemoryOpStatus.DEFERRED:
                        logger.info(f"MemoryHandler: MEMORIZE deferred for thought {thought_id}. Reason: {mem_result.reason}")
                        final_thought_status = ThoughtStatus.DEFERRED # Mark thought as deferred
                        # The DEFERRAL_PACKAGE_CONTENT should be handled by the ActionDispatcher
                        # when the DEFER action is selected by the ASPDMA due to memory service deferral.
                        # This handler should just report the deferral status.
                    elif mem_result.status == MemoryOpStatus.FAILED:
                         logger.error(f"MemoryHandler: MEMORIZE FAILED for thought {thought_id}. Reason: {mem_result.reason}")
                         final_thought_status = ThoughtStatus.FAILED # Mark thought as failed


            elif action == HandlerActionType.REMEMBER and isinstance(params, RememberParams):
                 # Implement REMEMBER logic here
                 logger.warning(f"MemoryHandler: REMEMBER action received for thought {thought_id}. Implementation pending.")
                 # Example:
                 user_nick_for_query = ctx.get("author_name") # Or derive from params if available/different
                 if not user_nick_for_query and params.query: # Fallback if query itself might be a user identifier
                     # This part is speculative, depends on how params.query is used.
                     # For now, assume query is a general query string, and user context is from ctx.
                     pass

                 if not user_nick_for_query: # If still no user_nick, REMEMBER might be for general knowledge
                     logger.warning(f"MemoryHandler: REMEMBER action for thought {thought_id} has no user_nick in context. Query: {params.query}")
                     # Proceed with a general query if memory_service supports it, or handle as error.
                     # For now, let's assume memory_service.remember can take a general query string.
                 
                 # For this example, let's assume params.query is the user_nick if not otherwise specified.
                 # A better approach would be a dedicated user_nick field in RememberParams.
                 query_target_user = params.query # Simplified assumption for now.
                 
                 remembered_data = await memory_service.remember(user_nick=query_target_user) # Pass user_nick

                 if remembered_data:
                     logger.info(f"MemoryHandler: REMEMBERED data for thought {thought_id} for user '{query_target_user}'. Data: {remembered_data}")
                     
                     # Create a new thought to process the remembered data
                     now_iso = datetime.now(timezone.utc).isoformat()
                     new_thought_id = f"th_remember_followup_{str(uuid.uuid4())[:8]}"
                     parent_task_id = ctx.get("source_task_id", "unknown_remember_task")

                     follow_up_thought = Thought(
                         thought_id=new_thought_id,
                         source_task_id=parent_task_id,
                         thought_type="remember_result_processing",
                         status=ThoughtStatus.PENDING,
                         created_at=now_iso,
                         updated_at=now_iso,
                         round_created=ctx.get("current_round_number", 0), # Get current round if available
                         content=f"Process remembered data for user '{query_target_user}'. Original query: '{params.query}'.",
                         processing_context={
                             "is_remember_follow_up": True,
                             "original_remember_thought_id": thought_id,
                             "remembered_data": remembered_data,
                             "original_query": params.query,
                             "queried_user_nick": query_target_user
                         },
                         priority=ctx.get("priority", 1) 
                     )
                     try:
                         persistence.add_thought(follow_up_thought)
                         logger.info(f"MemoryHandler: Created new thought {new_thought_id} to process remembered data.")
                         final_thought_status = ThoughtStatus.COMPLETED 
                     except Exception as e_add_thought:
                         logger.exception(f"MemoryHandler: Failed to add follow-up thought for REMEMBER: {e_add_thought}")
                         final_thought_status = ThoughtStatus.FAILED # Original REMEMBER thought failed
                 else:
                     logger.info(f"MemoryHandler: REMEMBER query for thought {thought_id} (user: '{query_target_user}') found no data.")
                     final_thought_status = ThoughtStatus.COMPLETED # REMEMBER action completed, found nothing.
                 
            elif action == HandlerActionType.FORGET and isinstance(params, ForgetParams):
                 # Implement FORGET logic here
                 logger.warning(f"MemoryHandler: FORGET action received for thought {thought_id}. Implementation pending.")
                 # Example:
                 # if params.item_description:
                 #     await memory_service.forget(params.item_description)
                 #     logger.info(f"MemoryHandler: FORGET action completed for thought {thought_id}.")
                 final_thought_status = ThoughtStatus.COMPLETED # Assume completed once forget is attempted

            else:
                # Catch cases where params is a BaseModel but not one of the expected memory ParamModels
                logger.error(f"MemoryHandler: Received action '{action.value}' for thought {thought_id} with unexpected parameter model type: {type(params).__name__}. Cannot process memory operation.")
                final_thought_status = ThoughtStatus.FAILED # Mark as failed

        except Exception as e:
            logger.exception(f"MemoryHandler: Unexpected error processing action {action.value} for thought {thought_id}: {e}")
            final_thought_status = ThoughtStatus.FAILED # Mark as failed on exception

        # Always update thought status after attempting to handle the action
        if thought_id:
            try:
                persistence.update_thought_status(
                    thought_id=thought_id,
                    new_status=final_thought_status,
                     # Store the final ActionSelectionPDMAResult regardless of success/failure
                    final_action_result=result.model_dump()
                )
                logger.debug(f"MemoryHandler: Updated thought {thought_id} status to {final_thought_status.value}.")
            except Exception as db_error:
                logger.error(f"MemoryHandler: Failed to update thought {thought_id} status to {final_thought_status.value} in DB: {db_error}")

    # Register the dedicated handler for Memory actions
    runtime.dispatcher.register_service_handler(
        "memory", lambda result, ctx: _memory_handler(result, ctx)
    )

    # --- Dedicated Handler for Observe Actions ---
    async def _observer_handler(runtime_ref: BaseRuntime, result: ActionSelectionPDMAResult, ctx: dict):
        logger.info(f"ObserverHandler: Received OBSERVE action. Params: {result.action_parameters}")
        
        # action_parameters should be ObserveParams, already asserted by ActionSelectionPDMA's parsing
        # but an explicit check here is good practice if this handler could be called from elsewhere.
        if not isinstance(result.action_parameters, ObserveParams):
            logger.error(f"ObserverHandler: Incorrect parameters type for OBSERVE action. Expected ObserveParams, got {type(result.action_parameters)}")
            if ctx.get("thought_id"):
                try:
                    persistence.update_thought_status(
                        thought_id=ctx.get("thought_id"),
                        new_status=ThoughtStatus.FAILED,
                        final_action_result={"error": "Incorrect params for OBSERVE in handler"}
                    )
                except Exception as e_db:
                    logger.error(f"ObserverHandler: DB error updating thought status to FAILED: {e_db}")
            return

        params: ObserveParams = result.action_parameters

        if params.perform_active_look:
            thought_id_for_status = ctx.get("thought_id") # For updating status of the OBSERVE thought
            logger.info(f"ObserverHandler: Performing active look for thought {thought_id_for_status}.")
            active_look_channel_id_str = os.getenv("DISCORD_CHANNEL_ID")

            if not active_look_channel_id_str:
                logger.error("ObserverHandler: DISCORD_CHANNEL_ID environment variable not set. Cannot perform active look.")
                if thought_id_for_status:
                    persistence.update_thought_status(thought_id_for_status, ThoughtStatus.FAILED, final_action_result={"error": "DISCORD_CHANNEL_ID not set"})
                return

            try:
                channel_id_int = int(active_look_channel_id_str)
                if not hasattr(runtime_ref.io_adapter, 'client') or not runtime_ref.io_adapter.client:
                    logger.error("ObserverHandler: Discord client not available on io_adapter.")
                    if thought_id_for_status:
                         persistence.update_thought_status(thought_id_for_status, ThoughtStatus.FAILED, final_action_result={"error": "Discord client unavailable"})
                    return

                target_channel = runtime_ref.io_adapter.client.get_channel(channel_id_int)
                if not target_channel:
                    logger.error(f"ObserverHandler: Could not find channel with ID {active_look_channel_id_str} for active look.")
                    if thought_id_for_status:
                         persistence.update_thought_status(thought_id_for_status, ThoughtStatus.FAILED, final_action_result={"error": f"Channel {active_look_channel_id_str} not found"})
                    return

                fetched_messages_data = []
                async for msg in target_channel.history(limit=10):
                    fetched_messages_data.append({
                        "id": str(msg.id),
                        "content": msg.content,
                        "author_id": str(msg.author.id),
                        "author_name": msg.author.name,
                        "timestamp": msg.created_at.isoformat()
                    })
                
                logger.info(f"ObserverHandler: Fetched {len(fetched_messages_data)} messages from channel {active_look_channel_id_str}.")
                
                now_iso = datetime.now(timezone.utc).isoformat()
                source_task_id = ctx.get("source_task_id", "unknown_active_look_task")
                
                summary_content = f"Active look observation from channel {active_look_channel_id_str}: Found {len(fetched_messages_data)} messages."
                if not fetched_messages_data:
                    summary_content = f"Active look observation from channel {active_look_channel_id_str}: No recent messages found."

                new_thought_id = f"th_active_obs_{str(uuid.uuid4())[:8]}"
                
                active_look_thought = Thought(
                    thought_id=new_thought_id,
                    source_task_id=source_task_id, # Associate with the task of the OBSERVE thought
                    thought_type="active_observation_result",
                    status=ThoughtStatus.PENDING,
                    created_at=now_iso,
                    updated_at=now_iso,
                    round_created=ctx.get("current_round_number", 0), 
                    content=summary_content,
                    processing_context={
                        "is_active_look_result": True,
                        "original_observe_thought_id": thought_id_for_status, # Link back to the OBSERVE thought
                        "source_observe_action_params": params.model_dump(mode="json"),
                        "fetched_messages_details": fetched_messages_data 
                    },
                    priority=ctx.get("priority", 1) 
                )
                persistence.add_thought(active_look_thought)
                logger.info(f"ObserverHandler: Created new thought {new_thought_id} for active look results.")
                
                # Mark the original OBSERVE thought as completed since its action (active look) is done.
                if thought_id_for_status:
                    persistence.update_thought_status(
                        thought_id=thought_id_for_status,
                        new_status=ThoughtStatus.COMPLETED,
                        final_action_result=result.model_dump(mode="json") # Store the ObserveParams
                    )

            except ValueError:
                logger.error(f"ObserverHandler: DISCORD_CHANNEL_ID '{active_look_channel_id_str}' is not a valid integer.")
                if thought_id_for_status:
                    persistence.update_thought_status(thought_id_for_status, ThoughtStatus.FAILED, final_action_result={"error": "Invalid DISCORD_CHANNEL_ID format"})
            except Exception as e:
                logger.exception(f"ObserverHandler: Error during active look: {e}")
                if thought_id_for_status:
                    persistence.update_thought_status(thought_id_for_status, ThoughtStatus.FAILED, final_action_result={"error": f"Exception during active_look: {str(e)}"})
        else:
            logger.info(f"ObserverHandler: OBSERVE action is passive for thought {ctx.get('thought_id')}. No active look performed by this handler.")
            # Passive observation is handled by DiscordObserver pushing to the queue.
            # Mark the OBSERVE thought as completed.
            if ctx.get("thought_id"):
                persistence.update_thought_status(
                    thought_id=ctx.get("thought_id"),
                    new_status=ThoughtStatus.COMPLETED,
                    final_action_result=result.model_dump(mode="json") # Store the ObserveParams
                )

    # Register the dedicated handler for Observe actions
    runtime.dispatcher.register_service_handler(
        "observer", lambda res_lambda, ctx_lambda: _observer_handler(runtime, res_lambda, ctx_lambda)
    )

    llm_client = llm_service.get_client()
    # Pass the instructor-patched client to PDMA and Guardrails that use it
    ethical_pdma = EthicalPDMAEvaluator(llm_client.instruct_client, model_name=llm_client.model_name) # type: ignore
    # CSDMA uses the raw client
    csdma = CSDMAEvaluator(llm_client.client, model_name=llm_client.model_name) # type: ignore
    # ActionSelectionPDMA uses the raw client and patches internally with the configured mode
    action_pdma = ActionSelectionPDMAEvaluator(
        llm_client.client, # type: ignore
        model_name=llm_client.model_name, # type: ignore
        prompt_overrides=profile.action_selection_pdma_overrides,
        # instructor_mode is read from config by ActionSelectionPDMAEvaluator itself
    )

    guardrails = EthicalGuardrails(
        llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name # type: ignore
    )

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client, # type: ignore # WorkflowCoordinator still gets the raw client? Check WorkflowCoordinator __init__ - yes, expects CIRISLLMClient but uses llm_client.client
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails,
        app_config=app_config,
        dsdma_evaluators={}, # DSDMA evaluators would be added here if profile specified them
        memory_service=memory_service,
    )

    processor = AgentProcessor(
        app_config=app_config,
        workflow_coordinator=workflow_coordinator,
        action_dispatcher=runtime.dispatcher,
        startup_channel_id=SNORE_CHANNEL_ID,
    )

    event_source = DiscordEventSource(discord_observer)

    async def main_loop():
        await event_source.start()
        await discord_sink.start()
        try:
            await asyncio.gather(
                runtime._main_loop(),
                processor.start_processing(),
            )
        finally:
            await discord_sink.stop()
            await event_source.stop()

    try:
        await main_loop()
    finally:
        await asyncio.gather(
            llm_service.stop(),
            memory_service.stop(),
        )


if __name__ == "__main__":
    asyncio.run(main())
