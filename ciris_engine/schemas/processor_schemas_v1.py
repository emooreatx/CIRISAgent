"""
Processor schemas for CIRIS Engine.

Provides strongly-typed results and metrics for all processor types,
eliminating Dict[str, Any] usage for security and self-awareness.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from datetime import datetime
from enum import Enum

from .versioning import SchemaVersion
from .states_v1 import AgentState
from .foundational_schemas_v1 import ResourceUsage
from .agent_core_schemas_v1 import ThoughtStatus, TaskStatus


class ProcessorMetrics(BaseModel):
    """Base metrics all processors track."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    rounds_processed: int = Field(default=0, description="Total rounds processed")
    errors_encountered: int = Field(default=0, description="Total errors encountered")
    total_duration_ms: float = Field(default=0.0, description="Total processing time in milliseconds")
    avg_duration_ms: float = Field(default=0.0, description="Average round duration in milliseconds")
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage, description="Resource consumption metrics")
    
    def update_averages(self) -> None:
        """Update average metrics."""
        if self.rounds_processed > 0:
            self.avg_duration_ms = self.total_duration_ms / self.rounds_processed


class BaseProcessorResult(BaseModel):
    """Base result from any processor."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    round_number: int = Field(..., description="Current processing round")
    state: AgentState = Field(..., description="Agent state during processing")
    duration_ms: float = Field(..., description="Duration of this round in milliseconds")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When this round completed")
    success: bool = Field(default=True, description="Whether processing succeeded")
    errors: List[str] = Field(default_factory=list, description="Any errors encountered")
    metrics: ProcessorMetrics = Field(default_factory=ProcessorMetrics, description="Processor metrics")
    
    class Config:
        """Pydantic configuration."""
        use_enum_values = True


# Processor-specific results

class WakeupResult(BaseProcessorResult):
    """Result from wakeup processor."""
    steps_completed: int = Field(default=0, description="Initialization steps completed")
    total_steps: int = Field(default=5, description="Total initialization steps")
    wakeup_complete: bool = Field(default=False, description="Whether wakeup is complete")
    initialization_errors: List[str] = Field(default_factory=list, description="Specific initialization errors")
    services_initialized: List[str] = Field(default_factory=list, description="Services successfully initialized")
    identity_loaded: bool = Field(default=False, description="Whether agent identity was loaded from graph")
    
    @property
    def progress_percent(self) -> float:
        """Calculate wakeup progress percentage."""
        if self.total_steps == 0:
            return 0.0
        return (self.steps_completed / self.total_steps) * 100.0


class WorkResult(BaseProcessorResult):
    """Result from work processor."""
    tasks_processed: int = Field(default=0, description="Number of tasks processed this round")
    thoughts_generated: int = Field(default=0, description="Number of thoughts generated")
    thoughts_processed: int = Field(default=0, description="Number of thoughts processed")
    queue_depth: int = Field(default=0, description="Current queue depth")
    idle_duration_ms: float = Field(default=0.0, description="Time spent idle in milliseconds")
    active_task_count: int = Field(default=0, description="Number of active tasks")
    pending_task_count: int = Field(default=0, description="Number of pending tasks")
    
    @property
    def productivity_score(self) -> float:
        """Calculate productivity score (0-1)."""
        if self.duration_ms == 0:
            return 0.0
        active_time = self.duration_ms - self.idle_duration_ms
        return min(1.0, active_time / self.duration_ms)


class SolitudeResult(BaseProcessorResult):
    """Result from solitude processor."""
    should_exit_solitude: bool = Field(default=False, description="Whether to exit solitude state")
    exit_reason: Optional[str] = Field(default=None, description="Reason for exiting solitude")
    maintenance_performed: List[str] = Field(default_factory=list, description="Maintenance tasks completed")
    reflections_generated: int = Field(default=0, description="Number of reflections generated")
    memory_optimized: bool = Field(default=False, description="Whether memory was optimized")
    patterns_identified: List[str] = Field(default_factory=list, description="Behavioral patterns identified")
    self_improvements: List[str] = Field(default_factory=list, description="Self-improvement actions taken")


class PlayResult(BaseProcessorResult):
    """Result from play processor."""
    creative_outputs: int = Field(default=0, description="Number of creative outputs generated")
    exploration_topics: List[str] = Field(default_factory=list, description="Topics explored")
    learning_achievements: List[str] = Field(default_factory=list, description="New things learned")
    community_interactions: int = Field(default=0, description="Community interactions")
    gratitude_expressed: int = Field(default=0, description="Gratitude expressions")


class DreamResult(BaseProcessorResult):
    """Result from dream processor."""
    dream_cycles: int = Field(default=0, description="Number of dream cycles completed")
    bench_scores: List[float] = Field(default_factory=list, description="Benchmark scores achieved")
    topics_explored: List[str] = Field(default_factory=list, description="Topics explored in dreams")
    insights_generated: List[str] = Field(default_factory=list, description="Insights from dreaming")
    avg_bench_score: Optional[float] = Field(default=None, description="Average benchmark score")


# Status schemas for get_status() methods

class ProcessorStatus(BaseModel):
    """Common processor status information."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    state: AgentState = Field(..., description="Current agent state")
    state_duration_seconds: float = Field(..., description="How long in current state")
    is_processing: bool = Field(..., description="Whether actively processing")
    round_number: int = Field(..., description="Current round number")
    last_error: Optional[str] = Field(default=None, description="Most recent error")
    metrics: ProcessorMetrics = Field(..., description="Processor metrics")


class QueueHealth(str, Enum):
    """Queue health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    CRITICAL = "critical"


class QueueStatus(BaseModel):
    """Status of the processing queue."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    thought_counts: dict[ThoughtStatus, int] = Field(..., description="Thoughts by status")
    total_thoughts: int = Field(default=0, description="Total thoughts in system")
    queue_depth: int = Field(default=0, description="Current queue depth")
    processing_rate: float = Field(default=0.0, description="Thoughts per second")
    avg_processing_time_ms: float = Field(default=0.0, description="Average processing time")
    queue_health: QueueHealth = Field(default=QueueHealth.HEALTHY, description="Overall queue health")
    has_pending_work: bool = Field(default=False, description="Whether work is pending")
    has_processing_work: bool = Field(default=False, description="Whether work is being processed")
    
    def calculate_health(self) -> QueueHealth:
        """Calculate queue health based on metrics."""
        if self.queue_depth > 100:
            return QueueHealth.CRITICAL
        elif self.queue_depth > 50 or self.avg_processing_time_ms > 5000:
            return QueueHealth.DEGRADED
        return QueueHealth.HEALTHY


class TaskQueueSummary(BaseModel):
    """Summary of task queue status."""
    active_tasks: int = Field(default=0, description="Currently active tasks")
    pending_tasks: int = Field(default=0, description="Pending tasks")
    completed_today: int = Field(default=0, description="Tasks completed today")
    failed_today: int = Field(default=0, description="Tasks failed today")
    avg_completion_time_ms: float = Field(default=0.0, description="Average task completion time")


# Supporting schemas

class TaskOutcome(BaseModel):
    """Outcome of a completed task."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    task_id: str = Field(..., description="Task identifier")
    status: TaskStatus = Field(..., description="Final task status")
    completion_reason: str = Field(..., description="Reason for completion")
    result_data: Optional[Any] = Field(default=None, description="Task result data")
    error: Optional[str] = Field(default=None, description="Error if failed")
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage, description="Resources consumed")
    duration_ms: float = Field(..., description="Total task duration")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Completion time")


class StateTransition(BaseModel):
    """Record of a state transition."""
    from_state: AgentState = Field(..., description="Previous state")
    to_state: AgentState = Field(..., description="New state")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When transition occurred")
    reason: Optional[str] = Field(default=None, description="Reason for transition")
    triggered_by: str = Field(default="system", description="What triggered the transition")


class StateMetadata(BaseModel):
    """Metadata about agent states."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    current_state: AgentState = Field(..., description="Current state")
    transition_history: List[StateTransition] = Field(default_factory=list, description="State transition history")
    state_durations: dict[AgentState, float] = Field(default_factory=dict, description="Time spent in each state (seconds)")
    idle_threshold_seconds: float = Field(default=300.0, description="Seconds before considering idle")
    last_activity: datetime = Field(default_factory=datetime.utcnow, description="Last activity timestamp")
    
    @property
    def current_idle_duration(self) -> float:
        """Calculate current idle duration in seconds."""
        return (datetime.utcnow() - self.last_activity).total_seconds()
    
    @property
    def is_idle(self) -> bool:
        """Check if agent is idle."""
        return self.current_idle_duration > self.idle_threshold_seconds


class MaintenanceResult(BaseModel):
    """Result of maintenance operations in solitude."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    memory_cleaned_mb: float = Field(default=0.0, description="Memory freed in MB")
    old_thoughts_archived: int = Field(default=0, description="Old thoughts archived")
    indexes_optimized: int = Field(default=0, description="Database indexes optimized")
    logs_rotated: bool = Field(default=False, description="Whether logs were rotated")
    cache_cleared: bool = Field(default=False, description="Whether caches were cleared")
    errors_encountered: List[str] = Field(default_factory=list, description="Any errors during maintenance")


class ReflectionResult(BaseModel):
    """Result of self-reflection in solitude."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    patterns_identified: List[str] = Field(default_factory=list, description="Behavioral patterns found")
    insights_generated: List[str] = Field(default_factory=list, description="New insights")
    improvements_suggested: List[str] = Field(default_factory=list, description="Suggested improvements")
    ethical_considerations: List[str] = Field(default_factory=list, description="Ethical reflections")
    gratitude_reflections: List[str] = Field(default_factory=list, description="Gratitude reflections")