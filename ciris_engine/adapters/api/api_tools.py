"""API tools endpoints for CIRISAgent, using the bus_manager for real tool service."""
import logging
from aiohttp import web
from typing import Any

logger = logging.getLogger(__name__)

class APIToolsRoutes:
    def __init__(self, bus_manager: Any) -> None:
        self.bus_manager = bus_manager

    def register(self, app: web.Application) -> None:
        app.router.add_get('/v1/tools', self._handle_list_tools)
        app.router.add_post('/v1/tools/{tool_name}', self._handle_tool)
        app.router.add_post('/v1/tools/{tool_name}/validate', self._handle_validate_tool)

    async def _handle_list_tools(self, request: web.Request) -> web.Response:
        try:
            tool_service = getattr(self.bus_manager, 'tool_service', None)
            if tool_service and hasattr(tool_service, 'get_available_tools'):
                tools = await tool_service.get_available_tools()
            else:
                tools = []
            return web.json_response([{"name": t} for t in tools])
        except Exception as e:
            logger.error(f"Error listing tools: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_tool(self, request: web.Request) -> web.Response:
        tool_name = request.match_info.get('tool_name')
        try:
            data = await request.json()
        except Exception:
            data = {}
        try:
            result = await self.bus_manager.execute_tool(tool_name, data)
            return web.json_response(result)
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_validate_tool(self, request: web.Request) -> web.Response:
        """Validate tool parameters without executing."""
        tool_name = request.match_info.get('tool_name')
        try:
            data = await request.json()
        except Exception:
            data = {}
        try:
            tool_service = getattr(self.bus_manager, 'tool_service', None)
            if tool_service and hasattr(tool_service, 'validate_parameters'):
                is_valid = await tool_service.validate_parameters(tool_name, data)
                return web.json_response({"valid": is_valid})
            else:
                if tool_service and hasattr(tool_service, 'get_available_tools'):
                    tools = await tool_service.get_available_tools()
                    exists = tool_name in tools
                    return web.json_response({"valid": exists, "reason": "Tool exists" if exists else "Tool not found"})
                return web.json_response({"error": "Validation not available"}, status=501)
        except Exception as e:
            logger.error(f"Error validating tool {tool_name}: {e}")
            return web.json_response({"error": str(e)}, status=500)
