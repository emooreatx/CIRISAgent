from enum import Enum
from pydantic import BaseModel, Field, ConfigDict
from .versioning import SchemaVersion
from typing import Optional, Any

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

class ThoughtStatus(CaseInsensitiveEnum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DEFERRED = "deferred"

class ObservationSourceType(CaseInsensitiveEnum):
    CHAT_MESSAGE = "chat_message"
    FEEDBACK_PACKAGE = "feedback_package"
    USER_REQUEST = "user_request"
    AGENT_MESSAGE = "agent_message"
    INTERNAL_SIGNAL = "internal_signal"

class IncomingMessage(BaseModel):
    """Schema for incoming messages from various sources."""

    message_id: SchemaVersion
    author_id: SchemaVersion
    author_name: SchemaVersion
    content: SchemaVersion
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

    channel_id: SchemaVersion
    is_bot: SchemaVersion = False
    is_dm: SchemaVersion = False

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
    """Track LLM resource utilization."""

    tokens: SchemaVersion = 0
    estimated_cost: Optional[float] = None
    energy_kwh: Optional[float] = None

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
]
