from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.runtime.models import Thought
from ciris_engine.schemas.actions import ForgetParams
from ciris_engine.schemas.services.graph_core import GraphScope
from ciris_engine.logic.services.memory_service import MemoryOpStatus
from ciris_engine.protocols.services import MemoryService
from ciris_engine.logic.infrastructure.handlers.base_handler import BaseActionHandler
from ciris_engine.logic.infrastructure.handlers.helpers import create_follow_up_thought
from typing import Any
from ciris_engine.schemas.runtime.enums import HandlerActionType, ThoughtStatus
from ciris_engine.schemas.runtime.contexts import DispatchContext
from ciris_engine.logic import persistence
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class ForgetHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionDMAResult, thought: Thought, dispatch_context: DispatchContext) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.FORGET, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="start")
        params = raw_params
        if not isinstance(params, ForgetParams):
            try:
                params = ForgetParams(**params) if isinstance(params, dict) else params
            except ValidationError as e:
                logger.error(f"ForgetHandler: Invalid params dict: {e}")
                follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action failed: Invalid parameters. {e}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
                )
                context_data = follow_up.context.model_dump() if follow_up.context else {}
                context_data.update({
                    "action_performed": HandlerActionType.FORGET.name,
                    "parent_task_id": thought.source_task_id,
                    "is_follow_up": True,
                    "error": str(e)
                })
                # Note: We don't modify the context here since ThoughtContext has extra="forbid"
                # The error details are already captured in the follow_up content
                persistence.add_thought(follow_up)
                await self._audit_log(HandlerActionType.FORGET, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="failed")
                return
        if not isinstance(params, ForgetParams):
            logger.error(f"ForgetHandler: Invalid params type: {type(raw_params)}")
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action failed: Invalid parameters type: {type(raw_params)}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": f"Invalid params type: {type(raw_params)}"
            })
            # Note: We don't modify the context here since ThoughtContext has extra="forbid"
            # The error details are already captured in the follow_up content
            persistence.add_thought(follow_up)
            await self._audit_log(HandlerActionType.FORGET, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="failed")
            return
        if not self._can_forget(params, dispatch_context):
            logger.info("ForgetHandler: Permission denied or WA required for forget operation. Creating deferral.")
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action was not permitted. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": "Permission denied or WA required"
            })
            # Note: We don't modify the context here since ThoughtContext has extra="forbid"
            # The error details are already captured in the follow_up content
            persistence.add_thought(follow_up)
            await self._audit_log(
                HandlerActionType.FORGET,
                dispatch_context.model_copy(update={"thought_id": thought_id}),
                outcome="wa_denied"
            )
            return
        # Memory operations will use the memory bus

        node = params.node
        scope = node.scope
        if scope in (GraphScope.IDENTITY, GraphScope.ENVIRONMENT) and not getattr(dispatch_context, 'wa_authorized', False):
            follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content="FORGET action denied: WA authorization required"
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": "wa_denied",
            })
            # Note: We don't modify the context here since ThoughtContext has extra="forbid"
            # The error details are already captured in the follow_up content
            persistence.add_thought(follow_up)
            await self._audit_log(
                HandlerActionType.FORGET,
                dispatch_context,
                outcome="wa_denied",
            )
            return

        forget_result = await self.bus_manager.memory.forget(
            node=node,
            handler_name=self.__class__.__name__
        )
        await self._audit_forget_operation(params, dispatch_context, forget_result)
        success = forget_result.status == MemoryOpStatus.OK

        if success:
            follow_up_content = (
                f"CIRIS_FOLLOW_UP_THOUGHT: This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. Successfully forgot key '{node.id}' in scope {node.scope.value}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
        else:
            follow_up_content = (
                f"CIRIS_FOLLOW_UP_THOUGHT: This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. Failed to forget key '{node.id}' in scope {node.scope.value}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
        follow_up = create_follow_up_thought(parent=thought, time_service=self.time_service, content=follow_up_content)
        # Note: We don't modify the context here since ThoughtContext has extra="forbid"
        # The action details are already captured in the follow_up_text content
        persistence.add_thought(follow_up)
        await self._audit_log(
            HandlerActionType.FORGET,
            dispatch_context.model_copy(update={"thought_id": thought_id}),
            outcome="success" if success else "failed",
        )

    def _can_forget(self, params: ForgetParams, dispatch_context: DispatchContext) -> bool:
        if hasattr(params, 'node') and hasattr(params.node, 'scope'):
            scope = params.node.scope
            if scope in (GraphScope.IDENTITY, GraphScope.ENVIRONMENT):
                return getattr(dispatch_context, 'wa_authorized', False)
        return True

    async def _audit_forget_operation(self, params: ForgetParams, dispatch_context: DispatchContext, result: Any) -> None:
        if hasattr(params, 'no_audit') and params.no_audit:
            return
            
        audit_data = {
            "forget_key": params.node.id,
            "forget_scope": params.node.scope.value,
            "operation_result": str(result.status) if hasattr(result, 'status') else str(result),
            "timestamp": getattr(dispatch_context, 'event_timestamp', None),
            "thought_id": getattr(dispatch_context, 'thought_id', None)
        }
        
        await self._audit_log(
            HandlerActionType.FORGET,
            dispatch_context.model_copy(update=audit_data),
            outcome="forget_executed"
        )
