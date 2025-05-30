# ciris_engine/action_handlers/handler_registry.py
"""
Central registry for all action handlers, mapping HandlerActionType to handler instances.
Ensures modular, v1-schema-compliant, and clean handler wiring for ActionDispatcher.
"""
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from .memorize_handler import MemorizeHandler
from .speak_handler import SpeakHandler
from .observe_handler import ObserveHandler
from .defer_handler import DeferHandler
from .reject_handler import RejectHandler
from .task_complete_handler import TaskCompleteHandler
from .tool_handler import ToolHandler
from .remember_handler import RememberHandler
from .forget_handler import ForgetHandler
from .action_dispatcher import ActionDispatcher
from .base_handler import ActionHandlerDependencies
from .ponder_handler import PonderHandler
import os

# Add any required dependencies for handlers here, e.g., services, sinks, etc.
def build_action_dispatcher(audit_service=None, max_ponder_rounds: int = 5, **handler_dependencies):
    """
    Instantiates all handlers and returns a ready-to-use ActionDispatcher.
    Passes handler_dependencies to each handler as needed.
    """
    deps = ActionHandlerDependencies(audit_service=audit_service, **handler_dependencies)
    handlers = {
        HandlerActionType.MEMORIZE: MemorizeHandler(deps),
        HandlerActionType.SPEAK: SpeakHandler(deps, snore_channel_id=os.getenv("SNORE_CHANNEL_ID")),
        HandlerActionType.OBSERVE: ObserveHandler(deps),
        HandlerActionType.DEFER: DeferHandler(deps),
        HandlerActionType.REJECT: RejectHandler(deps),
        HandlerActionType.TASK_COMPLETE: TaskCompleteHandler(deps),
        HandlerActionType.TOOL: ToolHandler(deps),
        HandlerActionType.REMEMBER: RememberHandler(deps),
        HandlerActionType.FORGET: ForgetHandler(deps),
        HandlerActionType.PONDER: PonderHandler(deps, max_ponder_rounds=max_ponder_rounds),
    }
    return ActionDispatcher(handlers, audit_service=audit_service)
