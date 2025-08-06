"""Configuration Service Protocol."""

from abc import abstractmethod
from typing import TYPE_CHECKING, Callable, Dict, List, Optional, Protocol, Union

from ...runtime.base import GraphServiceProtocol

if TYPE_CHECKING:
    from ciris_engine.schemas.services.nodes import ConfigNode


class GraphConfigServiceProtocol(GraphServiceProtocol, Protocol):
    """Protocol for graph configuration service."""

    @abstractmethod
    async def get_config(self, key: str) -> Optional["ConfigNode"]:
        """Get configuration value."""
        ...

    @abstractmethod
    async def set_config(self, key: str, value: Union[str, int, float, bool, List, Dict], updated_by: str) -> None:
        """Set configuration value."""
        ...

    @abstractmethod
    async def list_configs(self, prefix: Optional[str] = None) -> Dict[str, Union[str, int, float, bool, List, Dict]]:
        """List all configurations with optional prefix filter."""
        ...

    @abstractmethod
    def register_config_listener(self, key_pattern: str, callback: "Callable") -> None:
        """Register a callback for config changes matching the key pattern."""
        ...

    @abstractmethod
    def unregister_config_listener(self, key_pattern: str, callback: "Callable") -> None:
        """Unregister a config change callback."""
        ...
