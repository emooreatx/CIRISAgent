"""
Thought depth conscience that enforces maximum action chain length.

When a thought reaches the maximum allowed depth, this conscience
overrides the action to DEFER, ensuring proper escalation to humans.
"""

import logging
from typing import Optional

from ciris_engine.schemas.dma.results import ActionSelectionDMAResult
from ciris_engine.schemas.conscience.core import ConscienceCheckResult, ConscienceStatus
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.actions import DeferParams
from ciris_engine.logic.conscience.interface import ConscienceInterface
# TODO: Refactor to use dependency injection instead of get_config
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class ThoughtDepthconscience(ConscienceInterface):
    """Enforces maximum thought depth by deferring when limit is reached."""
    
    def __init__(self, time_service: TimeServiceProtocol, max_depth: Optional[int] = None):
        """Initialize with time service and configurable max depth."""
        self._time_service = time_service
        if max_depth is None:
            try:
                max_depth = get_config().workflow.max_rounds
            except Exception:
                max_depth = 7
        self.max_depth = max_depth
        logger.info(f"ThoughtDepthconscience initialized with max_depth={self.max_depth}")
    
    async def check(
        self,
        action: ActionSelectionDMAResult,
        context: dict,
    ) -> ConscienceCheckResult:
        """Check if thought depth exceeds maximum allowed."""
        timestamp = self._time_service.now()
        
        # Get the thought from context
        thought = context.get("thought")
        if not thought:
            logger.warning("No thought provided to ThoughtDepthconscience")
            from ciris_engine.schemas.conscience.core import EpistemicData
            return ConscienceCheckResult(
                status=ConscienceStatus.PASSED,
                passed=True,
                check_timestamp=timestamp,
                epistemic_data=EpistemicData(
                    entropy_level=0.5,
                    coherence_level=0.5,
                    uncertainty_acknowledged=True,
                    reasoning_transparency=0.0
                ),
                reason="No thought provided to check"
            )
        
        current_depth = getattr(thought, "thought_depth", 0)
        
        # Terminal actions don't count toward depth limit
        terminal_actions = {
            HandlerActionType.DEFER.value,
            HandlerActionType.REJECT.value, 
            HandlerActionType.TASK_COMPLETE.value
        }
        
        if action.selected_action in terminal_actions:
            return ConscienceCheckResult(
                status=ConscienceStatus.PASSED,
                passed=True,
                check_timestamp=timestamp,
                epistemic_data=EpistemicData(
                    entropy_level=0.5,
                    coherence_level=0.9,  # Terminal actions are coherent
                    uncertainty_acknowledged=True,
                    reasoning_transparency=0.8
                ),
                reason=f"Terminal action {action.selected_action} at depth {current_depth}"
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
                    "original_action": action.selected_action,  # It's already a string
                    "auto_deferred": True
                },
                defer_until=None  # No specific time, defer indefinitely
            )
            
            # Create the defer action that will replace the original
            defer_action = ActionSelectionDMAResult(
                selected_action=HandlerActionType.DEFER.value,
                action_parameters=None,  # No parameters needed
                selection_reasoning=f"Automatically deferred: Maximum thought depth of {self.max_depth} reached",
                selection_confidence=1.0,
                # Add required fields for ActionSelectionDMAResult
                pdma_weight=1.0,
                csdma_weight=0.0,
                dsdma_weight=0.0,
                actions_considered=[HandlerActionType.DEFER.value],
                selection_ethical_score=1.0,
                selection_fairness=1.0,
                selection_principles=["Safety", "Prudence"],
                total_evaluation_time_ms=0.0
            )
            
            return ConscienceCheckResult(
                status=ConscienceStatus.FAILED,
                passed=False,
                reason=f"Maximum thought depth ({self.max_depth}) reached - deferring to human",
                check_timestamp=timestamp,
                epistemic_data=EpistemicData(
                    entropy_level=0.8,  # High uncertainty at max depth
                    coherence_level=0.3,  # Low coherence when forced to stop
                    uncertainty_acknowledged=True,
                    reasoning_transparency=0.9  # Very transparent about why
                )
            )
        
        # Depth is within limits
        return ConscienceCheckResult(
            status=ConscienceStatus.PASSED,
            passed=True,
            check_timestamp=timestamp,
            epistemic_data=EpistemicData(
                entropy_level=0.5,
                coherence_level=0.8,  # Good coherence within limits
                uncertainty_acknowledged=True,
                reasoning_transparency=0.7
            ),
            reason=f"Thought depth {current_depth} within limit of {self.max_depth}"
        )