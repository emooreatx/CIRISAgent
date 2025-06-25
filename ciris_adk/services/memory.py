"""MemoryService protocol for agent memory storage - aligned with engine protocols."""

from __future__ import annotations

from typing import Any, Dict, List, Protocol

# Import the standardized protocols and schemas from engine
from ciris_engine.protocols.services import MemoryService
from ciris_engine.schemas.services_schemas_v1 import GraphNode
from ciris_engine.schemas.services_schemas_v1 import MemoryOpResult

# Re-export the engine protocol as the canonical interface
__all__ = ["MemoryService", "GraphNode", "MemoryOpResult"]

