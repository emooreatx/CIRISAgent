#!/usr/bin/env python3
"""
CLI utility to run the CIRISAgent wakeup mode harness outside of Discord.
This script creates a minimal AgentProcessor and runs the wakeup sequence, printing output to the console.
"""
import asyncio
import logging
from ciris_engine.harnesses.wakeup_mode import run_wakeup
from ciris_engine.core import persistence
from ciris_engine.core.config_manager import get_config_async
from ciris_engine.utils.profile_loader import load_profile
from ciris_engine.services.llm_service import LLMService
from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
from ciris_engine.core.workflow_coordinator import WorkflowCoordinator
from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.action_handlers import (
    ActionHandlerDependencies, SpeakHandler, DeferHandler, RejectHandler, ObserveHandler, MemorizeHandler, ToolHandler, TaskCompleteHandler
)
from ciris_engine.core.agent_core_schemas import HandlerActionType
from ciris_engine.core.agent_processor import AgentProcessor
from ciris_engine.dma.pdma import EthicalPDMAEvaluator
from ciris_engine.dma.csdma import CSDMAEvaluator
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
import instructor
from ciris_engine.guardrails import EthicalGuardrails

class ConsoleActionSink:
    async def start(self):
        pass
    async def stop(self):
        pass
    async def send_message(self, channel_id: str, content: str) -> None:
        print(f"[ConsoleActionSink] ({channel_id}): {content}")
    async def run_tool(self, tool_name: str, arguments: dict) -> None:
        print(f"[ConsoleActionSink] Tool: {tool_name} Args: {arguments}")

async def async_main():
    logging.basicConfig(level=logging.INFO)
    persistence.initialize_database()
    app_config = await get_config_async()
    profile_path = "ciris_profiles/teacher.yaml"
    profile = await load_profile(profile_path)
    if not profile:
        raise FileNotFoundError(profile_path)
    if profile.name.lower() not in app_config.agent_profiles:
        app_config.agent_profiles[profile.name.lower()] = profile

    llm_service = LLMService(app_config.llm_services)
    memory_service = CIRISLocalGraph()
    await llm_service.start()
    await memory_service.start()
    llm_client = llm_service.get_client()

    action_sink = ConsoleActionSink()
    action_handler_deps = ActionHandlerDependencies(
        action_sink=action_sink,
        memory_service=memory_service,
        observer_service=None,
        io_adapter=None,
        deferral_sink=None,
    )
    speak_handler = SpeakHandler(action_handler_deps)
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
    action_dispatcher = ActionDispatcher(handlers=handlers_map)

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
        llm_client=llm_client.client,
        ethical_pdma_evaluator=ethical_pdma,
        csdma_evaluator=csdma,
        action_selection_pdma_evaluator=action_pdma,
        ethical_guardrails=guardrails,
        app_config=app_config,
        dsdma_evaluators={},
        memory_service=memory_service,
    )
    services_dict = {
        "llm_client": llm_client,
        "memory_service": memory_service,
    }
    processor = AgentProcessor(
        app_config=app_config,
        workflow_coordinator=workflow_coordinator,
        action_dispatcher=action_dispatcher,
        services=services_dict,
        startup_channel_id="console",
    )

    # Metrics
    thoughts_processed = 0
    orig_process_thought = workflow_coordinator.process_thought
    async def process_thought_with_metrics(*args, **kwargs):
        nonlocal thoughts_processed
        thoughts_processed += 1
        print(f"[Progress] Thoughts processed: {thoughts_processed}")
        return await orig_process_thought(*args, **kwargs)
    workflow_coordinator.process_thought = process_thought_with_metrics

    processor_task = asyncio.create_task(processor.start_processing())
    try:
        print("[Startup] Running wakeup sequence...")
        result = await run_wakeup(processor)
        print(f"Wakeup harness completed with result: {result}")
    finally:
        processor._stop_event.set()
        await processor_task
        await llm_service.stop()
        await memory_service.stop()

def main():
    asyncio.run(async_main())

if __name__ == "__main__":
    main()
