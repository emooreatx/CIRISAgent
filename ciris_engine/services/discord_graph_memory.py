"""Backward-compat shim for legacy imports."""
from __future__ import annotations

from ciris_engine.memory.ciris_local_graph import CIRISLocalGraph, MemoryOpStatus, MemoryOpResult

DiscordGraphMemory = CIRISLocalGraph

__all__ = ["DiscordGraphMemory", "CIRISLocalGraph", "MemoryOpStatus", "MemoryOpResult"]
