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
from .recall_handler import RecallHandler
from .forget_handler import ForgetHandler
from .action_dispatcher import ActionDispatcher
from .base_handler import ActionHandlerDependencies
from .ponder_handler import PonderHandler
from ciris_engine.config.env_utils import get_env_var
from typing import Optional

def build_action_dispatcher(service_registry=None, max_rounds: int = 5, shutdown_callback: Optional[str] = None, telemetry_service=None, multi_service_sink=None) -> None:
    """
    Instantiates all handlers and returns a ready-to-use ActionDispatcher.
    Uses service_registry for all service dependencies.
    """
    deps = ActionHandlerDependencies(
        service_registry=service_registry,
        shutdown_callback=shutdown_callback,
        multi_service_sink=multi_service_sink,
    )
    handlers = {
        HandlerActionType.MEMORIZE: MemorizeHandler(deps),
        HandlerActionType.SPEAK: SpeakHandler(deps, snore_channel_id=get_env_var("SNORE_CHANNEL_ID")),
        HandlerActionType.OBSERVE: ObserveHandler(deps),
        HandlerActionType.DEFER: DeferHandler(deps),
        HandlerActionType.REJECT: RejectHandler(deps),
        HandlerActionType.TASK_COMPLETE: TaskCompleteHandler(deps),
        HandlerActionType.TOOL: ToolHandler(deps),
        HandlerActionType.RECALL: RecallHandler(deps),
        HandlerActionType.FORGET: ForgetHandler(deps),
        HandlerActionType.PONDER: PonderHandler(deps, max_rounds=max_rounds),
    }
    dispatcher = ActionDispatcher(handlers, telemetry_service=telemetry_service)
    
    deps.action_dispatcher = dispatcher
    
    return dispatcher
