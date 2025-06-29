from __future__ import annotations

from typing import List, Optional, Dict, Any

from ..models import (
    ProcessorControlResponse, AdapterInfo, AdapterLoadRequest,
    AdapterOperationResponse, RuntimeStatus, ConfigOperationResponse
)
from ..transport import Transport

class RuntimeResource:
    def __init__(self, transport: Transport):
        self._transport = transport

    # Processor Control Methods
    async def single_step(self) -> ProcessorControlResponse:
        """Execute a single processing step."""
        resp = await self._transport.request("POST", "/v1/runtime/processor/step")
        return ProcessorControlResponse(**resp.json())

    async def pause_processing(self) -> ProcessorControlResponse:
        """Pause the processor."""
        resp = await self._transport.request("POST", "/v1/runtime/processor/pause")
        return ProcessorControlResponse(**resp.json())

    async def resume_processing(self) -> ProcessorControlResponse:
        """Resume the processor."""
        resp = await self._transport.request("POST", "/v1/runtime/processor/resume")
        return ProcessorControlResponse(**resp.json())

    async def shutdown_runtime(self, reason: str = "SDK shutdown request") -> ProcessorControlResponse:
        """Shutdown the entire runtime system."""
        payload = {"reason": reason}
        resp = await self._transport.request("POST", "/v1/runtime/processor/shutdown", json=payload)
        return ProcessorControlResponse(**resp.json())

    async def get_queue_status(self) -> Dict[str, Any]:
        """Get processor queue status."""
        resp = await self._transport.request("GET", "/v1/runtime/processor/queue")
        return resp.json()

    # Adapter Management Methods
    async def load_adapter(
        self,
        adapter_type: str,
        adapter_id: Optional[str] = None,
        config: Dict[str, Any] = None,
        auto_start: bool = True
    ) -> AdapterOperationResponse:
        """Load a new adapter instance."""
        payload = AdapterLoadRequest(
            adapter_type=adapter_type,
            adapter_id=adapter_id,
            config=config or {},
            auto_start=auto_start
        ).model_dump(exclude_none=True)

        resp = await self._transport.request("POST", "/v1/runtime/adapters", json=payload)
        return AdapterOperationResponse(**resp.json())

    async def unload_adapter(
        self,
        adapter_id: str,
        force: bool = False
    ) -> AdapterOperationResponse:
        """Unload an adapter instance."""
        params = {"force": str(force).lower()} if force else {}
        resp = await self._transport.request(
            "DELETE",
            f"/v1/runtime/adapters/{adapter_id}",
            params=params
        )
        return AdapterOperationResponse(**resp.json())

    async def list_adapters(self) -> List[AdapterInfo]:
        """List all loaded adapters."""
        resp = await self._transport.request("GET", "/v1/runtime/adapters")
        adapters = []
        for adapter_data in resp.json():
            adapters.append(AdapterInfo(**adapter_data))
        return adapters

    async def get_adapter_info(self, adapter_id: str) -> Optional[AdapterInfo]:
        """Get detailed information about a specific adapter."""
        resp = await self._transport.request("GET", f"/v1/runtime/adapters/{adapter_id}")
        data = resp.json()
        if data and not data.get("error"):
            return AdapterInfo(**data)
        return None

    # Configuration Management Methods
    async def get_config(
        self,
        path: Optional[str] = None,
        include_sensitive: bool = False
    ) -> Dict[str, Any]:
        """Get configuration value(s)."""
        params = {}
        if path:
            params["path"] = path
        if include_sensitive:
            params["include_sensitive"] = "true"

        resp = await self._transport.request("GET", "/v1/runtime/config", params=params)
        return resp.json()

    async def update_config(
        self,
        path: str,
        value: Any,
        scope: str = "runtime",
        validation_level: str = "strict",
        reason: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update a configuration value."""
        payload = {
            "path": path,
            "value": value,
            "scope": scope,
            "validation_level": validation_level
        }
        if reason:
            payload["reason"] = reason

        resp = await self._transport.request("PUT", "/v1/runtime/config", json=payload)
        return ConfigOperationResponse(**resp.json())

    async def validate_config(
        self,
        config_data: Dict[str, Any],
        config_path: Optional[str] = None
    ) -> Dict[str, Any]:
        """Validate configuration data."""
        payload = {"config_data": config_data}
        if config_path:
            payload["config_path"] = config_path

        resp = await self._transport.request("POST", "/v1/runtime/config/validate", json=payload)
        return resp.json()

    async def reload_config(self) -> ConfigOperationResponse:
        """Reload configuration from files."""
        resp = await self._transport.request("POST", "/v1/runtime/config/reload")
        return ConfigOperationResponse(**resp.json())

    # Agent Profile Management
    async def list_profiles(self) -> List[Dict[str, Any]]:
        """List all available agent profiles."""
        resp = await self._transport.request("GET", "/v1/runtime/profiles")
        return resp.json()

    async def load_profile(
        self,
        profile_name: str,
        config_path: Optional[str] = None,
        scope: str = "session"
    ) -> ConfigOperationResponse:
        """Load an agent profile."""
        payload = {"scope": scope}
        if config_path:
            payload["config_path"] = config_path

        resp = await self._transport.request(
            "POST",
            f"/v1/runtime/profiles/{profile_name}/load",
            json=payload
        )
        return ConfigOperationResponse(**resp.json())

    async def get_profile(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """Get information about a specific agent profile."""
        resp = await self._transport.request("GET", f"/v1/runtime/profiles/{profile_name}")
        data = resp.json()
        if data and not data.get("error"):
            return data
        return None

    async def create_profile(
        self,
        profile_name: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Create a new agent profile."""
        payload = {
            "name": profile_name,
            **profile_data
        }
        resp = await self._transport.request("POST", "/v1/runtime/profiles", json=payload)
        return resp.json()

    async def update_profile(
        self,
        profile_name: str,
        profile_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Update an existing agent profile."""
        resp = await self._transport.request("PUT", f"/v1/runtime/profiles/{profile_name}", json=profile_data)
        return resp.json()

    async def delete_profile(self, profile_name: str) -> Dict[str, Any]:
        """Delete an agent profile."""
        resp = await self._transport.request("DELETE", f"/v1/runtime/profiles/{profile_name}")
        return resp.json()

    # Configuration Backup/Restore
    async def backup_config(
        self,
        include_profiles: bool = True,
        backup_name: Optional[str] = None
    ) -> Dict[str, Any]:
        """Create a configuration backup."""
        payload = {
            "include_profiles": include_profiles
        }
        if backup_name:
            payload["backup_name"] = backup_name

        resp = await self._transport.request("POST", "/v1/runtime/config/backup", json=payload)
        return resp.json()

    async def restore_config(
        self,
        backup_name: str,
        restore_profiles: bool = True,
        restore_env_vars: bool = False,
        restart_required: bool = True
    ) -> Dict[str, Any]:
        """Restore configuration from backup."""
        payload = {
            "backup_name": backup_name,
            "restore_profiles": restore_profiles,
            "restore_env_vars": restore_env_vars,
            "restart_required": restart_required
        }
        resp = await self._transport.request("POST", "/v1/runtime/config/restore", json=payload)
        return resp.json()

    async def list_config_backups(self) -> List[Dict[str, Any]]:
        """List available configuration backups."""
        resp = await self._transport.request("GET", "/v1/runtime/config/backups")
        return resp.json()

    # Runtime Status & Monitoring
    async def get_runtime_status(self) -> RuntimeStatus:
        """Get current runtime status."""
        resp = await self._transport.request("GET", "/v1/runtime/status")
        return RuntimeStatus(**resp.json())

    async def get_runtime_snapshot(self) -> Dict[str, Any]:
        """Get complete runtime state snapshot."""
        resp = await self._transport.request("GET", "/v1/runtime/snapshot")
        return resp.json()
