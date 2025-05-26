from enum import Enum

class CaseInsensitiveEnum(str, Enum):
    """Enum that allows case-insensitive value lookup."""
    @classmethod
    def _missing_(cls, value: object):
        if isinstance(value, str):
            lowered = value.lower()
            for member in cls:
                if member.value.lower() == lowered or member.name.lower() == lowered:
                    return member
        return None

class HandlerActionType(CaseInsensitiveEnum):
    """Core 3×3×3 action model"""
    # External actions
    OBSERVE = "observe"
    SPEAK = "speak"
    TOOL = "tool"
    # Control responses
    REJECT = "reject"
    PONDER = "ponder"
    DEFER = "defer"
    # Memory operations
    MEMORIZE = "memorize"
    REMEMBER = "remember"
    FORGET = "forget"
    # Terminal
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
    DISCORD_MESSAGE = "discord_message"
    FEEDBACK_PACKAGE = "feedback_package"  # Renamed from CORRECTION_PACKAGE
    USER_REQUEST = "user_request"
    AGENT_MESSAGE = "agent_message"
    INTERNAL_SIGNAL = "internal_signal"  # Simplified from INTERNAL_SENSOR
