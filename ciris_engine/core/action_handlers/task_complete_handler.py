from ..agent_core_schemas import Thought

async def handle_task_complete(thought: Thought, params: dict):
    thought.is_terminal = True
    thought.action_count += 1
    thought.history.append({"action": "task_complete"})
