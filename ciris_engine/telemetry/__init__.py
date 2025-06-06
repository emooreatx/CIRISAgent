"""
CIRIS Agent Telemetry System

Provides comprehensive observability while maintaining security and agent self-awareness.
All telemetry data is considered potentially sensitive and processed through security filters.

Key principles:
- Safety First: No PII or conversation content in metrics
- Agent Self-Awareness: Full visibility into own metrics via SystemSnapshot
- Secure by Default: All external endpoints require authentication and TLS
- Fail Secure: Telemetry failures don't affect agent operation
"""

from .resource_monitor import ResourceMonitor, ResourceSignalBus

__all__ = [
    "ResourceMonitor",
    "ResourceSignalBus",
]
