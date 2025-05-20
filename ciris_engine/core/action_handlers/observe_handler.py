from ..agent_core_schemas import Thought

async def handle_observe(thought: Thought, params: dict, observer_service):
    await observer_service.observe(params)
    thought.action_count += 1
    thought.history.append({"action": "observe"})
