"""
Thought depth guardrail that enforces maximum action chain length.

When a thought reaches the maximum allowed depth, this guardrail
overrides the action to DEFER, ensuring proper escalation to humans.
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.guardrails_schemas_v1 import GuardrailCheckResult, GuardrailStatus
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.action_params_v1 import DeferParams
from ciris_engine.guardrails.interface import GuardrailInterface
from ciris_engine.config.config_manager import get_config

logger = logging.getLogger(__name__)


class ThoughtDepthGuardrail(GuardrailInterface):
    """Enforces maximum thought depth by deferring when limit is reached."""
    
    def __init__(self, max_depth: Optional[int] = None):
        """Initialize with configurable max depth."""
        if max_depth is None:
            try:
                max_depth = get_config().workflow.max_rounds
            except Exception:
                max_depth = 7
        self.max_depth = max_depth
        logger.info(f"ThoughtDepthGuardrail initialized with max_depth={self.max_depth}")
    
    async def check(
        self,
        action: ActionSelectionResult,
        context: Dict[str, Any],
    ) -> GuardrailCheckResult:
        """Check if thought depth exceeds maximum allowed."""
        timestamp = datetime.now(timezone.utc).isoformat()
        
        # Get the thought from context
        thought = context.get("thought")
        if not thought:
            logger.warning("No thought provided to ThoughtDepthGuardrail")
            return GuardrailCheckResult(
                status=GuardrailStatus.PASSED,
                passed=True,
                check_timestamp=timestamp,
                epistemic_data={"error": "No thought in context"}
            )
        
        current_depth = getattr(thought, "thought_depth", 0)
        
        # Terminal actions don't count toward depth limit
        terminal_actions = {
            HandlerActionType.DEFER,
            HandlerActionType.REJECT, 
            HandlerActionType.TASK_COMPLETE
        }
        
        if action.selected_action in terminal_actions:
            return GuardrailCheckResult(
                status=GuardrailStatus.PASSED,
                passed=True,
                check_timestamp=timestamp,
                epistemic_data={
                    "thought_depth": current_depth,
                    "max_depth": self.max_depth,
                    "action": action.selected_action.value,
                    "is_terminal": True
                }
            )
        
        # Check if we're at or beyond max depth
        if current_depth >= self.max_depth:
            logger.warning(
                f"Thought {thought.thought_id} at depth {current_depth} "
                f"exceeds max depth {self.max_depth}. Forcing DEFER."
            )
            
            # Create defer parameters
            defer_params = DeferParams(
                reason=f"Maximum action depth ({self.max_depth}) reached. "
                       f"This task requires human guidance to proceed further.",
                context={
                    "thought_depth": current_depth,
                    "original_action": action.selected_action.value,
                    "auto_deferred": True
                },
                defer_until=None  # No specific time, defer indefinitely
            )
            
            # Create the defer action that will replace the original
            defer_action = ActionSelectionResult(
                selected_action=HandlerActionType.DEFER,
                action_parameters=defer_params.model_dump(mode='json'),
                rationale=f"Automatically deferred: Maximum thought depth of {self.max_depth} reached",
                confidence=1.0
            )
            
            return GuardrailCheckResult(
                status=GuardrailStatus.FAILED,
                passed=False,
                reason=f"Maximum thought depth ({self.max_depth}) reached - deferring to human",
                check_timestamp=timestamp,
                epistemic_data={
                    "thought_depth": current_depth,
                    "max_depth": self.max_depth,
                    "original_action": action.selected_action.value,
                    "replacement_action": defer_action.model_dump()
                }
            )
        
        # Depth is within limits
        return GuardrailCheckResult(
            status=GuardrailStatus.PASSED,
            passed=True,
            check_timestamp=timestamp,
            epistemic_data={
                "thought_depth": current_depth,
                "max_depth": self.max_depth,
                "remaining_actions": self.max_depth - current_depth
            }
        )