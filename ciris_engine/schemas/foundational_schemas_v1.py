from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from .versioning import SchemaVersion
from typing import Optional, Any, Dict, TYPE_CHECKING

if TYPE_CHECKING:
    from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult
    from ciris_engine.schemas.context_schemas_v1 import ChannelContext

class CaseInsensitiveEnum(str, Enum):
    """Enum that allows case-insensitive value lookup."""
    @classmethod
    def _missing_(cls, value: object) -> 'CaseInsensitiveEnum | None':
        if isinstance(value, str):
            lowered = value.lower()
            for member in cls:
                if member.value.lower() == lowered or member.name.lower() == lowered:
                    return member
        return None

class ServiceType(CaseInsensitiveEnum):
    """The core service types that can be provided by the runtime or an adapter."""
    COMMUNICATION = "communication"
    TOOL = "tool"
    WISE_AUTHORITY = "wise_authority"
    MEMORY = "memory"
    AUDIT = "audit"
    LLM = "llm"
    TELEMETRY = "telemetry"
    ORCHESTRATOR = "orchestrator"
    SECRETS = "secrets"
    RUNTIME_CONTROL = "runtime_control"
    FILTER = "filter"
    CONFIG = "config"
    MAINTENANCE = "maintenance"

class HandlerActionType(CaseInsensitiveEnum):
    """Core 3×3×3 action model"""
    OBSERVE = "observe"
    SPEAK = "speak"
    TOOL = "tool"
    REJECT = "reject"
    PONDER = "ponder"
    DEFER = "defer"
    MEMORIZE = "memorize"
    RECALL = "recall"
    FORGET = "forget"
    TASK_COMPLETE = "task_complete"

class TaskStatus(CaseInsensitiveEnum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"
    REJECTED = "rejected"

class ThoughtStatus(CaseInsensitiveEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"

class SensitivityLevel(CaseInsensitiveEnum):
    """Security sensitivity levels for secrets and sensitive information."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class ObservationSourceType(CaseInsensitiveEnum):
    CHAT_MESSAGE = "chat_message"
    FEEDBACK_PACKAGE = "feedback_package"
    USER_REQUEST = "user_request"
    AGENT_MESSAGE = "agent_message"
    INTERNAL_SIGNAL = "internal_signal"

class IncomingMessage(BaseModel):
    """Schema for incoming messages from various sources."""

    message_id: str
    author_id: str
    author_name: str
    content: str
    destination_id: Optional[str] = Field(default=None, alias="channel_id")
    reference_message_id: Optional[str] = None
    timestamp: Optional[str] = None

    model_config = ConfigDict(populate_by_name=True, extra="allow")

    @property
    def channel_id(self) -> Optional[str]:
        """Backward compatibility alias for destination_id."""
        return self.destination_id


class DiscordMessage(IncomingMessage):
    """Incoming message specific to the Discord platform."""

    is_bot: bool = False
    is_dm: bool = False
    raw_message: Optional[Any] = Field(default=None, exclude=True)  # Discord.py message object

    def __init__(self, **data: Any) -> None:
        if "destination_id" not in data and "channel_id" in data:
            data["destination_id"] = data.get("channel_id")
        super().__init__(**data)


class FetchedMessage(BaseModel):
    """Message returned by CommunicationService.fetch_messages."""

    message_id: Optional[str] = Field(default=None, alias="id")
    content: Optional[str] = None
    author_id: Optional[str] = None
    author_name: Optional[str] = None
    timestamp: Optional[str] = None
    is_bot: Optional[bool] = False

    model_config = ConfigDict(populate_by_name=True, extra="allow")


class ResourceUsage(BaseModel):
    """Track LLM resource utilization with environmental awareness."""

    # Token usage
    tokens_used: int = Field(default=0, description="Total tokens consumed")
    tokens_input: int = Field(default=0, description="Input tokens")
    tokens_output: int = Field(default=0, description="Output tokens")
    
    # Financial impact
    cost_cents: float = Field(default=0.0, ge=0.0, description="Cost in cents USD")
    
    # Environmental impact
    carbon_grams: float = Field(default=0.0, ge=0.0, description="Carbon emissions in grams CO2")
    energy_kwh: float = Field(default=0.0, ge=0.0, description="Energy consumption in kilowatt-hours")
    
    # Compute resources
    compute_ms: Optional[int] = Field(default=None, ge=0, description="Compute time in milliseconds")
    memory_mb: Optional[int] = Field(default=None, ge=0, description="Memory usage in megabytes")
    
    # Model information
    model_used: Optional[str] = Field(default=None, description="Model that incurred these costs")

    model_config = ConfigDict(extra="allow")


class ThoughtType(str, Enum):
    # Core thought types
    STANDARD = "standard"
    FOLLOW_UP = "follow_up"
    ERROR = "error"
    OBSERVATION = "observation"
    MEMORY = "memory"
    DEFERRED = "deferred"
    PONDER = "ponder"
    GRATITUDE = "gratitude"  # Acknowledging help received
    # Feedback and guidance types
    FEEDBACK = "feedback"           # Processing WA feedback
    GUIDANCE = "guidance"           # Incorporating WA guidance
    IDENTITY_UPDATE = "identity_update"  # Identity feedback processing
    # Decision-making types
    ETHICAL_REVIEW = "ethical_review"    # Ethical DMA triggered
    GUARDRAIL = "guardrail"         # Guardrail violation handling
    CONSENSUS = "consensus"         # Multi-agent consensus needed
    # System and meta types
    REFLECTION = "reflection"       # Self-reflection/meta-cognition
    SYNTHESIS = "synthesis"         # Combining multiple thoughts
    DELEGATION = "delegation"       # Delegating to another agent/service
    # Communication types
    CLARIFICATION = "clarification" # Seeking clarification from user
    SUMMARY = "summary"            # Summarizing conversation/task
    # Tool and action types
    TOOL_RESULT = "tool_result"    # Processing tool execution results
    ACTION_REVIEW = "action_review" # Reviewing action before execution
    # Urgency and priority types
    URGENT = "urgent"              # High-priority urgent thought
    SCHEDULED = "scheduled"        # Time-based scheduled thought
    # Learning and adaptation
    PATTERN = "pattern"           # Pattern recognition
    ADAPTATION = "adaptation"     # Behavioral adaptation

# Backwards-compatible alias for SchemaVersion
CIRISSchemaVersion = SchemaVersion


class DispatchContext(BaseModel):
    """Type-safe context for action handler dispatch.
    
    This replaces the generic Dict[str, Any] with proper typed fields
    for mission-critical production use. All core fields are REQUIRED.
    """
    # Core identification - ALL REQUIRED
    channel_context: 'ChannelContext' = Field(..., description="Channel context where action originated")
    author_id: str = Field(..., description="ID of user/entity initiating action")
    author_name: str = Field(..., description="Display name of initiator")
    
    # Service references - ALL REQUIRED
    origin_service: str = Field(..., description="Service that originated the request")
    handler_name: str = Field(..., description="Handler processing this action")
    
    # Action context - ALL REQUIRED
    action_type: HandlerActionType = Field(..., description="Type of action being handled")
    thought_id: str = Field(..., description="Associated thought ID")
    task_id: str = Field(..., description="Associated task ID")
    source_task_id: str = Field(..., description="Source task ID from thought")
    
    # Event details - ALL REQUIRED
    event_summary: str = Field(..., description="Summary of the event/action")
    event_timestamp: str = Field(..., description="ISO8601 timestamp of event")
    
    # Additional context - REQUIRED with sensible defaults
    wa_id: Optional[str] = Field(None, description="Wise Authority ID if applicable")
    wa_authorized: bool = Field(False, description="Whether WA authorized this action")
    correlation_id: str = Field(..., description="Correlation ID for tracking")
    round_number: int = Field(..., description="Processing round number")
    
    # Guardrail results - None for terminal actions (DEFER, REJECT, TASK_COMPLETE)
    guardrail_result: Optional['GuardrailResult'] = Field(
        None, 
        description="Guardrail evaluation results. None for terminal actions that bypass guardrails."
    )
    
    # Computed properties for convenience
    @property
    def has_guardrail_data(self) -> bool:
        """Check if guardrail data is available."""
        return self.guardrail_result is not None
    
    @property
    def epistemic_data(self) -> Optional[Dict[str, Any]]:
        """Get epistemic data from guardrail results if available."""
        if self.guardrail_result and hasattr(self.guardrail_result, 'epistemic_data'):
            return self.guardrail_result.epistemic_data
        return None
    
    @property
    def was_overridden(self) -> bool:
        """Check if the action was overridden by guardrails."""
        if self.guardrail_result and hasattr(self.guardrail_result, 'overridden'):
            return self.guardrail_result.overridden
        return False
    
    model_config = ConfigDict(extra="forbid")  # No arbitrary fields allowed!


__all__ = [
    "CaseInsensitiveEnum",
    "HandlerActionType",
    "TaskStatus",
    "ThoughtStatus",
    "ThoughtType",
    "ObservationSourceType",
    "IncomingMessage",
    "DiscordMessage",
    "FetchedMessage",
    "ResourceUsage",
    "SchemaVersion",
    "CIRISSchemaVersion",
    "ServiceType",
    "DispatchContext",
]

# Rebuild models with forward references
from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult
from ciris_engine.schemas.context_schemas_v1 import ChannelContext
DispatchContext.model_rebuild()
