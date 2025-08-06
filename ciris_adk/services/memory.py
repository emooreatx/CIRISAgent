"""MemoryService protocol for agent memory storage - aligned with engine protocols."""

from __future__ import annotations

# Import the standardized protocols and schemas from engine
from ciris_engine.protocols.services import MemoryService
from ciris_engine.schemas.services_schemas_v1 import GraphNode, MemoryOpResult

# Re-export the engine protocol as the canonical interface
__all__ = ["MemoryService", "GraphNode", "MemoryOpResult"]
