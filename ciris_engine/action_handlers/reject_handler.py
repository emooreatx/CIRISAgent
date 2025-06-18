import logging
from typing import Dict, Any
from datetime import datetime, timezone
import re

from ciris_engine.schemas import Thought, RejectParams, ThoughtStatus, TaskStatus, HandlerActionType, ActionSelectionResult, DispatchContext, ServiceType
from ciris_engine.schemas.context_schemas_v1 import ThoughtContext, SystemSnapshot
from ciris_engine.utils.channel_utils import extract_channel_id
from ciris_engine.schemas.filter_schemas_v1 import FilterTrigger, TriggerType, FilterPriority
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.action_params_v1 import MemorizeParams
from ciris_engine.schemas.agent_core_schemas_v1 import Task, ThoughtType
from ciris_engine import persistence
from .base_handler import BaseActionHandler
from .helpers import create_follow_up_thought
from .exceptions import FollowUpCreationError

logger = logging.getLogger(__name__)


class RejectHandler(BaseActionHandler):
    async def handle(
        self,
        result: ActionSelectionResult,
        thought: Thought,
        dispatch_context: DispatchContext
    ) -> None:
        raw_params = result.action_parameters
        thought_id = thought.thought_id
        parent_task_id = thought.source_task_id
        await self._audit_log(HandlerActionType.REJECT, dispatch_context.model_copy(update={"thought_id": thought_id}), outcome="start")
        original_event_channel_id = extract_channel_id(dispatch_context.channel_context)

        try:
            params = await self._validate_and_convert_params(raw_params, RejectParams)
        except Exception as e:
            await self._handle_error(HandlerActionType.REJECT, dispatch_context, thought_id, e)
            final_thought_status = ThoughtStatus.FAILED
            await self._audit_log(HandlerActionType.REJECT, {**dispatch_context.model_dump(), "thought_id": thought_id}, outcome="failed")
            persistence.update_thought_status(
                thought_id=thought_id,
                status=final_thought_status,
                final_action=result,
            )
            return
        final_thought_status = ThoughtStatus.FAILED 
        action_performed_successfully = False
        follow_up_content_key_info = f"REJECT action for thought {thought_id}"

        if not isinstance(params, RejectParams):
            self.logger.error(f"REJECT action params are not RejectParams model. Type: {type(params)}. Thought ID: {thought_id}")
            follow_up_content_key_info = f"REJECT action failed: Invalid parameters type ({type(params)}) for thought {thought_id}. Original reason might be lost."
        else:
            follow_up_content_key_info = f"Rejected thought {thought_id}. Reason: {params.reason}"
            if original_event_channel_id and params.reason:
                comm_service = await self.get_communication_service()
                if comm_service:
                    try:
                        await comm_service.send_message(original_event_channel_id, f"Unable to proceed: {params.reason}")
                    except Exception as e:
                        self.logger.error(
                            f"Failed to send REJECT notification via communication service for thought {thought_id}: {e}"
                        )
        persistence.update_thought_status(
            thought_id=thought_id,
            status=final_thought_status,
            final_action=result,
        )
        if parent_task_id:
            persistence.update_task_status(parent_task_id, TaskStatus.REJECTED)
        self.logger.info(f"Updated original thought {thought_id} to status {final_thought_status.value} for REJECT action. Info: {follow_up_content_key_info}")

        # Handle adaptive filtering if requested
        if isinstance(params, RejectParams) and params.create_filter:
            await self._create_adaptive_filter(params, thought, dispatch_context)

        # REJECT is a terminal action - no follow-up thoughts should be created
        self.logger.info(f"REJECT action completed for thought {thought_id}. This is a terminal action.")
        await self._audit_log(HandlerActionType.REJECT, {**dispatch_context.model_dump(), "thought_id": thought_id}, outcome="success")

    async def _create_adaptive_filter(self, params: RejectParams, thought: Thought, dispatch_context: DispatchContext) -> None:
        """Create an adaptive filter based on the rejected content."""
        try:
            # Get the adaptive filter service
            if not self.dependencies.service_registry:
                self.logger.warning("No service registry available")
                return
                
            adaptive_filter_service = await self.dependencies.service_registry.get_service(
                handler=self.__class__.__name__,
                service_type=ServiceType.FILTER
            )
            if not adaptive_filter_service:
                self.logger.warning("Adaptive filter service not available, cannot create filter")
                return

            # Determine the filter pattern
            filter_pattern = params.filter_pattern
            if not filter_pattern:
                # Try to extract a pattern from the thought content
                if hasattr(thought, 'content') and thought.content:
                    # Extract key phrases or patterns from the rejected content
                    content_lower = thought.content.lower()
                    # Look for common malicious patterns
                    if any(phrase in content_lower for phrase in ["jailbreak", "ignore instructions", "system prompt", "disregard"]):
                        filter_pattern = r"(jailbreak|ignore.*instructions|system.*prompt|disregard.*above)"
                    else:
                        # Create a simple keyword pattern from the first few words
                        words = re.findall(r'\w+', thought.content)[:5]
                        if words:
                            filter_pattern = '|'.join(re.escape(word) for word in words)
                        else:
                            filter_pattern = re.escape(thought.content[:50])

            if not filter_pattern:
                self.logger.warning(f"Could not determine filter pattern for rejected thought {thought.thought_id}")
                return

            # Map string priority to enum
            priority_map = {
                "critical": FilterPriority.CRITICAL,
                "high": FilterPriority.HIGH,
                "medium": FilterPriority.MEDIUM,
                "low": FilterPriority.LOW
            }
            filter_priority = priority_map.get(params.filter_priority or "high", FilterPriority.HIGH)

            # Map string type to enum
            type_map = {
                "regex": TriggerType.REGEX,
                "semantic": TriggerType.SEMANTIC,
                "keyword": TriggerType.REGEX  # Keywords are implemented as regex
            }
            filter_type = type_map.get(params.filter_type or "regex", TriggerType.REGEX)

            # Create the filter trigger
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            filter_trigger = FilterTrigger(
                trigger_id=f"reject_auto_{timestamp}_{thought.thought_id[:8]}",
                name=f"auto_reject_{params.reason[:20].replace(' ', '_')}",
                pattern_type=filter_type,
                pattern=filter_pattern,
                priority=filter_priority,
                description=f"Auto-created from REJECT: {params.reason}",
                learned_from=thought.thought_id,
                created_by="reject_handler"
            )

            # Add the filter to the service
            # Check if it's a coroutine or method
            if hasattr(adaptive_filter_service, 'add_filter_trigger'):
                added = await adaptive_filter_service.add_filter_trigger(filter_trigger, "review")
            else:
                self.logger.error("Adaptive filter service doesn't have add_filter_trigger method")
                return
            
            if added:
                self.logger.info(f"Created adaptive filter {filter_trigger.trigger_id} from rejected thought {thought.thought_id}")
                
                # Create a MEMORIZE task to ensure the filter is persisted
                import uuid
                from datetime import datetime, timezone
                
                memorize_task = Task(
                    task_id=str(uuid.uuid4()),
                    description=f"Memorize adaptive filter created from rejection: {params.reason}",
                    status=TaskStatus.PENDING,
                    priority=1,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    context=ThoughtContext(
                        system_snapshot=SystemSnapshot(
                            channel_context=dispatch_context.channel_context
                        ),
                        user_profiles={},
                        task_history=[]
                    )
                )
                # Add extra context after creation
                setattr(memorize_task.context, 'filter_id', filter_trigger.trigger_id)
                setattr(memorize_task.context, 'filter_pattern', filter_pattern)
                setattr(memorize_task.context, 'rejection_reason', params.reason)
                setattr(memorize_task.context, 'original_thought_id', thought.thought_id)
                
                persistence.add_task(memorize_task)
                
                # Create a thought for the memorize task
                memorize_thought = Thought(
                    thought_id=str(uuid.uuid4()),
                    thought_type=ThoughtType.OBSERVATION,
                    content=f"Memorize adaptive filter to prevent future occurrences of: {params.reason}",
                    source_task_id=memorize_task.task_id,
                    status=ThoughtStatus.PROCESSING,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    updated_at=datetime.now(timezone.utc).isoformat(),
                    round_number=0,
                    context=ThoughtContext(
                        system_snapshot=SystemSnapshot(
                            channel_context=dispatch_context.channel_context
                        ),
                        user_profiles={},
                        task_history=[]
                    )
                )
                # Add extra context
                setattr(memorize_thought.context, 'action', 'MEMORIZE')
                setattr(memorize_thought.context, 'filter_data', filter_trigger.model_dump())
                setattr(memorize_thought.context, 'source', 'reject_handler')
                
                persistence.add_thought(memorize_thought)
                self.logger.info(f"Created MEMORIZE task {memorize_task.task_id} for filter persistence")
            else:
                self.logger.error(f"Failed to add adaptive filter for rejected thought {thought.thought_id}")
                
        except Exception as e:
            self.logger.error(f"Error creating adaptive filter for rejected thought {thought.thought_id}: {e}", exc_info=True)