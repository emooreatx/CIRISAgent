from ..agent_core_schemas import Thought

async def handle_tool(thought: Thought, params: dict, tool_service):
    tool_name = params["tool_name"]
    arguments = params.get("arguments", {})
    await tool_service.execute_tool(tool_name, arguments)
    thought.action_count += 1
    thought.history.append({"action": "tool", "tool_name": tool_name})
