from ciris_engine.processor import AgentProcessor

from typing import Callable, Any
import logging
from ciris_engine.utils.logging_config import setup_basic_logging

setup_basic_logging(level=logging.INFO)

# Holistic logging fix: ensure all CIRIS loggers and submodules always log at INFO or lower
for name in logging.root.manager.loggerDict:
    if name.startswith("ciris_engine"):
        logging.getLogger(name).setLevel(logging.INFO)
        logging.getLogger(name).propagate = True


async def run_wakeup(
    agent_processor: AgentProcessor,
    output_func: Callable[[Any], None] = print,
    *,
    non_blocking: bool = False,
) -> dict:
    """Execute the wakeup ritual using the processor's WakeupProcessor with real handler logic."""
    await agent_processor.wakeup_processor.initialize()
    # Use the real process method, which will invoke the registered handlers (including PonderHandler)
    result = await agent_processor.wakeup_processor.process(0, non_blocking=non_blocking)
    output_func(f"Wakeup sequence result: {result}")
    return result


if __name__ == "__main__":
    import asyncio

    async def main():
        from ciris_engine.schemas.config_schemas_v1 import AppConfig
        from ciris_engine.ponder.manager import PonderManager
        from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
        from ciris_engine.processor.thought_processor import ThoughtProcessor
        from ciris_engine.processor.main_processor import AgentProcessor
        from ciris_engine.dma.pdma import EthicalPDMAEvaluator
        from ciris_engine.dma.csdma import CSDMAEvaluator
        from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
        from ciris_engine.dma.factory import create_dsdma_from_profile
        from ciris_engine.processor.dma_orchestrator import DMAOrchestrator
        from ciris_engine.guardrails import EthicalGuardrails
        from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
        from ciris_engine.services.llm_service import LLMService
        from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
        from ciris_engine.context.builder import ContextBuilder
        import instructor
        from ciris_engine.runtime import CLIAdapter
        from ciris_engine.ports import ActionSink

        class CLIHarnessActionSink(ActionSink):
            def __init__(self):
                self.cli_adapter = CLIAdapter()
            async def start(self): pass
            async def stop(self): pass
            async def send_message(self, channel_id, content):
                await self.cli_adapter.send_output(channel_id, content)
            async def run_tool(self, name, args):
                print(f"[CLIHarnessActionSink] Would run tool {name} with args {args}")

        # Load config (could be extended to load from file/env)
        app_config = AppConfig()
        ponder_manager = PonderManager()
        # Minimal LLM/memory/graph setup for harness
        llm_service = LLMService(app_config.llm_services)
        memory_service = CIRISLocalGraph()
        await llm_service.start()
        await memory_service.start()
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
            prompt_overrides=None,
            instructor_mode=instructor.Mode[app_config.llm_services.openai.instructor_mode.upper()]
        )
        # For harness, skip DSDMA/profile loading
        dsdma_instance = None
        dma_orchestrator = DMAOrchestrator(
            ethical_pdma,
            csdma,
            dsdma_instance,
            action_pdma,
            app_config=app_config,
            llm_service=llm_service,
            memory_service=memory_service
        )
        context_builder = ContextBuilder(
            memory_service=memory_service,
            graphql_provider=None,
            app_config=app_config
        )
        guardrails = EthicalGuardrails(
            llm_client.instruct_client, app_config.guardrails, model_name=llm_client.model_name
        )
        guardrail_orchestrator = GuardrailOrchestrator(guardrails)
        action_sink = CLIHarnessActionSink()
        action_dispatcher = build_action_dispatcher(
            ponder_manager=ponder_manager,
            action_sink=action_sink,
        )
        thought_processor = ThoughtProcessor(
            dma_orchestrator=dma_orchestrator,
            context_builder=context_builder,
            guardrail_orchestrator=guardrail_orchestrator,
            ponder_manager=ponder_manager,
            app_config=app_config
        )
        # Pass startup_channel_id to AgentProcessor so WakeupProcessor gets it
        agent_processor = AgentProcessor(app_config, thought_processor, action_dispatcher, {}, startup_channel_id="cli")

        # Ensure the agent is in WAKEUP state before running the wakeup rounds
        from ciris_engine.schemas.states import AgentState
        agent_processor.state_manager.transition_to(AgentState.WAKEUP)

        await agent_processor.wakeup_processor.initialize()

        from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
        from ciris_engine import persistence
        import asyncio

        async def all_wakeup_tasks_completed(wakeup_processor):
            # Exclude the root task (first in list)
            # Corrected: Should return False if not enough tasks are present (e.g., before they are created)
            if not wakeup_processor.wakeup_tasks or len(wakeup_processor.wakeup_tasks) < 2:
                return False
            for task in wakeup_processor.wakeup_tasks[1:]:
                t = persistence.get_task_by_id(task.task_id)
                if not t or t.status != TaskStatus.COMPLETED:
                    return False
            return True

        round_number = 0
        while not await all_wakeup_tasks_completed(agent_processor.wakeup_processor):
            # Corrected: Use non_blocking=True to allow other handlers to complete tasks
            await agent_processor.wakeup_processor.process(round_number, non_blocking=True)
            round_number += 1
            print(f"[HARNESS] Sleeping 1s after round {round_number}")
            await asyncio.sleep(1)  # Use asyncio sleep for async context

        # Explicitly transition to SHUTDOWN after wakeup
        if agent_processor.state_manager.get_state() != AgentState.SHUTDOWN:
            agent_processor.state_manager.transition_to(AgentState.SHUTDOWN)
        await llm_service.stop()
        await memory_service.stop()

    asyncio.run(main())
