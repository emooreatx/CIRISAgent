import os
import asyncio

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
from ciris_engine.services.discord_graph_memory import DiscordGraphMemory
from ciris_engine.core.agent_core_schemas import (
    HandlerActionType,
    SpeakParams,
    DeferParams,
    RejectParams,
)
from ciris_engine.core.foundational_schemas import ThoughtStatus

TOKEN = os.getenv("DISCORD_BOT_TOKEN")
SNORE_CHANNEL_ID = os.getenv("SNORE_CHANNEL_ID")
PROFILE_PATH = os.path.join("ciris_profiles", "teacher.yaml")


async def _discord_handler(runtime: BaseRuntime, result, ctx):
    """Minimal handler to send outputs via the runtime's adapter."""
    thought_id = ctx.get("thought_id")
    channel_id = ctx.get("channel_id")
    action = result.selected_handler_action
    params = result.action_parameters

    if action == HandlerActionType.SPEAK and isinstance(params, SpeakParams):
        if channel_id:
            await runtime.io_adapter.send_output(channel_id, params.content)
        if thought_id:
            persistence.update_thought_status(
                thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump()
            )
    elif action == HandlerActionType.DEFER and isinstance(params, DeferParams):
        if channel_id:
            await runtime.io_adapter.send_output(channel_id, f"Deferred: {params.reason}")
        if thought_id:
            persistence.update_thought_status(
                thought_id, ThoughtStatus.DEFERRED, final_action_result=result.model_dump()
            )
    elif action == HandlerActionType.REJECT and isinstance(params, RejectParams):
        if channel_id:
            await runtime.io_adapter.send_output(channel_id, f"Rejected: {params.reason}")
        if thought_id:
            persistence.update_thought_status(
                thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump()
            )
    else:
        if thought_id:
            persistence.update_thought_status(
                thought_id, ThoughtStatus.COMPLETED, final_action_result=result.model_dump()
            )


async def main() -> None:
    if not TOKEN:
        print("DISCORD_BOT_TOKEN not set")
        return

    setup_basic_logging()
    persistence.initialize_database()

    runtime = BaseRuntime(
        io_adapter=DiscordAdapter(TOKEN),
        profile_path=PROFILE_PATH,
        snore_channel_id=SNORE_CHANNEL_ID,
    )

    runtime.dispatcher.register_service_handler(
        "discord", lambda result, ctx: _discord_handler(runtime, result, ctx)
    )

    app_config = await get_config_async()
    profile = await runtime._load_profile()

    llm_service = LLMService(app_config.llm_services)
    memory_service = DiscordGraphMemory()
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

    guardrails = EthicalGuardrails(
        llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name
    )

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

    try:
        await asyncio.gather(runtime._main_loop(), processor.start_processing())
    finally:
        await asyncio.gather(llm_service.stop(), memory_service.stop())


if __name__ == "__main__":
    asyncio.run(main())
