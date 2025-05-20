from .foundational_schemas import HandlerActionType
from .agent_core_schemas import Thought
from typing import Callable, Awaitable, Any

from .action_handlers.speak_handler import handle_speak
from .action_handlers.observe_handler import handle_observe
from .action_handlers.memorize_handler import handle_memorize
from .action_handlers.defer_handler import handle_defer
from .action_handlers.tool_handler import handle_tool
from .action_handlers.task_complete_handler import handle_task_complete

handler_map = {
    HandlerActionType.SPEAK: handle_speak,
    HandlerActionType.OBSERVE: handle_observe,
    HandlerActionType.MEMORIZE: handle_memorize,
    HandlerActionType.DEFER: handle_defer,
    HandlerActionType.TOOL: handle_tool,
    HandlerActionType.TASK_COMPLETE: handle_task_complete,
}

ServiceHandlerCallable = Callable[[Any, Any], Awaitable[None]]

async def dispatch(action_type: HandlerActionType, thought: Thought, params: dict, services: dict):
    handler = handler_map[action_type]
    await handler(thought, params, **services)

class ActionDispatcher:
    def __init__(self, audit_service=None):
        self.service_handlers = {}
        self.action_filter = None

    def register_service_handler(self, service_name: str, handler_callback):
        self.service_handlers[service_name] = handler_callback

    async def dispatch(self, action_type: HandlerActionType, thought: Thought, params: dict, services: dict):
        if self.action_filter:
            class _Res:
                def __init__(self, act):
                    self.selected_handler_action = act

            should_skip = await self.action_filter(_Res(action_type), {"params": params})
            if should_skip:
                return
        await dispatch(action_type, thought, params, services)
