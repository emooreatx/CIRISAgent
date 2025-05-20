"""Service action for TOOL."""

from ..agent_core_schemas import Thought
from .helpers import create_follow_up_thought

async def handle_tool(thought: Thought, params: dict, tool_service) -> Thought:
    """Execute a tool and return a follow-up Thought."""
    tool_name = params["tool_name"]
    arguments = params.get("arguments", {})
    await tool_service.execute_tool(tool_name, arguments)
    return create_follow_up_thought(thought)
