"""
Centralized time utilities for consistent time handling across CIRIS.

This module provides timezone-aware time functions that should be used
throughout the codebase for consistency, especially important for:
- Cryptographic operations (signatures, tokens)
- Audit trails
- Telemetry and metrics
- Resource usage tracking
- Database timestamps
"""

from datetime import datetime, timezone, timedelta
from typing import Optional, Union


def utc_now() -> datetime:
    """
    Get current UTC time as timezone-aware datetime.
    
    Returns:
        datetime: Current time in UTC with timezone info
    """
    return datetime.now(timezone.utc)


def utc_now_iso() -> str:
    """
    Get current UTC time as ISO 8601 format string.
    
    Returns:
        str: Current UTC time in ISO format (e.g., "2024-01-15T10:30:00+00:00")
    """
    return datetime.now(timezone.utc).isoformat()


def utc_now_timestamp() -> float:
    """
    Get current UTC time as Unix timestamp.
    
    Returns:
        float: Seconds since Unix epoch
    """
    return datetime.now(timezone.utc).timestamp()


def utc_now_ms() -> int:
    """
    Get current UTC time as milliseconds since Unix epoch.
    
    Returns:
        int: Milliseconds since Unix epoch
    """
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def parse_iso_datetime(iso_string: str) -> datetime:
    """
    Parse ISO 8601 datetime string to timezone-aware datetime.
    
    Args:
        iso_string: ISO 8601 formatted datetime string
        
    Returns:
        datetime: Parsed timezone-aware datetime
        
    Raises:
        ValueError: If string cannot be parsed
    """
    # Try parsing with timezone first
    try:
        dt = datetime.fromisoformat(iso_string)
        # If no timezone, assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except ValueError:
        # Fallback for older Python versions or non-standard formats
        # Remove 'Z' suffix if present
        if iso_string.endswith('Z'):
            iso_string = iso_string[:-1] + '+00:00'
        return datetime.fromisoformat(iso_string)


def ensure_utc(dt: datetime) -> datetime:
    """
    Ensure a datetime is in UTC timezone.
    
    Args:
        dt: Datetime to convert
        
    Returns:
        datetime: Datetime in UTC timezone
        
    Raises:
        ValueError: If naive datetime is provided
    """
    if dt.tzinfo is None:
        raise ValueError("Naive datetime provided. Use timezone-aware datetimes.")
    
    return dt.astimezone(timezone.utc)


def add_seconds(dt: datetime, seconds: Union[int, float]) -> datetime:
    """
    Add seconds to a datetime, preserving timezone.
    
    Args:
        dt: Base datetime
        seconds: Number of seconds to add (can be negative)
        
    Returns:
        datetime: New datetime with seconds added
    """
    return dt + timedelta(seconds=seconds)


def is_expired(expiry: datetime, buffer_seconds: float = 0) -> bool:
    """
    Check if a datetime has expired (is in the past).
    
    Args:
        expiry: Expiry datetime to check
        buffer_seconds: Optional buffer to subtract from current time
        
    Returns:
        bool: True if expired, False otherwise
    """
    now = utc_now()
    if buffer_seconds > 0:
        now = add_seconds(now, -buffer_seconds)
    return expiry < now


def seconds_until(target: datetime) -> float:
    """
    Calculate seconds from now until target datetime.
    
    Args:
        target: Target datetime
        
    Returns:
        float: Seconds until target (negative if in past)
    """
    return (target - utc_now()).total_seconds()


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string.
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        str: Human-readable duration (e.g., "2h 15m 30s")
    """
    if seconds < 0:
        return f"-{format_duration(-seconds)}"
    
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    if secs > 0 or not parts:
        parts.append(f"{secs}s")
    
    return " ".join(parts)


# Backward compatibility aliases
def get_utc_timestamp() -> str:
    """DEPRECATED: Use utc_now_iso() instead."""
    return utc_now_iso()


def get_current_time() -> datetime:
    """DEPRECATED: Use utc_now() instead."""
    return utc_now()