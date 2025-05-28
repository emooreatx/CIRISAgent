from ciris_engine.processor import AgentProcessor

from typing import Callable, Any


async def run_wakeup(
    agent_processor: AgentProcessor,
    output_func: Callable[[Any], None] = print,
    *,
    non_blocking: bool = False,
) -> dict:
    """Execute the wakeup ritual using the processor's WakeupProcessor."""
    await agent_processor.wakeup_processor.initialize()
    result = await agent_processor.wakeup_processor.process(0, non_blocking=non_blocking)
    output_func(f"Wakeup sequence result: {result}")
    return result
