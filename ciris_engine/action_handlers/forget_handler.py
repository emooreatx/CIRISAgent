from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import ForgetParams
from ciris_engine.schemas.graph_schemas_v1 import GraphScope
from ciris_engine.services.memory_service import MemoryOpStatus
from ciris_engine.protocols.services import MemoryService
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from typing import Optional
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine import persistence
import logging
from pydantic import ValidationError

logger = logging.getLogger(__name__)

class ForgetHandler(BaseActionHandler):
    async def handle(self, result: ActionSelectionResult, thought: Thought, dispatch_context: dict) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.FORGET, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        params = raw_params
        if not isinstance(params, ForgetParams):
            try:
                params = ForgetParams(**params) if isinstance(params, dict) else params
            except ValidationError as e:
                logger.error(f"ForgetHandler: Invalid params dict: {e}")
                follow_up = create_follow_up_thought(
                    parent=thought,
                    content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action failed: Invalid parameters. {e}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
                )
                context_data = follow_up.context.model_dump() if follow_up.context else {}
                context_data.update({
                    "action_performed": HandlerActionType.FORGET.name,
                    "parent_task_id": thought.source_task_id,
                    "is_follow_up": True,
                    "error": str(e)
                })
                from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
                follow_up.context = ThoughtContext.model_validate(context_data)
                persistence.add_thought(follow_up)
                await self._audit_log(HandlerActionType.FORGET, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
                return
        if not isinstance(params, ForgetParams):
            logger.error(f"ForgetHandler: Invalid params type: {type(raw_params)}")
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action failed: Invalid parameters type: {type(raw_params)}. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": f"Invalid params type: {type(raw_params)}"
            })
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(follow_up)
            await self._audit_log(HandlerActionType.FORGET, {**dispatch_context, "thought_id": thought_id}, outcome="failed")
            return
        if not self._can_forget(params, dispatch_context):
            logger.info("ForgetHandler: Permission denied or WA required for forget operation. Creating deferral.")
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"This is a follow-up thought from a FORGET action performed on parent task {thought.source_task_id}. FORGET action was not permitted. If the task is now resolved, the next step may be to mark the parent task complete with COMPLETE_TASK."
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": "Permission denied or WA required"
            })
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(follow_up)
            return
        memory_service: Optional[MemoryService] = await self.get_memory_service()

        if not memory_service:
            logger.error("ForgetHandler: MemoryService not available")
            follow_up = create_follow_up_thought(
                parent=thought,
                content=f"FORGET action failed: MemoryService unavailable for thought {thought_id}"
            )
            persistence.add_thought(follow_up)
            await self._audit_log(
                HandlerActionType.FORGET,
                {**dispatch_context, "thought_id": thought_id},
                outcome="failed_no_memory_service",
            )
            return

        node = params.node
        scope = node.scope
        if scope in (GraphScope.IDENTITY, GraphScope.ENVIRONMENT) and not dispatch_context.get("wa_authorized"):
            follow_up = create_follow_up_thought(
                parent=thought,
                content="FORGET action denied: WA authorization required"
            )
            context_data = follow_up.context.model_dump() if follow_up.context else {}
            context_data.update({
                "action_performed": HandlerActionType.FORGET.name,
                "parent_task_id": thought.source_task_id,
                "is_follow_up": True,
                "error": "wa_denied",
            })
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(follow_up)
            await self._audit_log(
                HandlerActionType.FORGET,
                {**dispatch_context, "thought_id": thought_id},
                outcome="wa_denied",
            )
            return

        forget_result = await memory_service.forget(node)
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
        follow_up = create_follow_up_thought(
            parent=thought,
            content=ThoughtStatus.PENDING,
        )
        context_data = follow_up.context.model_dump() if follow_up.context else {}
        context_data.update({
            "action_performed": HandlerActionType.FORGET.name,
            "parent_task_id": thought.source_task_id,
            "is_follow_up": True,
            "forget_key": node.id,
            "forget_scope": node.scope.value,
            "forget_status": str(getattr(forget_result, "status", forget_result))
        })
        from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
        follow_up.context = ThoughtContext.model_validate(context_data)
        persistence.add_thought(follow_up)
        await self._audit_log(
            HandlerActionType.FORGET,
            {**dispatch_context, "thought_id": thought_id},
            outcome="success" if success else "failed",
        )

    def _can_forget(self, params, dispatch_context: dict) -> bool:
        if hasattr(params, 'node') and hasattr(params.node, 'scope'):
            scope = params.node.scope
            if scope in (GraphScope.IDENTITY, GraphScope.ENVIRONMENT):
                return dispatch_context.get("wa_authorized", False)
        return True

    async def _audit_forget_operation(self, params, dispatch_context, result) -> None:
        if hasattr(params, 'no_audit') and params.no_audit:
            return
            
        audit_data = {
            "forget_key": params.node.id,
            "forget_scope": params.node.scope.value,
            "operation_result": str(result.status) if hasattr(result, 'status') else str(result),
            "timestamp": dispatch_context.get("timestamp"),
            "thought_id": dispatch_context.get("thought_id")
        }
        
        await self._audit_log(
            HandlerActionType.FORGET,
            {**dispatch_context, **audit_data},
            outcome="forget_executed"
        )
