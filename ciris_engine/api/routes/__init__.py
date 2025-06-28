"""
API routes module.

Export all route modules for easy import.
"""

# Import all route modules
from . import (
    agent,
    audit,
    auth,
    config,
    emergency,
    health,
    incidents,
    llm,
    memory,
    resources,
    runtime,
    system,
    telemetry,
    time,
    wa
)

__all__ = [
    "agent",
    "audit",
    "auth",
    "config",
    "emergency",
    "health",
    "incidents",
    "llm",
    "memory",
    "resources",
    "runtime",
    "system",
    "telemetry",
    "time",
    "wa"
]