import logging
from typing import Dict, Any, Optional


from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus, HandlerActionType, DispatchContext
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine import persistence
from ciris_engine.protocols.services import MemoryService
from ciris_engine.services.memory_service import MemoryOpStatus
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class MemorizeHandler(BaseActionHandler):

    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="start")
        final_thought_status = ThoughtStatus.COMPLETED
        action_performed_successfully = False
        follow_up_content_key_info = f"MEMORIZE action for thought {thought_id}"

        try:
            params = await self._validate_and_convert_params(raw_params, MemorizeParams)
        except Exception as e:
            if isinstance(raw_params, dict) and "knowledge_unit_description" in raw_params:
                from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
                scope = GraphScope(raw_params.get("scope", "local"))
                node = GraphNode(
                    id=raw_params.get("knowledge_unit_description", "memory"),
                    type=NodeType.CONCEPT if scope == GraphScope.IDENTITY else NodeType.USER,
                    scope=scope,
                    attributes={"value": raw_params.get("knowledge_data", {})}
                )
                params = MemorizeParams(node=node)
            else:
                logger.error(f"Invalid memorize params: {e}")
                await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = f"MEMORIZE action failed: {e}"
                persistence.update_thought_status(
                    thought_id=thought_id,
                    status=final_thought_status,
                    final_action=result,
                )
                return

        from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope

        memory_service: Optional[MemoryService] = await self.get_memory_service()

        if not memory_service:
            self.logger.error(
                f"MemoryService not available. Cannot perform MEMORIZE for thought {thought_id}"
            )
            final_thought_status = ThoughtStatus.FAILED
            follow_up_content_key_info = (
                f"MEMORIZE action failed: MemoryService unavailable for thought {thought_id}."
            )
            await self._audit_log(
                HandlerActionType.MEMORIZE,
                {**dispatch_context, "thought_id": thought_id},
                outcome="failed_no_memory_service",
            )
        else:
            scope = params.node.scope  # type: ignore[attr-defined]
            node = params.node  # type: ignore[attr-defined]
            
            # Check if this is an identity graph node
            is_identity_node = (
                scope == GraphScope.IDENTITY or 
                node.id.startswith("agent/identity") or
                node.type == NodeType.AGENT
            )
            
            if is_identity_node:
                # Identity changes require WA approval
                if not dispatch_context.wa_authorized:
                    self.logger.warning(
                        f"WA authorization required for MEMORIZE to identity graph. Thought {thought_id} denied."
                    )
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = "WA authorization required for identity changes"
                else:
                    # Check variance if updating existing identity
                    variance_check_passed = True
                    if node.id == "agent/identity":
                        variance_pct = await self._check_identity_variance(node, memory_service)
                        if variance_pct > 0.2:  # 20% threshold
                            self.logger.warning(
                                f"Identity change variance {variance_pct:.1%} exceeds 20% threshold. "
                                f"Agent should reconsider this change."
                            )
                            # Add guidance to the follow-up
                            follow_up_content_key_info = (
                                f"WARNING: Proposed identity change represents {variance_pct:.1%} variance. "
                                "Changes exceeding 20% should be carefully reconsidered. "
                                "Large identity shifts may destabilize agent coherence."
                            )
                            variance_check_passed = False
                    
                    if variance_check_passed:
                        # Proceed with identity update
                        node.attributes.setdefault("source", thought.source_task_id)
                        node.attributes["wa_approved_by"] = dispatch_context.wa_authorized
                        node.attributes["approval_timestamp"] = dispatch_context.event_timestamp
                        
                        try:
                            mem_op = await memory_service.memorize(node)
                            if mem_op.status == MemoryOpStatus.OK:
                                action_performed_successfully = True
                                follow_up_content_key_info = (
                                    f"Identity update successful. Node: '{node.id}'"
                                )
                            else:
                                final_thought_status = ThoughtStatus.DEFERRED
                                follow_up_content_key_info = mem_op.reason or mem_op.error or "Identity update failed"
                        except Exception as e_mem:
                            await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e_mem)
                            final_thought_status = ThoughtStatus.FAILED
                            follow_up_content_key_info = f"Exception during identity update: {e_mem}"
            
            elif scope in (GraphScope.ENVIRONMENT,) and not dispatch_context.wa_authorized:
                # Environment scope also requires WA approval
                self.logger.warning(
                    f"WA authorization required for MEMORIZE in scope {scope}. Thought {thought_id} denied."
                )
                final_thought_status = ThoughtStatus.FAILED
                follow_up_content_key_info = "WA authorization missing"
            else:
                # Regular memory operation
                node.attributes.setdefault("source", thought.source_task_id)
                try:
                    mem_op = await memory_service.memorize(node)
                    if mem_op.status == MemoryOpStatus.OK:
                        action_performed_successfully = True
                        follow_up_content_key_info = (
                            f"Memorization successful. Key: '{node.id}'"
                        )
                    else:
                        final_thought_status = ThoughtStatus.DEFERRED
                        follow_up_content_key_info = mem_op.reason or mem_op.error or "Memory operation failed"
                except Exception as e_mem:
                    await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e_mem)
                    final_thought_status = ThoughtStatus.FAILED
                    follow_up_content_key_info = f"Exception during memory operation: {e_mem}"

        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        self.logger.debug(f"Updated original thought {thought_id} to status {final_thought_status.value} after MEMORIZE attempt.")

        follow_up_text = ""
        if action_performed_successfully:
            follow_up_text = (
                f"CIRIS_FOLLOW_UP_THOUGHT: Memorization successful for original thought {thought_id} (Task: {thought.source_task_id}). "
                f"Info: {follow_up_content_key_info}. "
                "Consider informing the user with SPEAK or select TASK_COMPLETE if the overall task is finished."
            )
        else:
            follow_up_text = f"CIRIS_FOLLOW_UP_THOUGHT: MEMORIZE action for thought {thought_id} resulted in status {final_thought_status.value}. Info: {follow_up_content_key_info}. Review and determine next steps."

        try:
            new_follow_up = create_follow_up_thought(
                parent=thought,
                content=ThoughtStatus.PENDING,
            )

            context_data = new_follow_up.context.model_dump() if new_follow_up.context else {}
            context_for_follow_up = {
                "action_performed": HandlerActionType.MEMORIZE.value
            }
            if final_thought_status != ThoughtStatus.COMPLETED:
                context_for_follow_up["error_details"] = follow_up_content_key_info

            context_for_follow_up["action_params"] = result.action_parameters
            context_data.update(context_for_follow_up)
            from ciris_engine.schemas.context_schemas_v1 import ThoughtContext
            new_follow_up.context = ThoughtContext.model_validate(context_data)
            persistence.add_thought(new_follow_up)
            self.logger.info(
                f"Created follow-up thought {new_follow_up.thought_id} for original thought {thought_id} after MEMORIZE action."
            )
            await self._audit_log(HandlerActionType.MEMORIZE, {**dispatch_context, "thought_id": thought_id}, outcome="success")
        except Exception as e:
            await self._handle_error(HandlerActionType.MEMORIZE, dispatch_context, thought_id, e)
            raise FollowUpCreationError from e
    
    async def _check_identity_variance(self, proposed_node: Any, memory_service: MemoryService) -> float:
        """Calculate variance between current and proposed identity."""
        try:
            # Retrieve current identity
            from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
            current_node = GraphNode(
                id="agent/identity",
                type=NodeType.AGENT,
                scope=GraphScope.IDENTITY
            )
            result = await memory_service.recall(current_node)
            
            if not result or not result.nodes:
                # No existing identity, this is first creation
                return 0.0
            
            current_identity = result.nodes[0].attributes.get("identity", {})
            proposed_identity = proposed_node.attributes.get("identity", {})
            
            # Calculate variance across key identity attributes
            variance_points = 0.0
            total_points = 0.0
            
            # Core attributes with weights
            attribute_weights = {
                "agent_id": 5.0,  # Changing name is very significant
                "core_profile.description": 3.0,
                "core_profile.role_description": 3.0,
                "core_profile.dsdma_identifier": 4.0,  # Changing domain is major
                "allowed_capabilities": 2.0,
                "restricted_capabilities": 2.0,
            }
            
            for attr_path, weight in attribute_weights.items():
                current_val = self._get_nested_value(current_identity, attr_path)
                proposed_val = self._get_nested_value(proposed_identity, attr_path)
                
                if current_val != proposed_val:
                    variance_points += weight
                total_points += weight
            
            # Check override changes
            for override_type in ['dsdma_overrides', 'csdma_overrides', 'action_selection_pdma_overrides']:
                current_overrides = self._get_nested_value(current_identity, f"core_profile.{override_type}") or {}
                proposed_overrides = self._get_nested_value(proposed_identity, f"core_profile.{override_type}") or {}
                
                # Count changed keys
                all_keys = set(current_overrides.keys()) | set(proposed_overrides.keys())
                changed_keys = sum(1 for key in all_keys if current_overrides.get(key) != proposed_overrides.get(key))
                
                if all_keys:
                    variance_points += (changed_keys / len(all_keys)) * 2.0
                total_points += 2.0
            
            return variance_points / total_points if total_points > 0 else 0.0
            
        except Exception as e:
            self.logger.error(f"Error calculating identity variance: {e}")
            # On error, return high variance to be safe
            return 1.0
    
    def _get_nested_value(self, data: Dict[str, Any], path: str) -> Any:
        """Get value from nested dict using dot notation."""
        parts = path.split('.')
        value = data
        for part in parts:
            if isinstance(value, dict):
                value = value.get(part)
            else:
                return None
        return value
