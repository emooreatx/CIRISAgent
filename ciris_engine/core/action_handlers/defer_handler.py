from ..agent_core_schemas import Thought

async def handle_defer(thought: Thought, params: dict):
    reason = params.get("reason")
    thought.is_terminal = True
    thought.action_count += 1
    thought.history.append({"action": "defer", "reason": reason})
