from ciris_engine.core.agent_processor import AgentProcessor

from typing import Callable, Any

async def run_wakeup(agent_processor: AgentProcessor, output_func: Callable[[Any], None] = print) -> bool:
    """Execute only the wakeup ritual using the processor's built-in sequence. Output results using output_func."""
    result = await agent_processor._run_wakeup_sequence()
    output_func(f"Wakeup sequence result: {result}")
    return result
