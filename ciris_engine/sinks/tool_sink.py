"""
Tool sink implementation for tool-related actions.
"""

import logging
import asyncio
from typing import Dict, List, Optional, Any

from ciris_engine.schemas.service_actions_v1 import (
    ActionType,
    ActionMessage,
    SendToolAction,
    FetchToolAction,
)
from .base_sink import BaseMultiServiceSink
from ..protocols.services import ToolService

logger = logging.getLogger(__name__)


class MultiServiceToolSink(BaseMultiServiceSink):
    """Specialized sink for tool-related actions"""
    def __init__(self, 
                 service_registry: Optional[Any] = None,
                 max_queue_size: int = 1000,
                 fallback_channel_id: Optional[str] = None):
        super().__init__(service_registry, max_queue_size, fallback_channel_id)
        self._tool_results: Dict[str, Any] = {}
    
    @property
    def service_routing(self) -> Dict[ActionType, str]:
        return {
            ActionType.SEND_TOOL: 'tool',
            ActionType.FETCH_TOOL: 'tool',
        }
    
    @property
    def capability_map(self) -> Dict[ActionType, List[str]]:
        return {
            ActionType.SEND_TOOL: ['execute_tool'],
            ActionType.FETCH_TOOL: ['get_tool_result'],
        }
    
    async def _execute_action_on_service(self, service: ToolService, action: ActionMessage):
        """Execute tool action on service"""
        if action.type == ActionType.SEND_TOOL:
            result = await service.execute_tool(action.tool_name, action.tool_args)
            correlation_id = action.correlation_id or f"tool_{asyncio.get_event_loop().time()}"
            logger.info(f"Executed tool {action.tool_name} with correlation {correlation_id}")
            if correlation_id:
                self._tool_results[correlation_id] = result
            return result
        elif action.type == ActionType.FETCH_TOOL:
            result = await service.get_tool_result(action.correlation_id, action.timeout)
            if result:
                logger.info(f"Retrieved tool result for correlation {action.correlation_id}")
            else:
                logger.warning(f"No tool result found for correlation {action.correlation_id}")
            return result
    
    async def execute_tool(self, handler_name: str, tool_name: str, tool_args: Dict[str, Any], 
                          correlation_id: Optional[str] = None, metadata: Optional[Dict] = None) -> bool:
        """Convenience method to execute a tool"""
        action = SendToolAction(
            handler_name=handler_name,
            metadata=metadata or {},
            tool_name=tool_name,
            tool_args=tool_args,
            correlation_id=correlation_id
        )
        return await self.enqueue_action(action)
