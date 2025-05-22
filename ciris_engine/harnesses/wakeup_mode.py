from ciris_engine.core.agent_processor import AgentProcessor


async def run_wakeup(agent_processor: AgentProcessor) -> bool:
    """Execute only the wakeup ritual using the processor's built-in sequence."""
    return await agent_processor._run_wakeup_sequence()
