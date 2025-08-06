"""
Protocol Analyzer Whitelist Configuration

This module defines patterns that should be excluded from protocol compliance checks.
These are legitimate uses of Any that don't violate CIRIS type safety principles.
"""

import re
from typing import Dict, List, Pattern

# Decorator patterns that legitimately use Any for *args and **kwargs
DECORATOR_PATTERNS: List[Pattern[str]] = [
    # Async decorator wrappers
    re.compile(r"async def \w+_wrapper\(\*args: Any, \*\*kwargs: Any\) -> Any:"),
    # Sync decorator wrappers
    re.compile(r"def \w+_wrapper\(\*args: Any, \*\*kwargs: Any\) -> Any:"),
    # Generic decorators
    re.compile(r"def decorator\(.*\) -> Callable\[\[.*\], Any\]:"),
]

# Function signatures that legitimately use Any
FUNCTION_PATTERNS: List[Pattern[str]] = [
    # Extensible kwargs for telemetry/metrics
    re.compile(r"\*\*kwargs: Any\s*#.*telemetry.*parameters"),
    # Extensible kwargs for configuration
    re.compile(r"\*\*kwargs: Any\s*#.*config.*parameters"),
    # Generic event handlers
    re.compile(r"\*\*kwargs: Any\s*#.*event.*data"),
]

# Services that are allowed to use specific Any patterns
SERVICE_WHITELIST: Dict[str, List[str]] = {
    "AuthenticationService": [
        # Authentication decorators need Any for flexibility
        "require_scope",
        "require_role",
        "require_channel_permission",
        "verify_kill_switch_command",
    ],
    "TelemetryService": [
        # Telemetry needs extensible parameters
        "record_metric",
        "record_event",
        "process_snapshot",
    ],
}


def is_whitelisted(service_name: str, line: str, context: str) -> bool:
    """
    Check if a specific Any usage should be whitelisted.

    Args:
        service_name: Name of the service being checked
        line: Line number where Any is used
        context: The code context containing Any

    Returns:
        True if this usage should be whitelisted, False otherwise
    """
    # Check decorator patterns
    for pattern in DECORATOR_PATTERNS:
        if pattern.search(context):
            return True

    # Check function patterns
    for pattern in FUNCTION_PATTERNS:
        if pattern.search(context):
            return True

    # Check service-specific whitelist
    if service_name in SERVICE_WHITELIST:
        # For now, whitelist all Any usage in these services
        # Could be more specific by checking method names
        return True

    return False
