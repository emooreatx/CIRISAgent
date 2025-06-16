"""Protocol interface for runtime control operations."""
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List

from ciris_engine.schemas.runtime_control_schemas import (
    ProcessorControlResponse, AdapterOperationResponse, ConfigOperationResponse,
    ConfigValidationResponse, ConfigBackupResponse, RuntimeStatusResponse, 
    RuntimeStateSnapshot, ConfigScope, ConfigValidationLevel
)


class RuntimeControlInterface(ABC):
    """Interface for runtime control operations."""

    @abstractmethod
    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        pass

    @abstractmethod
    async def pause_processing(self) -> ProcessorControlResponse:
        """Pause the processor."""
        pass

    @abstractmethod
    async def resume_processing(self) -> ProcessorControlResponse:
        """Resume the processor."""
        pass

    @abstractmethod
    async def get_processor_queue_status(self) -> Dict[str, Any]:
        """Get processor queue status."""
        pass

    @abstractmethod
    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: str,
        config: Dict[str, Any],
        auto_start: bool = True
    ) -> AdapterOperationResponse:
        """Load a new adapter instance."""
        pass

    @abstractmethod
    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterOperationResponse:
        """Unload an adapter instance."""
        pass

    @abstractmethod
    async def list_adapters(self) -> List[Dict[str, Any]]:
        """List all loaded adapters."""
        pass

    @abstractmethod
    async def get_adapter_info(self, adapter_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific adapter."""
        pass

    @abstractmethod
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get configuration value(s)."""
        pass

    @abstractmethod
    async def update_config(
        self,
        path: str,
        value: Any,
        scope: ConfigScope = ConfigScope.RUNTIME,
        validation_level: ConfigValidationLevel = ConfigValidationLevel.STRICT,
        reason: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update a configuration value."""
        pass

    @abstractmethod
    async def validate_config(
        self,
        config_data: Dict[str, Any],
        config_path: Optional[str] = None
    ) -> ConfigValidationResponse:
        """Validate configuration data."""
        pass


    # Backup and Restore
    @abstractmethod
    async def backup_config(
        self,
        backup_name: Optional[str] = None
    ) -> ConfigBackupResponse:
        """Create a configuration backup."""
        pass

    @abstractmethod
    async def get_runtime_status(self) -> RuntimeStatusResponse:
        """Get current runtime status."""
        pass

    @abstractmethod
    async def get_runtime_snapshot(self) -> RuntimeStateSnapshot:
        """Get complete runtime state snapshot."""
        pass
