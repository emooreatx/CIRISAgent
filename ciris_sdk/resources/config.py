from __future__ import annotations

from typing import List, Optional, Dict, Any

from ..models import ConfigItem, ConfigValue, ConfigOperationResponse
from ..transport import Transport
from ..exceptions import CIRISAPIError


class ConfigResource:
    """Client for interacting with CIRIS configuration endpoints.

    This client handles the simplified /v1/config endpoints with
    transparent role-based filtering for sensitive configuration.
    """

    def __init__(self, transport: Transport):
        self._transport = transport

    async def list_configs(self, include_sensitive: bool = False) -> List[ConfigItem]:
        """List all configuration items.

        Args:
            include_sensitive: Whether to include sensitive configs (requires appropriate role)

        Returns:
            List of configuration items with their current values

        Note:
            Sensitive configurations will be automatically redacted based on
            the authenticated user's role. Use include_sensitive=True to attempt
            to retrieve sensitive values (requires ADMIN role or higher).
        """
        params = {}
        if include_sensitive:
            params["include_sensitive"] = "true"

        resp = await self._transport.request("GET", "/v1/config", params=params)
        configs = []
        for item in resp.json():
            configs.append(ConfigItem(**item))
        return configs

    async def get_config(self, key: str) -> ConfigValue:
        """Get a specific configuration value by key.

        Args:
            key: The configuration key to retrieve

        Returns:
            The configuration value

        Raises:
            CIRISAPIError: If the configuration key does not exist

        Note:
            Sensitive values will be automatically redacted based on
            the authenticated user's role.
        """
        resp = await self._transport.request("GET", f"/v1/config/{key}")
        return ConfigValue(**resp.json())

    async def set_config(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None,
        sensitive: bool = False
    ) -> ConfigOperationResponse:
        """Set a configuration value.

        Args:
            key: The configuration key to set
            value: The value to set (can be any JSON-serializable type)
            description: Optional description of the configuration
            sensitive: Whether this configuration contains sensitive data

        Returns:
            Response indicating success/failure of the operation

        Note:
            Setting configuration requires appropriate permissions.
            Sensitive configurations require ADMIN role or higher.
        """
        payload = {
            "value": value,
            "sensitive": sensitive
        }
        if description:
            payload["description"] = description

        resp = await self._transport.request("PUT", f"/v1/config/{key}", json=payload)
        return ConfigOperationResponse(**resp.json())

    async def delete_config(self, key: str) -> ConfigOperationResponse:
        """Delete a configuration key.

        Args:
            key: The configuration key to delete

        Returns:
            Response indicating success/failure of the operation

        Note:
            Deleting configuration requires ADMIN role or higher.
            Some system configurations may be protected from deletion.
        """
        resp = await self._transport.request("DELETE", f"/v1/config/{key}")
        return ConfigOperationResponse(**resp.json())

    async def update_config(
        self,
        key: str,
        value: Any,
        description: Optional[str] = None
    ) -> ConfigOperationResponse:
        """Update an existing configuration value.

        This is an alias for set_config() for convenience.

        Args:
            key: The configuration key to update
            value: The new value
            description: Optional updated description

        Returns:
            Response indicating success/failure of the operation
        """
        return await self.set_config(key, value, description)

    async def bulk_set(self, configs: Dict[str, Any]) -> Dict[str, ConfigOperationResponse]:
        """Set multiple configuration values at once.

        Args:
            configs: Dictionary mapping configuration keys to values

        Returns:
            Dictionary mapping keys to their operation responses

        Note:
            This performs individual set operations for each config.
            Partial success is possible - check individual responses.
        """
        results = {}
        for key, value in configs.items():
            try:
                results[key] = await self.set_config(key, value)
            except CIRISAPIError as e:
                # Create error response for failed operations
                results[key] = ConfigOperationResponse(
                    success=False,
                    message=str(e),
                    key=key
                )
        return results

    async def search_configs(self, pattern: str) -> List[ConfigItem]:
        """Search for configuration keys matching a pattern.

        Args:
            pattern: Search pattern (supports wildcards)

        Returns:
            List of matching configuration items

        Note:
            This is a client-side search that first fetches all configs
            then filters them. For large config sets, consider pagination.
        """
        all_configs = await self.list_configs()

        # Simple pattern matching (could be enhanced)
        import fnmatch
        matching = []
        for config in all_configs:
            if fnmatch.fnmatch(config.key.lower(), pattern.lower()):
                matching.append(config)

        return matching
