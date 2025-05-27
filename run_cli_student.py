import logging
from ciris_engine.utils.logging_config import setup_basic_logging
setup_basic_logging(level=logging.INFO)

import os
import asyncio
from typing import Optional

from ciris_engine.runtime.base_runtime import BaseRuntime, CLIAdapter
from ciris_engine.core.ports import ActionSink
from ciris_engine.core import persistence
from ciris_engine.core.config_manager import get_config_async
from ciris_engine.core.processor import AgentProcessor
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.guardrails import EthicalGuardrails
from ciris_engine.services.llm_service import LLMService
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.dma_results_v1 import SpeakParams, DeferParams, RejectParams, MemorizeParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus

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

    async def run_tool(self, tool_name: str, arguments: dict) -> None:
        return None


async def _cli_handler(runtime: BaseRuntime, sink: ActionSink, result: ActionSelectionResult, ctx: dict) -> None:
    """Handle speak/notify style actions for CLI output."""
    thought_id = ctx.get("thought_id")
    action = result.selected_handler_action
    params = result.action_parameters
    final_status = ThoughtStatus.COMPLETED

    try:
        if action == HandlerActionType.SPEAK and isinstance(params, SpeakParams):
            await sink.send_message(None, params.content)
        elif action == HandlerActionType.DEFER and isinstance(params, DeferParams):
            await sink.send_message(None, f"Deferred: {params.reason}")
            final_status = ThoughtStatus.DEFERRED
        elif action == HandlerActionType.REJECT and isinstance(params, RejectParams):
            await sink.send_message(None, f"Unable to proceed. Reason: {params.reason}")
        elif action == HandlerActionType.TOOL and isinstance(params, ActParams):
            await sink.run_tool(params.tool_name, params.arguments)
        else:
            logger.error("CLIHandler: Unhandled action %s", action.value)
            final_status = ThoughtStatus.FAILED
    except Exception as e:
        logger.exception("CLIHandler: Error processing action %s for thought %s: %s", action.value, thought_id, e)
        final_status = ThoughtStatus.FAILED

    if thought_id:
        try:
            persistence.update_thought_status(thought_id=thought_id, new_status=final_status, final_action_result=result.model_dump())
        except Exception as db_error:
            logger.error("CLIHandler: Failed to update thought %s status to %s in DB: %s", thought_id, final_status.value, db_error)


async def main() -> None:
    persistence.initialize_database()

    runtime = BaseRuntime(io_adapter=CLIAdapter(), profile_path=PROFILE_PATH)
    sink = CLIActionSink(runtime)
    runtime.dispatcher.register_service_handler("cli", lambda res, ctx: _cli_handler(runtime, sink, res, ctx))

    app_config = await get_config_async()
    profile = await runtime._load_profile()
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    memory_service = CIRISLocalGraph()

    await llm_service.start()
    await memory_service.start()

    llm_client = llm_service.get_client()
    ethical_pdma = EthicalPDMAEvaluator(llm_client.instruct_client, model_name=llm_client.model_name)
    csdma = CSDMAEvaluator(llm_client.client, model_name=llm_client.model_name)
    action_pdma = ActionSelectionPDMAEvaluator(
        llm_client.client,
        model_name=llm_client.model_name,
        prompt_overrides=profile.action_selection_pdma_overrides,
    )
    guardrails = EthicalGuardrails(llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name)

    workflow_coordinator = WorkflowCoordinator(
        llm_client=llm_client.client,
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails,
        app_config=app_config,
        dsdma_evaluators={},
        memory_service=memory_service,
    )

    processor = AgentProcessor(
        app_config=app_config,
        workflow_coordinator=workflow_coordinator,
        action_dispatcher=runtime.dispatcher,
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
