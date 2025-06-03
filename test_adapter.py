"""Auto-generated adapter stub."""
from ciris_adk import ToolService

class TestAdapter(ToolService):
    async def list_tools(self) -> list[str]:
        return []

    async def call_tool(self, name: str, *, arguments: dict | None = None, timeout: float | None = None) -> dict:
        return {}
