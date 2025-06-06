"""
Play processor for creative and experimental processing.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from ciris_engine.schemas.states_v1 import AgentState

from .work_processor import WorkProcessor

logger = logging.getLogger(__name__)


class PlayProcessor(WorkProcessor):
    """
    Handles the PLAY state for creative and experimental processing.
    
    Currently inherits from WorkProcessor but can be customized for:
    - Creative task prioritization
    - Experimental prompt variations
    - Less constrained processing
    - Learning through exploration
    """
    
    def __init__(self, *args, **kwargs) -> None:
        """Initialize play processor."""
        super().__init__(*args, **kwargs)
        self.play_metrics = {
            "creative_tasks_processed": 0,
            "experiments_run": 0,
            "novel_approaches_tried": 0
        }
    
    def get_supported_states(self) -> List[AgentState]:
        """Play processor only handles PLAY state."""
        return [AgentState.PLAY]
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        """
        Execute one round of play processing.
        Currently delegates to work processing but logs differently.
        """
        logger.info(f"--- Starting Play Round {round_number} (Creative Mode) ---")
        
        result = await super().process(round_number)
        
        result["mode"] = "play"
        result["creativity_enabled"] = True
        
        
        self.play_metrics["creative_tasks_processed"] += result.get("thoughts_processed", 0)
        
        logger.info(
            f"--- Finished Play Round {round_number} "
            f"(Processed: {result.get('thoughts_processed', 0)} creative thoughts) ---"
        )
        
        return result
    
    def get_play_stats(self) -> Dict[str, Any]:
        """Get play-specific statistics."""
        base_stats = self.get_work_stats()
        base_stats.update({
            "play_metrics": self.play_metrics.copy(),
            "mode": "play",
            "creativity_level": self._calculate_creativity_level()
        })
        return base_stats
    
    def _calculate_creativity_level(self) -> float:
        """
        Calculate a creativity level based on play metrics.
        Returns a value between 0.0 and 1.0.
        """
        if self.play_metrics["creative_tasks_processed"] == 0:
            return 0.0
        
        # Simple formula - can be made more sophisticated
        experiments_ratio = (
            self.play_metrics["experiments_run"] / 
            max(self.play_metrics["creative_tasks_processed"], 1)
        )
        
        novel_ratio = (
            self.play_metrics["novel_approaches_tried"] / 
            max(self.play_metrics["creative_tasks_processed"], 1)
        )
        
        return min((experiments_ratio + novel_ratio) / 2, 1.0)
    
    async def _prioritize_creative_tasks(self, tasks: List[Any]) -> List[Any]:
        """
        Prioritize tasks that are marked as creative or experimental.
        
        Future implementation could:
        - Look for tasks with creative tags
        - Boost priority of experimental tasks
        - Prefer tasks that allow exploration
        """
        # For now, return tasks as-is
        return tasks
    
    def should_experiment(self, thought_content: str) -> bool:
        """
        Determine if we should try an experimental approach.
        
        Args:
            thought_content: The content of the thought being processed
            
        Returns:
            True if experimental approach should be tried
        """
        # Future implementation could analyze thought content
        # and decide when to try novel approaches
        
        # Simple heuristic for now - experiment 20% of the time
        import random
        return random.random() < 0.2