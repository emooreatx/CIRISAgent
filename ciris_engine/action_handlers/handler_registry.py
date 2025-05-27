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
from .discord_observe_handler import handle_discord_observe_event  # Importing the Discord-specific handler
from .action_dispatcher import ActionDispatcher

# Add any required dependencies for handlers here, e.g., services, sinks, etc.
def build_action_dispatcher(audit_service=None, **handler_dependencies):
    """
    Instantiates all handlers and returns a ready-to-use ActionDispatcher.
    Passes handler_dependencies to each handler as needed.
    """
    handlers = {
        HandlerActionType.MEMORIZE: MemorizeHandler(**handler_dependencies),
        HandlerActionType.SPEAK: SpeakHandler(**handler_dependencies),
        HandlerActionType.OBSERVE: ObserveHandler(**handler_dependencies),
        HandlerActionType.DEFER: DeferHandler(**handler_dependencies),
        HandlerActionType.REJECT: RejectHandler(**handler_dependencies),
        HandlerActionType.TASK_COMPLETE: TaskCompleteHandler(**handler_dependencies),
        HandlerActionType.TOOL: ToolHandler(**handler_dependencies),
        HandlerActionType.OBSERVATION_EVENT: handle_discord_observe_event,  # Now uses Discord-specific handler
    }
    return ActionDispatcher(handlers, audit_service=audit_service)
