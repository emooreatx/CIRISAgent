import logging
from ciris_engine.utils.logging_config import setup_basic_logging
setup_basic_logging(level=logging.INFO)

import os
import asyncio
from typing import Optional

from ciris_engine.runtime.base_runtime import BaseRuntime, CLIAdapter
from ciris_engine.ports import ActionSink
from ciris_engine import persistence
from ciris_engine.config.config_manager import get_config_async
from ciris_engine.processor import AgentProcessor # AgentProcessor is in main_processor
from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
from ciris_engine.context.builder import ContextBuilder
from ciris_engine.ponder.manager import PonderManager
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.services.llm_service import LLMService
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.action_params_v1 import SpeakParams, DeferParams, RejectParams, MemorizeParams, ToolParams # Corrected import and added ToolParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
# Removed ThoughtStatus from here as it's already imported from foundational_schemas_v1

logger = logging.getLogger(__name__)

PROFILE_PATH = os.path.join("ciris_profiles", "student.yaml")


class CLIActionSink(ActionSink):
    """Send actions back through the CLI adapter."""

    def __init__(self, runtime: BaseRuntime):
        self.runtime = runtime

    async def start(self) -> None:
        pass

    async def stop(self) -> None:
        pass

    async def send_message(self, channel_id: Optional[str], content: str) -> None:
        await self.runtime.io_adapter.send_output(channel_id, content)

    async def run_tool(self, name: str, args: dict) -> None:
        return None


async def _cli_handler(runtime: BaseRuntime, sink: ActionSink, result: ActionSelectionResult, ctx: dict) -> None:
    """Handle speak/notify style actions for CLI output."""
    thought_id = ctx.get("thought_id")
    action = result.selected_action # Corrected to selected_action
    params = result.action_parameters # This is a dict
    final_status = ThoughtStatus.COMPLETED

    try:
        if action == HandlerActionType.SPEAK:
            # Assuming params is a dict that can be unpacked into SpeakParams
            # or SpeakParams.model_validate(params) if params is already a dict matching SpeakParams
            speak_params = SpeakParams(**params) if isinstance(params, dict) else params
            if isinstance(speak_params, SpeakParams):
                 await sink.send_message(None, speak_params.content)
        elif action == HandlerActionType.DEFER:
            defer_params = DeferParams(**params) if isinstance(params, dict) else params
            if isinstance(defer_params, DeferParams):
                await sink.send_message(None, f"Deferred: {defer_params.reason}")
                final_status = ThoughtStatus.DEFERRED
        elif action == HandlerActionType.REJECT:
            reject_params = RejectParams(**params) if isinstance(params, dict) else params
            if isinstance(reject_params, RejectParams):
                await sink.send_message(None, f"Unable to proceed. Reason: {reject_params.reason}")
        elif action == HandlerActionType.TOOL:
            tool_params = ToolParams(**params) if isinstance(params, dict) else params
            if isinstance(tool_params, ToolParams):
                await sink.run_tool(tool_params.name, tool_params.args)
        else:
            logger.error("CLIHandler: Unhandled action %s", action.value)
            final_status = ThoughtStatus.FAILED
    except Exception as e:
        logger.exception("CLIHandler: Error processing action %s for thought %s: %s", action.value, thought_id, e)
        final_status = ThoughtStatus.FAILED

    if thought_id:
        try:
            # result.model_dump() will include all fields from ActionSelectionResult
            # final_action in DB expects a dict of action details
            final_action_payload = {
                "action_type": action.value,
                "parameters": params, # params is already a dict here
                "rationale": result.rationale
            }
            persistence.update_thought_status(thought_id=thought_id, status=final_status, final_action=final_action_payload)
        except Exception as db_error:
            logger.error("CLIHandler: Failed to update thought %s status to %s in DB: %s", thought_id, final_status.value, db_error)


async def main() -> None:
    persistence.initialize_database()

    runtime = BaseRuntime(io_adapter=CLIAdapter(), profile_path=PROFILE_PATH)
    sink = CLIActionSink(runtime)
    runtime.dispatcher.register_service_handler("cli", lambda res, ctx: _cli_handler(runtime, sink, res, ctx))

    app_config = await get_config_async()
    profile = await runtime._load_profile() # Loads student.yaml by default from PROFILE_PATH
    if profile:
        app_config.agent_profiles[profile.name.lower()] = profile
    else:
        logger.error(f"Failed to load primary profile from {PROFILE_PATH}. Exiting.")
        return

    # Attempt to load the "default" profile as well
    from ciris_engine.utils.profile_loader import load_profile as load_profile_util
    from pathlib import Path
    default_profile_path = Path(app_config.profile_directory) / "default.yaml"
    default_profile_obj = await load_profile_util(default_profile_path)
    if default_profile_obj:
        app_config.agent_profiles["default"] = default_profile_obj
        logger.info(f"Successfully loaded and registered 'default' profile from {default_profile_path}")
    else:
        logger.warning(f"'default' profile not found or failed to load from {default_profile_path}. Some profile-specific features for 'default' may not work.")


    llm_service = LLMService(app_config.llm_services)
    memory_service = CIRISLocalGraph()

    await llm_service.start()
    await memory_service.start()

    llm_client = llm_service.get_client()
    ethical_pdma = EthicalPDMAEvaluator(llm_client.instruct_client, model_name=llm_client.model_name)
    csdma = CSDMAEvaluator(llm_client.client, model_name=llm_client.model_name) # Use non-instruct client for CSDMA
    
    # DSDMA setup (example, assuming a 'student_dsdma' or similar might be configured via profile)
    # For CLI student, DSDMA might be optional or a generic one.
    # If profile.dsdma_identifier exists, use dma_factory.get_dsdma_evaluator(...)
    # For now, assuming no specific DSDMA or it's handled by a factory not shown here.
    # If a DSDMA is needed, its instantiation would go here.
    # Example: student_dsdma = dma_factory.get_dsdma_evaluator(profile.dsdma_identifier, llm_client.client, ...)
    # For now, we'll pass None for dsdma to DMAOrchestrator if no specific one is configured.
    dsdma_instance = None # Placeholder

    dma_orchestrator = DMAOrchestrator(
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        dsdma=dsdma_instance, # Pass the DSDMA instance if available
        action_selection_pdma_evaluator=ActionSelectionPDMAEvaluator( # Instantiate ASPDMA here
            aclient=llm_client.client, # Use non-instruct client
            model_name=llm_client.model_name,
            prompt_overrides=profile.action_selection_pdma_overrides
        ),
        app_config=app_config,
        llm_service=llm_service,
        memory_service=memory_service
    )

    context_builder = ContextBuilder(
        memory_service=memory_service,
        # graphql_provider can be None if not used for CLI
    )
    
    # PonderManager needs llm_service and app_config
    ponder_manager = PonderManager(
        llm_service=llm_service, 
        app_config=app_config
    )

    guardrails = EthicalGuardrails(
        aclient=llm_client.instruct_client, # Guardrails might use instruct client
        guardrails_config=app_config.guardrails,
        model_name=llm_client.model_name
    )

    thought_processor = ThoughtProcessor(
        dma_orchestrator=dma_orchestrator,
        context_builder=context_builder,
        guardrail_orchestrator=guardrails, # Pass the guardrails instance
        ponder_manager=ponder_manager,
        app_config=app_config
    )
    
    services_dict = {
        "llm_service": llm_service,
        "memory_service": memory_service,
        "action_sink": sink, # Make sink available as a service if needed by handlers
        # Add other services if they are created and needed by handlers/processors
    }

    processor = AgentProcessor(
        app_config=app_config,
        thought_processor=thought_processor, # Pass ThoughtProcessor
        action_dispatcher=runtime.dispatcher,
        services=services_dict, # Pass services
        startup_channel_id=None # For CLI, there's no specific startup channel
    )

    async def main_loop():
        await sink.start()
        try:
            await asyncio.gather(runtime._main_loop(), processor.start_processing())
        finally:
            await sink.stop()

    try:
        await main_loop()
    finally:
        await asyncio.gather(llm_service.stop(), memory_service.stop())


if __name__ == "__main__":
    asyncio.run(main())
