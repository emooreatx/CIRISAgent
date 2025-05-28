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

async def run_work_shutdown(
    agent_processor: AgentProcessor,
    output_func: Callable[[Any], None] = print,
    *,
    num_rounds: int = 10,
) -> dict:
    """Run 10 work rounds using the processor's WorkProcessor, then shut down."""
    from ciris_engine.schemas.states import AgentState
    # Ensure the agent is in WORK state
    agent_processor.state_manager.transition_to(AgentState.WORK)
    await agent_processor.work_processor.initialize()
    results = []
    for round_number in range(num_rounds):
        result = await agent_processor.work_processor.process(round_number)
        output_func(f"[WORK] Round {round_number+1} result: {result}")
        results.append(result)
    # Explicitly transition to SHUTDOWN after work rounds
    agent_processor.state_manager.transition_to(AgentState.SHUTDOWN)
    return {"status": "completed", "rounds": num_rounds, "results": results}

if __name__ == "__main__":
    import asyncio
    async def main():
        from ciris_engine.schemas.config_schemas_v1 import AppConfig
        from ciris_engine.ponder.manager import PonderManager
        from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
        from ciris_engine.processor.thought_processor import ThoughtProcessor
        from ciris_engine.processor.main_processor import AgentProcessor
        from ciris_engine.services.llm_service import LLMService
        from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph
        from ciris_engine.context.builder import ContextBuilder
        from ciris_engine.ports import ActionSink
        from ciris_engine.runtime import CLIAdapter
        app_config = AppConfig()
        ponder_manager = PonderManager()
        llm_service = LLMService(app_config.llm_services)
        memory_service = CIRISLocalGraph()
        await llm_service.start()
        await memory_service.start()
        llm_client = llm_service.get_client()
        context_builder = ContextBuilder(
            memory_service=memory_service,
            graphql_provider=None,
            app_config=app_config
        )
        action_sink = type("CLIHarnessActionSink", (ActionSink,), {
            "__init__": lambda self: setattr(self, "cli_adapter", CLIAdapter()),
            "start": lambda self: None,
            "stop": lambda self: None,
            "send_message": lambda self, channel_id, content: self.cli_adapter.send_output(channel_id, content),
            "run_tool": lambda self, name, args: print(f"[CLIHarnessActionSink] Would run tool {name} with args {args}")
        })()
        action_dispatcher = build_action_dispatcher(
            ponder_manager=ponder_manager,
            action_sink=action_sink,
        )
        thought_processor = ThoughtProcessor(
            dma_orchestrator=None,
            context_builder=context_builder,
            guardrail_orchestrator=None,
            ponder_manager=ponder_manager,
            app_config=app_config
        )
        agent_processor = AgentProcessor(app_config, thought_processor, action_dispatcher, {}, startup_channel_id="cli")
        await run_work_shutdown(agent_processor)
        await llm_service.stop()
        await memory_service.stop()
    asyncio.run(main())
