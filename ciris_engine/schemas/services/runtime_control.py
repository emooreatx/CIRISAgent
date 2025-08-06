"""
Runtime control service schemas for type-safe operations.

This module provides Pydantic models to replace Dict[str, Any] usage
in the runtime control service, ensuring full type safety and validation.
"""

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional, Union

from pydantic import BaseModel, Field


class CircuitBreakerState(str, Enum):
    """States of a circuit breaker."""

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerStatus(BaseModel):
    """Status information for a circuit breaker."""

    state: CircuitBreakerState = Field(..., description="Current state of the circuit breaker")
    failure_count: int = Field(0, description="Number of consecutive failures")
    last_failure_time: Optional[datetime] = Field(None, description="Time of last failure")
    last_success_time: Optional[datetime] = Field(None, description="Time of last success")
    half_open_retry_time: Optional[datetime] = Field(None, description="When to retry in half-open state")
    trip_threshold: int = Field(5, description="Number of failures before tripping")
    reset_timeout_seconds: float = Field(60.0, description="Seconds before attempting reset")
    service_name: str = Field(..., description="Name of the service this breaker protects")


class ConfigValueMap(BaseModel):
    """Typed map for configuration values."""

    configs: Dict[str, Union[str, int, float, bool, list, dict]] = Field(
        default_factory=dict, description="Configuration key-value pairs with typed values"
    )

    def get(
        self, key: str, default: Optional[Union[str, int, float, bool, list, dict]] = None
    ) -> Optional[Union[str, int, float, bool, list, dict]]:
        """Get a configuration value with optional default."""
        return self.configs.get(key, default)

    def set(self, key: str, value: Union[str, int, float, bool, list, dict]) -> None:
        """Set a configuration value."""
        self.configs[key] = value

    def update(self, values: Dict[str, Union[str, int, float, bool, list, dict]]) -> None:
        """Update multiple configuration values."""
        self.configs.update(values)

    def keys(self) -> List[str]:
        """Get all configuration keys."""
        return list(self.configs.keys())

    def items(self) -> List[tuple]:
        """Get all key-value pairs."""
        return list(self.configs.items())


class ServiceProviderUpdate(BaseModel):
    """Details of a service provider update."""

    service_type: str = Field(..., description="Type of service")
    old_priority: str = Field(..., description="Previous priority")
    new_priority: str = Field(..., description="New priority")
    old_priority_group: int = Field(..., description="Previous priority group")
    new_priority_group: int = Field(..., description="New priority group")
    old_strategy: str = Field(..., description="Previous selection strategy")
    new_strategy: str = Field(..., description="New selection strategy")


class ServicePriorityUpdateResponse(BaseModel):
    """Response from service priority update operation."""

    success: bool = Field(..., description="Whether the update succeeded")
    message: Optional[str] = Field(None, description="Success or error message")
    provider_name: str = Field(..., description="Name of the service provider")
    changes: Optional[ServiceProviderUpdate] = Field(None, description="Details of changes made")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    error: Optional[str] = Field(None, description="Error message if operation failed")


class CircuitBreakerResetResponse(BaseModel):
    """Response from circuit breaker reset operation."""

    success: bool = Field(..., description="Whether the reset succeeded")
    message: str = Field(..., description="Operation result message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    service_type: Optional[str] = Field(None, description="Service type if specified")
    reset_count: Optional[int] = Field(None, description="Number of breakers reset")
    error: Optional[str] = Field(None, description="Error message if operation failed")


class ServiceProviderInfo(BaseModel):
    """Information about a registered service provider."""

    name: str = Field(..., description="Provider name")
    priority: str = Field(..., description="Priority level name")
    priority_group: int = Field(..., description="Priority group number")
    strategy: str = Field(..., description="Selection strategy")
    capabilities: Optional[Dict[str, Union[str, int, float, bool, list]]] = Field(
        None, description="Provider capabilities"
    )
    metadata: Optional[Dict[str, Union[str, int, float, bool]]] = Field(None, description="Provider metadata")
    circuit_breaker_state: Optional[str] = Field(None, description="Circuit breaker state if available")


class ServiceRegistryInfoResponse(BaseModel):
    """Enhanced service registry information response."""

    total_services: int = Field(0, description="Total registered services")
    services_by_type: Dict[str, int] = Field(default_factory=dict, description="Count by service type")
    handlers: Dict[str, Dict[str, List[ServiceProviderInfo]]] = Field(
        default_factory=dict, description="Handlers and their services with details"
    )
    global_services: Optional[Dict[str, List[ServiceProviderInfo]]] = Field(
        None, description="Global services not tied to specific handlers"
    )
    healthy_services: int = Field(0, description="Number of healthy services")
    circuit_breaker_states: Dict[str, str] = Field(
        default_factory=dict, description="Circuit breaker states by service"
    )
    error: Optional[str] = Field(None, description="Error message if query failed")


class WAPublicKeyMap(BaseModel):
    """Map of Wise Authority IDs to their public keys."""

    keys: Dict[str, str] = Field(
        default_factory=dict, description="Mapping of WA ID to Ed25519 public key (PEM format)"
    )

    def add_key(self, wa_id: str, public_key_pem: str) -> None:
        """Add a WA public key."""
        self.keys[wa_id] = public_key_pem

    def get_key(self, wa_id: str) -> Optional[str]:
        """Get a WA public key by ID."""
        return self.keys.get(wa_id)

    def has_key(self, wa_id: str) -> bool:
        """Check if a WA ID has a registered key."""
        return wa_id in self.keys

    def clear(self) -> None:
        """Clear all keys."""
        self.keys.clear()

    def count(self) -> int:
        """Get the number of registered keys."""
        return len(self.keys)


class ConfigBackupData(BaseModel):
    """Data structure for configuration backups."""

    configs: Dict[str, Union[str, int, float, bool, list, dict]] = Field(
        ..., description="Backed up configuration values"
    )
    backup_timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc), description="When the backup was created"
    )
    backup_version: str = Field(..., description="Version of the configuration")
    backup_by: str = Field("RuntimeControlService", description="Who created the backup")

    def to_config_value(self) -> dict:
        """Convert to a format suitable for storage as a config value."""
        return {
            "configs": self.configs,
            "backup_timestamp": self.backup_timestamp.isoformat(),
            "backup_version": self.backup_version,
            "backup_by": self.backup_by,
        }

    @classmethod
    def from_config_value(cls, data: dict) -> "ConfigBackupData":
        """Create from a stored config value."""
        return cls(
            configs=data.get("configs", {}),
            backup_timestamp=datetime.fromisoformat(data["backup_timestamp"]),
            backup_version=data["backup_version"],
            backup_by=data.get("backup_by", "RuntimeControlService"),
        )


class ProcessingQueueItem(BaseModel):
    """
    Information about an item in the processing queue.
    Used for runtime control service to report queue status.
    """

    item_id: str = Field(..., description="Unique identifier for the queue item")
    item_type: str = Field(..., description="Type of item (e.g., thought, task, message)")
    priority: int = Field(0, description="Processing priority (higher = more urgent)")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = Field(None, description="When processing started")
    status: str = Field("pending", description="Item status: pending, processing, completed, failed")
    source: Optional[str] = Field(None, description="Source of the queue item")
    metadata: Dict[str, Union[str, int, float, bool]] = Field(
        default_factory=dict, description="Additional item metadata"
    )
