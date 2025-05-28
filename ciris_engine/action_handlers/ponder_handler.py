import logging
from ciris_engine.action_handlers.base_handler import BaseActionHandler, ActionHandlerDependencies
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import PonderParams
from ciris_engine.ponder.manager import PonderManager

logger = logging.getLogger(__name__)

class PonderHandler(BaseActionHandler):
    def __init__(self, dependencies: ActionHandlerDependencies, ponder_manager: PonderManager = None):
        super().__init__(dependencies)
        self.ponder_manager = ponder_manager or PonderManager()

    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: dict) -> None:
        params = result.action_parameters
        if not isinstance(params, PonderParams):
            # Try to coerce if dict
            if isinstance(params, dict):
                params = PonderParams(**params)
            else:
                logger.error(f"PonderHandler: Invalid params type: {type(params)}")
                return
        # Ensure channel_id is set in the thought context for downstream consumers (e.g., guardrails)
        channel_id = dispatch_context.get("channel_id")
        if hasattr(thought, "context"):
            if not thought.context:
                thought.context = {}
            if "channel_id" not in thought.context or not thought.context["channel_id"]:
                thought.context["channel_id"] = channel_id
        await self._audit_log(HandlerActionType.PONDER, {**dispatch_context, "thought_id": thought.thought_id}, outcome="start")
        await self.ponder_manager.handle_ponder_action(thought, params)
        await self._audit_log(HandlerActionType.PONDER, {**dispatch_context, "thought_id": thought.thought_id}, outcome="complete")
