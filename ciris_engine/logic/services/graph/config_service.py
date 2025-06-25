"""
Graph Configuration Service for CIRIS Trinity Architecture.

All configuration is stored as memories in the graph, with full history tracking.
This replaces the old config_manager_service and agent_config_service.
"""
import logging
from typing import Dict, List, Optional, Union

from ciris_engine.protocols.services.graph.config import GraphConfigServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.services.nodes import ConfigNode
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class GraphConfigService(GraphConfigServiceProtocol, ServiceProtocol):
    """Configuration service that stores all config as graph memories."""
    
    def __init__(self, graph_memory_service: LocalGraphMemoryService, time_service: TimeServiceProtocol):
        """Initialize with graph memory service."""
        self.graph = graph_memory_service
        self._running = False
        self._time_service = time_service
        
    async def start(self) -> None:
        """Start the service."""
        self._running = True
        
    async def stop(self) -> None:
        """Stop the service."""
        self._running = False
        # Nothing to clean up
        
    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="GraphConfigService",
            actions=[
                "get_config",
                "set_config", 
                "list_configs"
            ],
            version="1.0.0",
            dependencies=["GraphMemoryService", "TimeService"]
        )
        
    def get_status(self) -> ServiceStatus:
        """Get service status."""
        return ServiceStatus(
            service_name="GraphConfigService",
            service_type="graph_service",
            is_healthy=self._running,
            uptime_seconds=0.0,  # TODO: Track uptime
            metrics={
                "total_configs": 0  # TODO: Track configs
            }
        )
        
    async def store_in_graph(self, node: ConfigNode) -> str:
        """Store config node in graph."""
        # Convert typed node to GraphNode for storage
        graph_node = node.to_graph_node()
        result = await self.graph.memorize(graph_node)
        # MemoryOpResult has data field, not node_id
        if result.status == "ok" and result.data:
            return result.data if isinstance(result.data, str) else str(result.data)
        return ""
        
    async def query_graph(self, query: dict) -> List[ConfigNode]:
        """Query config nodes from graph."""
        # Get all config nodes (use lowercase enum value)
        nodes = await self.graph.search("type:config")
        
        # Convert GraphNodes to ConfigNodes
        config_nodes = []
        for node in nodes:
            try:
                config_node = ConfigNode.from_graph_node(node)
                
                # Apply query filters
                matches = True
                for k, v in query.items():
                    if k == "key" and config_node.key != v:
                        matches = False
                        break
                    elif k == "version" and config_node.version != v:
                        matches = False
                        break
                
                if matches:
                    config_nodes.append(config_node)
            except Exception as e:
                # Skip nodes that can't be converted (might be old format)
                logger.warning(f"Failed to convert node {node.id} to ConfigNode: {e}")
                continue
        
        return config_nodes
        
    def get_node_type(self) -> str:
        """Get the node type this service manages."""
        return "CONFIG"
        
    async def get_config(self, key: str) -> Optional[ConfigNode]:
        """Get current configuration value."""
        # Find latest version
        nodes = await self.query_graph({"key": key})
        if not nodes:
            return None
            
        # Sort by version, get latest
        nodes.sort(key=lambda n: n.version, reverse=True)
        return nodes[0]
        
    async def set_config(self, key: str, value: Union[str, int, float, bool, List, Dict], updated_by: str) -> None:
        """Set configuration value with history."""
        import uuid
        from ciris_engine.schemas.services.graph_core import GraphScope
        from ciris_engine.schemas.services.nodes import ConfigValue
        
        # Get current version
        current = await self.get_config(key)
        
        # Wrap value in ConfigValue
        from pathlib import Path
        config_value = ConfigValue()
        if isinstance(value, str):
            config_value.string_value = value
        elif isinstance(value, Path):
            config_value.string_value = str(value)  # Convert Path to string
        elif isinstance(value, bool):  # Check bool before int (bool is subclass of int)
            config_value.bool_value = value
        elif isinstance(value, int):
            config_value.int_value = value
        elif isinstance(value, float):
            config_value.float_value = value
        elif isinstance(value, list):
            config_value.list_value = value
        elif isinstance(value, dict):
            config_value.dict_value = value
        else:
            # Log unexpected type
            logger.warning(f"Unexpected config value type for key {key}: {type(value)} = {value}")
        
        # Check if value has changed
        if current:
            current_value = current.value.value  # Use the @property method
            # Convert Path objects for comparison
            if isinstance(value, Path):
                value = str(value)
            if current_value == value:
                # No change needed
                logger.debug(f"Config {key} unchanged, skipping update")
                return
        
        # Create new config node with all required fields
        new_config = ConfigNode(
            # GraphNode required fields
            id=f"config_{key.replace('.', '_')}_{uuid.uuid4().hex[:8]}",
            # type will use default from ConfigNode
            scope=GraphScope.LOCAL,  # Config is always local scope
            attributes={},  # Empty dict for base GraphNode
            # ConfigNode specific fields
            key=key,
            value=config_value,
            version=(current.version + 1) if current else 1,
            updated_by=updated_by,
            updated_at=self._time_service.now(),
            previous_version=current.id if current else None
        )
        
        # Store in graph (base class will handle conversion)
        await self.store_in_graph(new_config)
        
    
    async def list_configs(self, prefix: Optional[str] = None) -> Dict[str, Union[str, int, float, bool, List, Dict]]:
        """List all configurations with optional prefix filter."""
        # Get all config nodes
        all_configs = await self.query_graph({})
        
        # Group by key to get latest version of each
        config_map: Dict[str, ConfigNode] = {}
        for config in all_configs:
            if prefix and not config.key.startswith(prefix):
                continue
            if config.key not in config_map or config.version > config_map[config.key].version:
                config_map[config.key] = config
        
        # Return key->value mapping
        return {key: node.value for key, node in config_map.items()}
    
    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._running