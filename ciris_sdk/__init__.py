"""Minimal async client SDK for CIRIS Engine."""

from .client import CIRISClient
from .resources.agent import (
    InteractResponse,
    AgentStatus,
    AgentIdentity,
    ConversationHistory,
    ConversationMessage
)
from .models import (
    GraphNode,
    MemoryOpResult,
    TimelineResponse,
    # Legacy models
    MemoryEntry,
    MemoryScope,
    # Telemetry models
    TelemetryMetricData,
    TelemetryDetailedMetric,
    TelemetrySystemOverview,
    TelemetryReasoningTrace,
    TelemetryLogEntry,
    # Other models
    Message,
    ProcessorControlResponse,
    AdapterInfo,
    RuntimeStatus,
    SystemHealth,
    ServiceInfo,
    ProcessorState,
    MetricRecord,
    DeferralInfo,
    AuditEntryResponse,
    AuditEntriesResponse,
    AuditExportResponse
)

__all__ = [
    "CIRISClient",
    # Agent interaction types
    "InteractResponse",
    "AgentStatus",
    "AgentIdentity",
    "ConversationHistory",
    "ConversationMessage",
    "GraphNode",
    "MemoryOpResult",
    "TimelineResponse",
    "MemoryEntry",
    "MemoryScope",
    # Telemetry
    "TelemetryMetricData",
    "TelemetryDetailedMetric",
    "TelemetrySystemOverview",
    "TelemetryReasoningTrace",
    "TelemetryLogEntry",
    # Other models
    "Message",
    "ProcessorControlResponse",
    "AdapterInfo",
    "RuntimeStatus",
    "SystemHealth",
    "ServiceInfo",
    "ProcessorState",
    "MetricRecord",
    "DeferralInfo",
    "AuditEntryResponse",
    "AuditEntriesResponse",
    "AuditExportResponse"
]
