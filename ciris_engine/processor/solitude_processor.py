"""
Solitude processor for minimal processing and reflection state.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from ciris_engine.schemas.states_v1 import AgentState
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus
from ciris_engine import persistence

from .base_processor import BaseProcessor

logger = logging.getLogger(__name__)


class SolitudeProcessor(BaseProcessor):
    """
    Handles the SOLITUDE state for minimal processing and reflection.
    In this state, the agent:
    - Only responds to critical/high-priority tasks
    - Performs maintenance and cleanup
    - Reflects on past activities
    - Conserves resources
    """
    
    def __init__(self, *args, critical_priority_threshold: int = 8, **kwargs) -> None:
        """
        Initialize solitude processor.
        
        Args:
            critical_priority_threshold: Minimum priority to consider a task critical
        """
        super().__init__(*args, **kwargs)
        self.critical_priority_threshold = critical_priority_threshold
        self.reflection_data = {
            "tasks_reviewed": 0,
            "thoughts_reviewed": 0,
            "memories_consolidated": 0,
            "cleanup_performed": False
        }
    
    def get_supported_states(self) -> List[AgentState]:
        """Solitude processor only handles SOLITUDE state."""
        return [AgentState.SOLITUDE]
    
    async def can_process(self, state: AgentState) -> bool:
        """Check if we can process the given state."""
        return state == AgentState.SOLITUDE
    
    async def process(self, round_number: int) -> Dict[str, Any]:
        """
        Execute solitude processing.
        Performs minimal work focusing on critical tasks and maintenance.
        """
        logger.info(f"Solitude round {round_number}: Minimal processing mode")
        
        result = {
            "round_number": round_number,
            "critical_tasks_found": 0,
            "maintenance_performed": False,
            "should_exit_solitude": False,
            "reflection_summary": {}
        }
        
        try:
            critical_count = await self._check_critical_tasks()
            result["critical_tasks_found"] = critical_count
            
            if critical_count > 0:
                logger.info(f"Found {critical_count} critical tasks")
                result["should_exit_solitude"] = True
                return result
            
            if round_number % 10 == 0:
                maintenance_result = await self._perform_maintenance()
                result["maintenance_performed"] = True
                result["maintenance_summary"] = maintenance_result
            
            if round_number % 5 == 0:
                reflection_result = await self._reflect_and_learn()
                result["reflection_summary"] = reflection_result
            
            exit_conditions = await self._check_exit_conditions()
            result["should_exit_solitude"] = exit_conditions["should_exit"]
            result["exit_reason"] = exit_conditions.get("reason")
            
            self.metrics["rounds_completed"] += 1
            
        except Exception as e:
            logger.error(f"Error in solitude round {round_number}: {e}", exc_info=True)
            self.metrics["errors"] += 1
            result["error"] = str(e)
        
        return result
    
    async def _check_critical_tasks(self) -> int:
        """Check for critical tasks that require immediate attention."""
        # Get pending tasks ordered by priority
        pending_tasks = persistence.get_pending_tasks_for_activation(limit=20)
        
        critical_count = 0
        for task in pending_tasks:
            if task.priority >= self.critical_priority_threshold:
                critical_count += 1
                logger.info(
                    f"Critical task found: {task.task_id} "
                    f"(Priority: {task.priority}) - {task.description}"
                )
        
        return critical_count
    
    async def _perform_maintenance(self) -> Dict[str, Any]:
        """Perform system maintenance tasks."""
        logger.info("Performing maintenance tasks")
        
        maintenance_result = {
            "old_completed_tasks_cleaned": 0,
            "old_thoughts_cleaned": 0,
            "database_optimized": False
        }
        
        try:
            cutoff_date = datetime.now(timezone.utc)
            cutoff_date = cutoff_date.replace(day=cutoff_date.day - 7)
            
            old_tasks = persistence.get_tasks_older_than(cutoff_date.isoformat())
            completed_old = [t for t in old_tasks if t.status == TaskStatus.COMPLETED]
            
            if completed_old:
                task_ids = [t.task_id for t in completed_old]
                deleted = persistence.delete_tasks_by_ids(task_ids)
                maintenance_result["old_completed_tasks_cleaned"] = deleted
                logger.info(f"Cleaned up {deleted} old completed tasks")
            
            old_thoughts = persistence.get_thoughts_older_than(cutoff_date.isoformat())
            if old_thoughts:
                thought_ids = [t.thought_id for t in old_thoughts]
                deleted = persistence.delete_thoughts_by_ids(thought_ids)
                maintenance_result["old_thoughts_cleaned"] = deleted
                logger.info(f"Cleaned up {deleted} old thoughts")
            
            self.reflection_data["cleanup_performed"] = True
            
        except Exception as e:
            logger.error(f"Error during maintenance: {e}")
        
        return maintenance_result
    
    async def _reflect_and_learn(self) -> Dict[str, Any]:
        """
        Perform reflection and learning activities.
        This could include analyzing patterns, consolidating memories, etc.
        """
        logger.info("Performing reflection and learning")
        
        reflection_result = {
            "recent_tasks_analyzed": 0,
            "patterns_identified": [],
            "memories_consolidated": 0
        }
        
        try:
            recent_completed = persistence.get_recent_completed_tasks(limit=20)
            reflection_result["recent_tasks_analyzed"] = len(recent_completed)
            
            task_types: Dict[str, Any] = {}
            for task in recent_completed:
                task_type = task.context.get("type", "unknown") if task.context else "unknown"
                task_types[task_type] = task_types.get(task_type, 0) + 1
            
            if task_types:
                most_common = max(task_types.items(), key=lambda x: x[1])
                reflection_result["patterns_identified"].append({
                    "pattern": "most_common_task_type",
                    "value": most_common[0],
                    "count": most_common[1]
                })
            
            self.reflection_data["tasks_reviewed"] += len(recent_completed)
            
            if self.services.get("memory_service"):
                reflection_result["memories_consolidated"] = 0
            
        except Exception as e:
            logger.error(f"Error during reflection: {e}")
        
        return reflection_result
    
    async def _check_exit_conditions(self) -> Dict[str, Any]:
        """
        Check if conditions warrant exiting solitude state.
        
        Returns:
            Dict with 'should_exit' bool and optional 'reason' string
        """
        conditions = {"should_exit": False, "reason": None}
        
        
        state_duration = 0
        if hasattr(self, 'state_manager'):
            state_duration = self.state_manager.get_state_duration()
        
        if state_duration > 1800:
            conditions["should_exit"] = True
            conditions["reason"] = "Maximum solitude duration reached"
            return conditions
        
        pending_count = persistence.count_tasks(TaskStatus.PENDING)
        if pending_count > 5:
            conditions["should_exit"] = True
            conditions["reason"] = f"Accumulated {pending_count} pending tasks"
            return conditions
        
        
        return conditions
    
    def get_solitude_stats(self) -> Dict[str, Any]:
        """Get statistics about solitude processing."""
        return {
            "reflection_data": self.reflection_data.copy(),
            "critical_threshold": self.critical_priority_threshold,
            "total_rounds": self.metrics.get("rounds_completed", 0),
            "cleanup_performed": self.reflection_data.get("cleanup_performed", False)
        }