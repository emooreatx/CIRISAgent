from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ForgetParams
from ciris_engine.schemas.graph_schemas_v1 import GraphScope
from ciris_engine.memory.ciris_local_graph import MemoryOpStatus
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
import logging

logger = logging.getLogger(__name__)

class ForgetHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: dict) -> None:
        params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.FORGET, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        if not isinstance(params, ForgetParams):
            logger.error(f"ForgetHandler: Invalid params type: {type(params)}")
            return
        if not self._can_forget(params, dispatch_context):
            logger.info("ForgetHandler: Permission denied or WA required for forget operation. Creating deferral.")
            # Optionally, create a deferral to WA here
            return
        forget_result = await self.dependencies.memory_service.forget(
            params.key,
            GraphScope(params.scope)
        )
        await self._audit_forget_operation(params, dispatch_context, forget_result)
        if forget_result.status == MemoryOpStatus.OK:
            follow_up_content = f"Successfully forgot key '{params.key}' in scope {params.scope}."
        else:
            follow_up_content = f"Failed to forget key '{params.key}' in scope {params.scope}."
        follow_up = create_follow_up_thought(
            parent=thought,
            content=follow_up_content,
        )
        self.dependencies.persistence.add_thought(follow_up)
        await self._audit_log(HandlerActionType.FORGET, {**dispatch_context, "thought_id": thought_id}, outcome="success" if forget_result.status == MemoryOpStatus.OK else "failed")

    def _can_forget(self, params, dispatch_context):
        # Placeholder: implement permission logic as needed
        return True

    async def _audit_forget_operation(self, params, dispatch_context, result):
        # Placeholder: implement audit logging as needed
        pass
