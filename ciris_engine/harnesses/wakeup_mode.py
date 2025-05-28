from ciris_engine.processor import AgentProcessor

from typing import Callable, Any
import logging
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.runtime.base_runtime import BaseRuntime, CLIAdapter

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


class CLIActionSink:
    """Routes all agent outputs to CLI (stdout or stub)."""

    def __init__(self, cli_adapter):
        self.cli_adapter = cli_adapter

    async def send_message(self, channel_id, content):
        await self.cli_adapter.send_output(channel_id, content)

    async def run_tool(self, name, args):
        print(f"[CLIActionSink] Would run tool {name} with args {args}")

    async def send_embed(self, channel_id, embed):
        print(f"[CLIActionSink] Would send embed to {channel_id}: {embed}")

    async def send_file(self, channel_id, file_path, description=None):
        print(f"[CLIActionSink] Would send file {file_path} to {channel_id} ({description})")

    async def send_reaction(self, channel_id, message_id, emoji):
        print(f"[CLIActionSink] Would react to {message_id} in {channel_id} with {emoji}")


class NonBlockingCLIAdapter(CLIAdapter):
    """Non-blocking CLIAdapter with an async queue for test/event injection."""

    def __init__(self):
        super().__init__()
        import asyncio

        self._input_queue = asyncio.Queue()

    async def fetch_inputs(self):
        # Non-blocking: return all currently available messages
        messages = []
        while not self._input_queue.empty():
            messages.append(await self._input_queue.get())
        return messages

    async def inject_input(self, message):
        await self._input_queue.put(message)


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

        app_config = AppConfig()
        ponder_manager = PonderManager()
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
        action_dispatcher = build_action_dispatcher(
            ponder_manager=ponder_manager,
            action_sink=None,
        )
        thought_processor = ThoughtProcessor(
            dma_orchestrator=dma_orchestrator,
            context_builder=context_builder,
            guardrail_orchestrator=guardrail_orchestrator,
            ponder_manager=ponder_manager,
            app_config=app_config
        )
        agent_processor = AgentProcessor(app_config, thought_processor, action_dispatcher, {}, startup_channel_id="cli")

        # Run the wakeup sequence and stream outputs to stdout
        await agent_processor.wakeup_processor.initialize()
        result = await agent_processor.wakeup_processor.process(0, non_blocking=False)
        print(f"Wakeup sequence result: {result}")

        await llm_service.stop()
        await memory_service.stop()

    asyncio.run(main())
