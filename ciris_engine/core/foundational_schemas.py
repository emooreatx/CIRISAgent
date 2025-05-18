"""Core enums and type aliases for CIRIS Engine."""
from enum import Enum
from typing import Union, List, Dict, Any, Optional # Retaining for now, can be pruned

# Pydantic might not be strictly needed here if only Enums and type aliases
# from pydantic import BaseModel, Field

class CIRISSchemaVersion(str, Enum):
    V1_0_BETA = "1.0-beta"
    #... future versions

class HandlerActionType(str, Enum):
    """The 3×3×3 action model for CIRIS handlers."""

    # External actions
    OBSERVE = "observe"
    SPEAK = "speak"
    ACT = "act"

    # Control responses
    REJECT = "reject"
    PONDER = "ponder"
    DEFER = "defer"  # Generic deferral action
    DEFER_TO_WA = "defer_to_wa"  # Explicit deferral requiring WA intervention

    # Memory operations
    MEMORIZE = "memorize"
    REMEMBER = "remember"
    FORGET = "forget"

class TaskStatus(str, Enum):
    PENDING = "pending"
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused" # Added based on user feedback
    FAILED = "failed"
    DEFERRED = "deferred" # Task deferred to WA
    REJECTED = "rejected" # Task rejected by agent

class ThoughtStatus(str, Enum):
    PENDING = "pending" # Includes thoughts queued for pondering
    PROCESSING = "processing"
    COMPLETED = "completed" # Terminal state after action/deferral
    PAUSED = "paused" # Added based on user feedback
    FAILED = "failed" # Error during processing
    DEFERRED = "deferred" # Outcome was deferral to WA
    REJECTED = "rejected" # Outcome was rejection


class MemoryUpdateContext(str, Enum):
    """Context markers for memory updates."""

    CHANNEL_UPDATE_REQUEST = "channel_update_request"
    CHANNEL_UPDATE_WA_APPROVED = "channel_update_wa_approved"

class ObservationSourceType(str, Enum):
    DISCORD_MESSAGE = "discord_message"
    WBD_PACKAGE = "wbd_package" # Wisdom-Based Deferral package received
    CORRECTION_PACKAGE = "correction_package" # Feedback/correction received
    USER_REQUEST = "user_request" # Direct request (CLI, API, etc.)
    BENCHMARK_REQUEST = "benchmark_request" # Request to run a benchmark
    INTERNAL_SENSOR = "internal_sensor" # Agent's own internal state monitoring
    EXTERNAL_SENSOR = "external_sensor" # Physical or virtual sensor feed
    AGENT_MESSAGE = "agent_message" # Observation derived from another agent's message
    DKG_UPDATE = "dkg_update" # Change detected in a relevant KA

class DKGAssetType(str, Enum):
    AGENT_PROFILE = "AgentProfile"
    TASK_DEFINITION = "TaskDefinition"
    ENVIRONMENT_MODEL = "EnvironmentModel"
    METATHOUGHT_RECORD = "MetathoughtRecord"
    LEARNED_MODEL = "LearnedModel"
    AUDIT_LOG_BATCH = "AuditLogBatch"
    SCHEMA_DEFINITION = "SchemaDefinition"
    #... other CIRIS-specific KA types

# Placeholder types for UALs and DIDs - assume string validation elsewhere
CIRISAgentUAL = str # e.g., "did:dkg:otp:cirisMain/agentProfilesContract/agentTokenID"
CIRISTaskUAL = str
CIRISKnowledgeAssetUAL = str # Generic KA UAL
VeilidDID = str # e.g., "did:key:z..." or a Veilid-specific method
VeilidRouteID = str # Veilid's internal routing identifier
