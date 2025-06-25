"""Configuration Service Protocol."""

from typing import Protocol, Dict, List, Optional, Union, TYPE_CHECKING
from abc import abstractmethod

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