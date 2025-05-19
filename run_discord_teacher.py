import os
import asyncio
import logging # Import logging

from ciris_engine.runtime.base_runtime import BaseRuntime, DiscordAdapter
from ciris_engine.utils.logging_config import setup_basic_logging
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
)
from ciris_engine.core.foundational_schemas import ThoughtStatus
from pydantic import BaseModel # Import BaseModel for type checking
from ciris_engine.utils.constants import DEFAULT_WA, WA_USER_ID

logger = logging.getLogger(__name__) # Get logger

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNORE_CHANNEL_ID = os.getenv("SNORE_CHANNEL_ID")
PROFILE_PATH = os.path.join("ciris_profiles", "teacher.yaml")


async def _discord_handler(runtime: BaseRuntime, result: ActionSelectionPDMAResult, ctx: dict): # Added type hints
    """Minimal handler to send outputs via the runtime's adapter."""
    thought_id = ctx.get("thought_id")
    channel_id = ctx.get("channel_id")
    action = result.selected_handler_action
    params = result.action_parameters # This should now be a Pydantic model or a dict if no ParamModel

    # Use a more general status update at the end, after attempting the action
    final_thought_status = ThoughtStatus.COMPLETED # Default to completed if action is handled

    try:
        if action == HandlerActionType.SPEAK and isinstance(params, SpeakParams):
            if channel_id:
                # Attempt to reply if original message ID is available in context
                original_message_id = ctx.get("message_id")
                if original_message_id:
                     try:
                         target_channel = runtime.io_adapter.client.get_channel(int(channel_id)) # Assuming adapter.client is discord.Client
                         if target_channel:
                              original_message = await target_channel.fetch_message(int(original_message_id))
                              await original_message.reply(params.content)
                              logger.info(f"DiscordHandler: Replied SPEAK message to message {original_message_id} in channel {channel_id} for thought {thought_id}.")
                         else:
                              logger.warning(f"DiscordHandler: Could not find channel {channel_id} to send SPEAK reply for thought {thought_id}.")
                              await runtime.io_adapter.send_output(channel_id, params.content) # Fallback
                     except Exception as reply_error:
                          logger.error(f"DiscordHandler: Error sending SPEAK reply for thought {thought_id}: {reply_error}. Sending to channel instead.")
                          await runtime.io_adapter.send_output(channel_id, params.content) # Fallback
                else:
                    # If no original message ID, just send to the channel
                    await runtime.io_adapter.send_output(channel_id, params.content)
                    logger.info(f"DiscordHandler: Sent SPEAK message to channel {channel_id} for thought {thought_id} (no reply).")
            else:
                logger.warning(f"DiscordHandler: SPEAK action for thought {thought_id} has no channel_id in context. Message not sent.")

        elif action == HandlerActionType.DEFER and isinstance(params, DeferParams):
            if channel_id:
                content = (
                    f"\U0001f6d1 Deferred update: {params.reason}\n"
                    f"<@{WA_USER_ID}> please approve with \u2714 or reject with \u2716."
                )
                # Attempt to reply if original message ID is available in context
                original_message_id = ctx.get("message_id")
                if original_message_id:
                    try:
                        target_channel = runtime.io_adapter.client.get_channel(int(channel_id))  # Assuming adapter.client is discord.Client
                        if target_channel:
                            original_message = await target_channel.fetch_message(int(original_message_id))
                            await original_message.reply(content)
                            logger.info(
                                f"DiscordHandler: Replied DEFER notification to message {original_message_id} in channel {channel_id} for thought {thought_id}."
                            )
                        else:
                            logger.warning(
                                f"DiscordHandler: Could not find channel {channel_id} to send DEFER reply for thought {thought_id}."
                            )
                            await runtime.io_adapter.send_output(channel_id, content)  # Fallback
                    except Exception as reply_error:
                        logger.error(
                            f"DiscordHandler: Error sending DEFER reply for thought {thought_id}: {reply_error}. Sending to channel instead."
                        )
                        await runtime.io_adapter.send_output(channel_id, content)  # Fallback
                else:
                    # If no original message ID, just send to the channel
                    await runtime.io_adapter.send_output(channel_id, content)
                    logger.info(f"DiscordHandler: Sent DEFER notification to channel {channel_id} for thought {thought_id} (no reply).")

                # Deferral report logic (often to a separate deferral channel) could go here if needed
                # For this minimal handler, we just send the user-facing message.
                final_thought_status = ThoughtStatus.DEFERRED # Explicitly mark thought as deferred

            elif action == HandlerActionType.REJECT and isinstance(params, RejectParams):
                if channel_id:
                    rejection_message = f"Unable to proceed with this request. Reason: {params.reason}"
                     # Attempt to reply if original message ID is available in context
                    original_message_id = ctx.get("message_id")
                    if original_message_id:
                         try:
                             target_channel = runtime.io_adapter.client.get_channel(int(channel_id))
                             if target_channel:
                                 original_message = await target_channel.fetch_message(int(original_message_id))
                                 await original_message.reply(rejection_message)
                                 logger.info(f"DiscordHandler: Replied REJECT message to message {original_message_id} in channel {channel_id} for thought {thought_id}.")
                             else:
                                 logger.warning(f"DiscordHandler: Could not find channel {channel_id} to send REJECT reply for thought {thought_id}.")
                                 await runtime.io_adapter.send_output(channel_id, rejection_message) # Fallback
                         except Exception as reply_error:
                              logger.error(f"DiscordHandler: Error sending REJECT reply for thought {thought_id}: {reply_error}. Sending to channel instead.")
                              await runtime.io_adapter.send_output(channel_id, rejection_message) # Fallback
                    else:
                         await runtime.io_adapter.send_output(channel_id, rejection_message)
                         logger.info(f"DiscordHandler: Sent REJECT message to channel {channel_id} for thought {thought_id} (no reply).")


            elif action == HandlerActionType.ACT and isinstance(params, ActParams):
                 # This handler doesn't implement ACT, so log it and potentially handle in a dedicated ACT handler
                 logger.warning(f"DiscordHandler: Received ACT action '{params.tool_name}' for thought {thought_id}. No specific DiscordHandler implementation.")
                 # The ActionDispatcher's main logic might handle ACT based on origin_service,
                 # so this warning might mean the dispatcher logic needs refinement too.
                 # For now, just log and let the thought be marked completed below.

            # --- Memory Actions ---
            # These should ideally be handled by the 'memory' service handler.
            # If they somehow arrive here due to a routing issue, log an error.
            elif action in [HandlerActionType.MEMORIZE, HandlerActionType.REMEMBER, HandlerActionType.FORGET]:
                 logger.error(f"DiscordHandler: Received a Memory Action ({action.value}) for thought {thought_id}. This should be routed to the 'memory' service handler. Possible ActionDispatcher routing issue.")
                 final_thought_status = ThoughtStatus.FAILED # Mark as failed because it wasn't handled correctly

            else:
                # Catch any other unexpected action types reaching this handler
                logger.error(f"DiscordHandler: Received unhandled action type '{action.value}' for thought {thought_id}. Parameters: {params}")
                final_thought_status = ThoughtStatus.FAILED # Mark as failed

    except Exception as e:
        logger.exception(f"DiscordHandler: Unexpected error processing action {action.value} for thought {thought_id}: {e}")
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
            logger.debug(f"DiscordHandler: Updated thought {thought_id} status to {final_thought_status.value}.")
        except Exception as db_error:
            logger.error(f"DiscordHandler: Failed to update thought {thought_id} status to {final_thought_status.value} in DB: {db_error}")


async def main() -> None:
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return

    setup_basic_logging()
    persistence.initialize_database()

    runtime = BaseRuntime(
        io_adapter=DiscordAdapter(TOKEN), # This adapter will fetch messages
        profile_path=PROFILE_PATH,
        snore_channel_id=SNORE_CHANNEL_ID,
    )

    # Register the handler for Discord-specific actions
    runtime.dispatcher.register_service_handler(
        "discord", lambda result, ctx: _discord_handler(runtime, result, ctx)
    )

    app_config = await get_config_async()
    profile = await runtime._load_profile()

    # Ensure the loaded profile is available to the workflow coordinator.
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    # Instantiate DiscordGraphMemory - this is the actual memory service
    memory_service = DiscordGraphMemory()
    await llm_service.start()
    await memory_service.start()

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
                # Extract data from the VALIDATED MemorizeParams
                # Fallbacks to ctx if data not found in params
                user_nick = params.knowledge_data.get("nick") if isinstance(params.knowledge_data, dict) else (ctx.get("author_name") if ctx.get("author_name") != DEFAULT_WA else None) # Use author_name from context as fallback, but not default WA
                channel = params.channel_metadata.get("channel") if isinstance(params.channel_metadata, dict) else ctx.get("channel_id") # Use channel_id from context as fallback
                metadata = params.knowledge_data if isinstance(params.knowledge_data, dict) else {"data": params.knowledge_data} # Use knowledge_data as metadata or wrap string

                if not user_nick or not channel: # Memory service requires user_nick and channel for memorizing
                     logger.error(f"MemoryHandler: MEMORIZE action for thought {thought_id} is missing required user_nick ({user_nick}) or channel ({channel}) after parameter parsing. Cannot perform memory operation.")
                     final_thought_status = ThoughtStatus.FAILED # Mark as failed
                else:
                     # Call the actual memory service method
                    mem_result = await memory_service.memorize(
                        user_nick=user_nick,
                        channel=channel,
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
                 # remembered_data = await memory_service.remember(params.query)
                 # if remembered_data:
                 #     logger.info(f"MemoryHandler: REMEMBERED data for thought {thought_id}.")
                 #     # Need a way to return remembered_data to the task flow - maybe put in thought's processing_context?
                 # else:
                 #     logger.info(f"MemoryHandler: REMEMBER query for thought {thought_id} found no data.")
                 final_thought_status = ThoughtStatus.COMPLETED # Assume completed once query is done

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


    llm_client = llm_service.get_client()
    # Pass the instructor-patched client to PDMA and Guardrails that use it
    ethical_pdma = EthicalPDMAEvaluator(llm_client.instruct_client, model_name=llm_client.model_name)
    # CSDMA uses the raw client
    csdma = CSDMAEvaluator(llm_client.client, model_name=llm_client.model_name)
    # ActionSelectionPDMA uses the raw client and patches internally with the configured mode
    action_pdma = ActionSelectionPDMAEvaluator(
        llm_client.client,
        model_name=llm_client.model_name,
        prompt_overrides=profile.action_selection_pdma_overrides,
        # instructor_mode is read from config by ActionSelectionPDMAEvaluator itself
    )

    guardrails = EthicalGuardrails(
        llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name
    )

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client, # WorkflowCoordinator still gets the raw client? Check WorkflowCoordinator __init__ - yes, expects CIRISLLMClient but uses llm_client.client
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

    try:
        # runtimes main_loop handles fetching messages and creating tasks
        # processor.start_processing handles running the agent processing rounds
        await asyncio.gather(runtime._main_loop(), processor.start_processing())
    finally:
        await asyncio.gather(llm_service.stop(), memory_service.stop())