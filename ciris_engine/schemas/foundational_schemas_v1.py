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

    channel_id: str
    is_bot: bool = False
    is_dm: bool = False

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

    tokens: int = 0
    estimated_cost: Optional[float] = None
    energy_kwh: Optional[float] = None

    model_config = ConfigDict(extra="allow")


# Backwards-compatible alias for SchemaVersion
CIRISSchemaVersion = SchemaVersion


__all__ = [
    "CaseInsensitiveEnum",
    "HandlerActionType",
    "TaskStatus",
    "ThoughtStatus",
    "ObservationSourceType",
    "IncomingMessage",
    "DiscordMessage",
    "FetchedMessage",
    "ResourceUsage",
    "SchemaVersion",
    "CIRISSchemaVersion",
]
