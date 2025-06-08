from typing import Dict, Type, Any
from pydantic import BaseModel

from .agent_core_schemas_v1 import Task, Thought
from .action_params_v1 import (
    ObserveParams,
    SpeakParams,
    ToolParams,
    PonderParams,
    RejectParams,
    DeferParams,
    MemorizeParams,
    RecallParams,
    ForgetParams,
)
from .dma_results_v1 import ActionSelectionResult
from .network_schemas_v1 import AgentIdentity, NetworkPresence
from .community_schemas_v1 import MinimalCommunityContext
from .wisdom_schemas_v1 import WisdomRequest, UniversalGuidanceProtocol
from .telemetry_schemas_v1 import CompactTelemetry
from .resource_schemas_v1 import ResourceSnapshot

class SchemaRegistry:
    """Central registry for schema validation."""

    schemas: Dict[str, Type[BaseModel]] = {
        "Task": Task,
        "Thought": Thought,
        "ObserveParams": ObserveParams,
        "SpeakParams": SpeakParams,
        "ToolParams": ToolParams,
        "PonderParams": PonderParams,
        "RejectParams": RejectParams,
        "DeferParams": DeferParams,
        "MemorizeParams": MemorizeParams,
        "RecallParams": RecallParams,
        "ForgetParams": ForgetParams,
        "ActionSelectionResult": ActionSelectionResult,
        
        # Network schemas
        "AgentIdentity": AgentIdentity,
        "NetworkPresence": NetworkPresence,
        
        # Community schemas
        "MinimalCommunityContext": MinimalCommunityContext,
        
        # Wisdom schemas
        "WisdomRequest": WisdomRequest,
        "UniversalGuidanceProtocol": UniversalGuidanceProtocol,
        
        # Telemetry schemas
        "CompactTelemetry": CompactTelemetry,
        "ResourceSnapshot": ResourceSnapshot,
    }

    @classmethod
    def validate_schema(cls, name: str, data: Dict[str, Any]) -> BaseModel:
        """Validate data against a registered schema."""
        schema = cls.schemas.get(name)
        if schema is None:
            raise ValueError(f"Schema '{name}' not registered")
        return schema(**data)
