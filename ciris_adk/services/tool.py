"""ToolService protocol for executing external tools."""

from __future__ import annotations

from typing import Any, Dict, Protocol


class ToolService(Protocol):
    async def list_tools(self) -> list[str]:
        """Return a list of available tool names."""
        ...

    async def call_tool(
        self,
        name: str,
        *,
        arguments: Dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> Dict[str, Any]:
        """Execute a tool and return its result."""
        ...

