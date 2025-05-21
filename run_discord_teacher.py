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
    ObserveParams, # ObserveParams is used by ObserveHandler
    Thought,
    # ActParams, DeferParams, MemorizeParams, RejectParams, SpeakParams are used by their respective handlers
)
from ciris_engine.core.foundational_schemas import ThoughtStatus, TaskStatus
from pydantic import BaseModel # Used by handlers for params
import uuid # Used by handlers
from ciris_engine.utils.constants import DEFAULT_WA, WA_USER_ID # Potentially used by handlers or context
# from ciris_engine.core.action_handlers.helpers import create_follow_up_thought # Now used within handlers
from datetime import datetime, timezone
from ciris_engine.utils.profile_loader import load_profile # Added import

# Centralized Action Handlers and Dispatcher
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.action_handlers import (
    ActionHandlerDependencies,
    SpeakHandler,
    DeferHandler,
    RejectHandler,
    ObserveHandler,
    MemorizeHandler,
    ToolHandler,
    TaskCompleteHandler
)
from ciris_engine.dma.factory import create_dsdma_from_profile


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
    async def run_tool(self, tool_name: str, arguments: dict) -> None: 
        # This is a basic sink; tool execution results would typically be handled
        # by the agent observing the effects of the tool, or the tool directly
        # creating new observations/events. For now, this is a placeholder.
        logger.info(f"DiscordActionSink: Request to run tool '{tool_name}' with args: {arguments}. (Placeholder implementation)")
        return None

# _discord_handler is removed as its logic is now in centralized handlers.
# _memory_handler is removed as its logic is now in MemorizeHandler.
# _get_user_nick_for_memory is removed as its logic is now in MemorizeHandler.
# _observer_service_handler is removed as its logic is now in ObserveHandler (for active look)
# or handled by the core event router for passive observations.

async def main() -> None:
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return

    persistence.initialize_database()
    app_config = await get_config_async() # Moved this line up

    # Initialize and run DatabaseMaintenanceService
    from ciris_engine.services.maintenance_service import DatabaseMaintenanceService
    # Assuming app_config has these paths, or use defaults / direct strings if not
    archive_dir = getattr(getattr(app_config, "data_paths", {}), "archive_dir", "data_archive")
    archive_hours = getattr(getattr(app_config, "maintenance", {}), "archive_older_than_hours", 24)
    
    db_maintenance_service = DatabaseMaintenanceService(
        archive_dir_path=archive_dir, 
        archive_older_than_hours=archive_hours
    )
    await db_maintenance_service.perform_startup_cleanup()

    from ciris_engine.runtime.base_runtime import IncomingMessage
    from ciris_engine.services.discord_event_queue import DiscordEventQueue
    discord_message_queue = DiscordEventQueue[IncomingMessage]()
    discord_adapter = DiscordAdapter(TOKEN, message_queue=discord_message_queue) # Create adapter first
    discord_sink = DiscordActionSink(None) # Placeholder, will be set after runtime init

    # app_config is already loaded
    profile = await load_profile(PROFILE_PATH) # Load profile directly, not via runtime yet
    if not profile:
        raise FileNotFoundError(PROFILE_PATH)

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

    llm_client = llm_service.get_client()

    # Create dependencies for action handlers
    # ActionSink needs runtime, but runtime needs dispatcher.
    # We'll create a temporary sink or set it later if BaseRuntime needs it during init.
    # For now, ActionHandlerDependencies can take None for action_sink if it's only used by handlers later.
    # Or, we can initialize runtime, then sink, then update deps.
    # Let's initialize ActionHandlerDependencies with a placeholder sink for now,
    # and ensure the real sink is available when handlers are called.
    # A better way: initialize sink after runtime, then pass to deps.

    action_handler_deps = ActionHandlerDependencies(
        action_sink=None, # Will be set after runtime is initialized
        memory_service=memory_service,
        observer_service=discord_observer,
        io_adapter=discord_adapter # Pass the discord_adapter here
    )

    speak_handler = SpeakHandler(action_handler_deps, snore_channel_id=SNORE_CHANNEL_ID)
    defer_handler = DeferHandler(action_handler_deps)
    reject_handler = RejectHandler(action_handler_deps)
    observe_handler = ObserveHandler(action_handler_deps)
    memorize_handler = MemorizeHandler(action_handler_deps)
    tool_handler = ToolHandler(action_handler_deps)
    task_complete_handler = TaskCompleteHandler(action_handler_deps)

    handlers_map = {
        HandlerActionType.SPEAK: speak_handler,
        HandlerActionType.DEFER: defer_handler,
        HandlerActionType.REJECT: reject_handler,
        HandlerActionType.OBSERVE: observe_handler,
        HandlerActionType.MEMORIZE: memorize_handler,
        HandlerActionType.TOOL: tool_handler,
        HandlerActionType.TASK_COMPLETE: task_complete_handler,
    }

    # Instantiate the new ActionDispatcher
    # The audit_service for ActionDispatcher can be created here if BaseRuntime doesn't own it solely.
    # For now, ActionDispatcher's audit_service is optional.
    new_action_dispatcher = ActionDispatcher(handlers=handlers_map)
    
    runtime = BaseRuntime(
        io_adapter=discord_adapter,
        profile_path=PROFILE_PATH, # Profile object could be passed instead if already loaded
        action_dispatcher=new_action_dispatcher, # Pass the configured dispatcher
        snore_channel_id=SNORE_CHANNEL_ID,
    )
    discord_sink.runtime = runtime # Now set the runtime for the sink
    action_handler_deps.action_sink = discord_sink # Update dependency with real sink

    # The old runtime.dispatcher.register_service_handler for "discord" and "memory" is no longer needed here
    # as these are handled by the new ActionDispatcher and its centralized handlers.

    # profile is already loaded and added to app_config.agent_profiles
    # llm_service, memory_service, discord_observer are already initialized.
    # llm_client is already initialized.
    # action_handler_deps, handlers_map, and new_action_dispatcher are already initialized.

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

    # Create the DSDMA instance for the loaded profile
    dsdma_instance = await create_dsdma_from_profile(profile, llm_client.client, model_name=llm_client.model_name)
    dsdma_evaluators = {profile.name.lower(): dsdma_instance} if dsdma_instance else {}

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client, ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma, action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails, app_config=app_config,
        dsdma_evaluators=dsdma_evaluators, memory_service=memory_service,
    )
    # services_dict is still used by AgentProcessor for other potential needs or context.
    # It's not directly used by the new ActionDispatcher's main path but could be part of dispatch_context.
    services_dict = {
        "llm_client": llm_service.get_client(), # For DMAs
        "memory_service": memory_service, # For WorkflowCoordinator context, and handler deps
        "discord_service": runtime.io_adapter, # For general Discord interactions if needed outside handlers
        "observer_service": discord_observer, # For event source and handler deps
        # Potentially add other services if AgentProcessor or other components need them.
    }
    
    processor = AgentProcessor(
        app_config=app_config,
        workflow_coordinator=workflow_coordinator,
        action_dispatcher=new_action_dispatcher, # Pass the new dispatcher
        services=services_dict, # services_dict is still passed for general context
        startup_channel_id=SNORE_CHANNEL_ID,
    )
    event_source = DiscordEventSource(discord_observer) # DiscordObserver is the event generator

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
        await asyncio.gather(
            llm_service.stop(), 
            memory_service.stop(),
            db_maintenance_service.stop() # Add maintenance service to shutdown
        )

if __name__ == "__main__":
    asyncio.run(main())
