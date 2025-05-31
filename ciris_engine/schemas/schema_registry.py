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
    }

    @classmethod
    def validate_schema(cls, name: str, data: Dict[str, Any]) -> BaseModel:
        """Validate data against a registered schema."""
        schema = cls.schemas.get(name)
        if schema is None:
            raise ValueError(f"Schema '{name}' not registered")
        return schema(**data)
