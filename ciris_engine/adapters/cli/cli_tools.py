import os
import asyncio
from typing import Dict, Any, List, Optional

from ciris_engine.protocols.services import ToolService

class CLIToolService(ToolService):
    """Simple ToolService providing local filesystem browsing."""

    def __init__(self):
        self._results: Dict[str, Dict[str, Any]] = {}

    async def execute_tool(self, tool_name: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        correlation_id = parameters.get("correlation_id")
        result: Dict[str, Any]
        if tool_name == "list_files":
            path = parameters.get("path", ".")
            try:
                files = sorted(os.listdir(path))
                result = {"files": files, "path": path}
            except Exception as e:
                result = {"error": str(e)}
        else:
            result = {"error": f"unknown tool {tool_name}"}
        if correlation_id:
            self._results[correlation_id] = result
        return result

    async def get_available_tools(self) -> List[str]:
        return ["list_files"]

    async def get_tool_result(self, correlation_id: str, timeout: float = 30.0) -> Optional[Dict[str, Any]]:
        for _ in range(int(timeout * 10)):
            if correlation_id in self._results:
                return self._results.pop(correlation_id)
            await asyncio.sleep(0.1)
        return None

    async def validate_parameters(self, tool_name: str, parameters: Dict[str, Any]) -> bool:
        if tool_name == "list_files":
            return True
        return False
