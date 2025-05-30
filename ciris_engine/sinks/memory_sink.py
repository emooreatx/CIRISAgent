"""
Memory sink implementation for memory-related actions.
"""

import logging
from typing import Dict, List, Optional, Any

from ciris_engine.schemas.service_actions_v1 import (
    ActionType,
    ActionMessage,
    MemorizeAction,
    RecallAction,
    ForgetAction,
)
from .base_sink import BaseMultiServiceSink
from ..protocols.services import MemoryService

logger = logging.getLogger(__name__)


class MultiServiceMemorySink(BaseMultiServiceSink):
    """Specialized sink for memory-related actions"""
    
    @property
    def service_routing(self) -> Dict[ActionType, str]:
        return {
            ActionType.MEMORIZE: 'memory',
            ActionType.RECALL: 'memory',
            ActionType.FORGET: 'memory',
        }
    
    @property
    def capability_map(self) -> Dict[ActionType, List[str]]:
        return {
            ActionType.MEMORIZE: ['memorize'],
            ActionType.RECALL: ['recall'],
            ActionType.FORGET: ['forget'],
        }
    
    async def _execute_action_on_service(self, service: MemoryService, action: ActionMessage):
        """Execute memory action on service"""
        if action.type == ActionType.MEMORIZE:
            success = await service.memorize(action.key, action.value, action.scope)
            if success:
                logger.info(f"Stored memory {action.key} via {type(service).__name__}")
            else:
                logger.warning(f"Failed to store memory via {type(service).__name__}")
        elif action.type == ActionType.RECALL:
            value = await service.recall(action.key, action.scope)
            logger.info(f"Retrieved memory {action.key} via {type(service).__name__}")
            return value
        elif action.type == ActionType.FORGET:
            success = await service.forget(action.key, action.scope)
            if success:
                logger.info(f"Deleted memory {action.key} via {type(service).__name__}")
            else:
                logger.warning(f"Failed to delete memory via {type(service).__name__}")
