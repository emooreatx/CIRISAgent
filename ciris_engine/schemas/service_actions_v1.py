"""
Action and message types for multi-service sinks.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional, List
from datetime import datetime
from ciris_engine.schemas.graph_schemas_v1 import GraphNode
from enum import Enum


class ActionType(Enum):
    """Types of actions that can be processed by sinks"""
    SEND_MESSAGE = "send_message"
    FETCH_MESSAGES = "fetch_messages"
    FETCH_GUIDANCE = "fetch_guidance"
    SEND_DEFERRAL = "send_deferral"
    MEMORIZE = "memorize"
    RECALL = "recall"
    FORGET = "forget"
    SEND_TOOL = "send_tool"
    FETCH_TOOL = "fetch_tool"
    # Note: OBSERVE_MESSAGE removed - observation handled at adapter level
    # LLM Actions
    GENERATE_STRUCTURED = "generate_structured"
    # TSDB/Telemetry Actions
    RECORD_METRIC = "record_metric"
    QUERY_TELEMETRY = "query_telemetry"
    RECORD_LOG = "record_log"
    # Audit Actions
    LOG_AUDIT_EVENT = "log_audit_event"
    QUERY_AUDIT_TRAIL = "query_audit_trail"



@dataclass
class ActionMessage:
    """Base action message for service sinks"""
    type: ActionType
    handler_name: str
    metadata: Dict[str, Any]


@dataclass
class SendMessageAction(ActionMessage):
    """Action to send a message via communication service"""
    channel_id: str
    content: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], channel_id: str, content: str) -> None:
        super().__init__(ActionType.SEND_MESSAGE, handler_name, metadata)
        self.channel_id = channel_id
        self.content = content


@dataclass
class FetchMessagesAction(ActionMessage):
    """Action to fetch messages via communication service"""
    channel_id: str
    limit: int = 10
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], channel_id: str, limit: int = 10) -> None:
        super().__init__(ActionType.FETCH_MESSAGES, handler_name, metadata)
        self.channel_id = channel_id
        self.limit = limit


@dataclass
class FetchGuidanceAction(ActionMessage):
    """Action to fetch guidance from WA service"""
    context: Dict[str, Any]
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], context: Dict[str, Any]) -> None:
        super().__init__(ActionType.FETCH_GUIDANCE, handler_name, metadata)
        self.context = context


@dataclass
class SendDeferralAction(ActionMessage):
    """Action to send deferral to WA service"""
    thought_id: str
    reason: str
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], thought_id: str, reason: str) -> None:
        super().__init__(ActionType.SEND_DEFERRAL, handler_name, metadata)
        self.thought_id = thought_id
        self.reason = reason


@dataclass
class MemorizeAction(ActionMessage):
    """Action to memorize data via memory service"""
    node: GraphNode

    def __init__(self, handler_name: str, metadata: Dict[str, Any], node: GraphNode) -> None:
        super().__init__(ActionType.MEMORIZE, handler_name, metadata)
        self.node = node


@dataclass
class RecallAction(ActionMessage):
    """Action to recall data via memory service"""
    node: GraphNode

    def __init__(self, handler_name: str, metadata: Dict[str, Any], node: GraphNode) -> None:
        super().__init__(ActionType.RECALL, handler_name, metadata)
        self.node = node


@dataclass
class ForgetAction(ActionMessage):
    """Action to forget data via memory service"""
    node: GraphNode

    def __init__(self, handler_name: str, metadata: Dict[str, Any], node: GraphNode) -> None:
        super().__init__(ActionType.FORGET, handler_name, metadata)
        self.node = node


@dataclass
class SendToolAction(ActionMessage):
    """Action to send tool result via tool service"""
    tool_name: str
    tool_args: Dict[str, Any]
    correlation_id: Optional[str] = None
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], tool_name: str, tool_args: Dict[str, Any], correlation_id: Optional[str] = None) -> None:
        super().__init__(ActionType.SEND_TOOL, handler_name, metadata)
        self.tool_name = tool_name
        self.tool_args = tool_args
        self.correlation_id = correlation_id


@dataclass
class FetchToolAction(ActionMessage):
    """Action to fetch tool via tool service"""
    tool_name: str
    correlation_id: str
    timeout: float = 30.0
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], tool_name: str, correlation_id: str, timeout: float = 30.0) -> None:
        super().__init__(ActionType.FETCH_TOOL, handler_name, metadata)
        self.tool_name = tool_name
        self.correlation_id = correlation_id
        self.timeout = timeout


@dataclass  
class GenerateStructuredAction(ActionMessage):
    """Action to generate a structured response via LLM service"""
    messages: list
    response_model: Any
    max_tokens: int = 1024
    temperature: float = 0.0
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], messages: list, 
                 response_model: Any, max_tokens: int = 1024, temperature: float = 0.0) -> None:
        super().__init__(ActionType.GENERATE_STRUCTURED, handler_name, metadata)
        self.messages = messages
        self.response_model = response_model
        self.max_tokens = max_tokens
        self.temperature = temperature


DeferralMessage = SendDeferralAction


# TSDB/Telemetry Actions

@dataclass
class RecordMetricAction(ActionMessage):
    """Action to record a metric via telemetry service"""
    metric_name: str
    value: float
    tags: Optional[Dict[str, str]] = None
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], metric_name: str, 
                 value: float, tags: Optional[Dict[str, str]] = None) -> None:
        super().__init__(ActionType.RECORD_METRIC, handler_name, metadata)
        self.metric_name = metric_name
        self.value = value
        self.tags = tags


@dataclass
class QueryTelemetryAction(ActionMessage):
    """Action to query telemetry data via telemetry service"""
    metric_names: Optional[List[str]] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    tags: Optional[Dict[str, str]] = None
    limit: int = 1000
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], 
                 metric_names: Optional[List[str]] = None, start_time: Optional[datetime] = None,
                 end_time: Optional[datetime] = None, tags: Optional[Dict[str, str]] = None,
                 limit: int = 1000) -> None:
        super().__init__(ActionType.QUERY_TELEMETRY, handler_name, metadata)
        self.metric_names = metric_names
        self.start_time = start_time
        self.end_time = end_time
        self.tags = tags
        self.limit = limit


@dataclass
class RecordLogAction(ActionMessage):
    """Action to record a log entry via telemetry service"""
    log_message: str
    log_level: str = "INFO"
    tags: Optional[Dict[str, str]] = None
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], log_message: str,
                 log_level: str = "INFO", tags: Optional[Dict[str, str]] = None) -> None:
        super().__init__(ActionType.RECORD_LOG, handler_name, metadata)
        self.log_message = log_message
        self.log_level = log_level
        self.tags = tags



@dataclass
class LogAuditEventAction(ActionMessage):
    """Action to log an audit event via audit service"""
    event_type: str
    event_data: Dict[str, Any]
    outcome: Optional[str] = None
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any], event_type: str,
                 event_data: Dict[str, Any], outcome: Optional[str] = None) -> None:
        super().__init__(ActionType.LOG_AUDIT_EVENT, handler_name, metadata)
        self.event_type = event_type
        self.event_data = event_data
        self.outcome = outcome


@dataclass
class QueryAuditTrailAction(ActionMessage):
    """Action to query audit trail via audit service"""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    action_types: Optional[List[str]] = None
    thought_id: Optional[str] = None
    task_id: Optional[str] = None
    limit: int = 100
    
    def __init__(self, handler_name: str, metadata: Dict[str, Any],
                 start_time: Optional[datetime] = None, end_time: Optional[datetime] = None,
                 action_types: Optional[List[str]] = None, thought_id: Optional[str] = None,
                 task_id: Optional[str] = None, limit: int = 100) -> None:
        super().__init__(ActionType.QUERY_AUDIT_TRAIL, handler_name, metadata)
        self.start_time = start_time
        self.end_time = end_time
        self.action_types = action_types
        self.thought_id = thought_id
        self.task_id = task_id
        self.limit = limit
