from __future__ import annotations
import logging
from typing import Optional, Any, Dict, List
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from ciris_engine.config.config_manager import get_sqlite_db_full_path
from ciris_engine.persistence import initialize_database, get_db_connection
from ciris_engine import persistence

from ciris_engine.schemas.graph_schemas_v1 import (
    GraphScope,
    GraphNode,
    NodeType,
    GraphEdge,
    TSDBGraphNode,
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult
from ciris_engine.protocols.services import MemoryService
from ciris_engine.secrets.service import SecretsService

logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


class LocalGraphMemoryService(MemoryService):
    """Graph memory backed by the persistence database."""

    def __init__(self, db_path: Optional[str] = None, secrets_service: Optional[SecretsService] = None) -> None:
        super().__init__()
        self.db_path = db_path or get_sqlite_db_full_path()
        initialize_database(db_path=self.db_path)
        self.secrets_service = secrets_service or SecretsService(db_path=self.db_path.replace('.db', '_secrets.db'))

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def memorize(self, node: GraphNode, *args: Any, **kwargs: Any) -> MemoryOpResult:
        """Store a node with automatic secrets detection and processing."""
        try:
            # Process secrets in node attributes before storing
            processed_node = await self._process_secrets_for_memorize(node)
            
            persistence.add_graph_node(processed_node, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error storing node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def recall(self, node: GraphNode) -> MemoryOpResult:
        """Recall a node with automatic secrets decryption if needed."""
        try:
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                processed_data = await self._process_secrets_for_recall(stored.attributes, "recall")
                return MemoryOpResult(status=MemoryOpStatus.OK, data=processed_data)
            return MemoryOpResult(status=MemoryOpStatus.OK, data=None)
        except Exception as e:
            logger.exception("Error recalling node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def forget(self, node: GraphNode) -> MemoryOpResult:
        """Forget a node and clean up any associated secrets."""
        try:
            # First retrieve the node to check for secrets
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                await self._process_secrets_for_forget(stored.attributes)
            
            persistence.delete_graph_node(node.id, node.scope, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error forgetting node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    def export_identity_context(self) -> str:
        lines: List[Any] = []
        with get_db_connection(db_path=self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_id, attributes_json FROM graph_nodes WHERE scope = ?",
                (GraphScope.IDENTITY.value,)
            )
            for row in cursor.fetchall():
                attrs = json.loads(row["attributes_json"]) if row["attributes_json"] else {}
                lines.append(f"{row['node_id']}: {attrs}")
        return "\n".join(lines)

    async def update_identity_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        from datetime import datetime, timezone
        if not self._validate_identity_update(update_data):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Invalid identity update format"
            )
        if not update_data.get("wa_authorized"):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Identity updates require WA authorization"
            )
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                persistence.delete_graph_node(node_id, GraphScope.IDENTITY, db_path=self.db_path)
            else:
                attrs = node_update.get("attributes", {})
                attrs["updated_by"] = update_data.get("wa_user_id", "unknown")
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                node = GraphNode(
                    id=node_id,
                    type=NodeType.CONCEPT,
                    scope=GraphScope.IDENTITY,
                    attributes=attrs,
                )
                persistence.add_graph_node(node, db_path=self.db_path)

        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            edge_id = f"{source}->{target}->{edge_update.get('relationship','related')}"
            if edge_update.get("action") == "delete":
                persistence.delete_graph_edge(edge_id, db_path=self.db_path)
            else:
                attrs = edge_update.get("attributes", {})
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relationship=edge_update.get("relationship", "related"),
                    scope=GraphScope.IDENTITY,
                    weight=edge_update.get("weight", 1.0),
                    attributes=attrs,
                )
                persistence.add_graph_edge(edge, db_path=self.db_path)

        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    async def update_environment_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update environment graph based on WA feedback."""
        from datetime import datetime, timezone
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                persistence.delete_graph_node(node_id, GraphScope.ENVIRONMENT, db_path=self.db_path)
            else:
                attrs = node_update.get("attributes", {})
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                node = GraphNode(
                    id=node_id,
                    type=NodeType.CONCEPT,
                    scope=GraphScope.ENVIRONMENT,
                    attributes=attrs,
                )
                persistence.add_graph_node(node, db_path=self.db_path)
        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            edge_id = f"{source}->{target}->{edge_update.get('relationship','related')}"
            if edge_update.get("action") == "delete":
                persistence.delete_graph_edge(edge_id, db_path=self.db_path)
            else:
                attrs = edge_update.get("attributes", {})
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relationship=edge_update.get("relationship", "related"),
                    scope=GraphScope.ENVIRONMENT,
                    weight=edge_update.get("weight", 1.0),
                    attributes=attrs,
                )
                persistence.add_graph_edge(edge, db_path=self.db_path)
        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    def _validate_identity_update(self, update_data: Dict[str, Any]) -> bool:
        """Validate identity update structure."""
        required_fields = ["wa_user_id", "wa_authorized", "update_timestamp"]
        if not all(field in update_data for field in required_fields):
            return False
        for node in update_data.get("nodes", []):
            if "id" not in node or "type" not in node:
                return False
            if node["type"] != NodeType.CONCEPT:
                return False
        return True

    async def _process_secrets_for_memorize(self, node: GraphNode) -> GraphNode:
        """Process secrets in node attributes during memorization."""
        if not node.attributes:
            return node
        
        # Convert attributes to JSON string for processing
        attributes_str = json.dumps(node.attributes, cls=DateTimeEncoder)
        
        # Process for secrets detection and replacement
        processed_text, secret_refs = await self.secrets_service.process_incoming_text(
            attributes_str,
            context_hint=f"memorize node_id={node.id} scope={node.scope.value}"
        )
        
        # Create new node with processed attributes
        processed_attributes = json.loads(processed_text) if processed_text != attributes_str else node.attributes
        
        # Add secret references to node metadata if any were found
        if secret_refs:
            processed_attributes.setdefault("_secret_refs", []).extend([ref.uuid for ref in secret_refs])
            logger.info(f"Stored {len(secret_refs)} secret references in memory node {node.id}")
        
        return GraphNode(
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=processed_attributes
        )

    async def _process_secrets_for_recall(self, attributes: Dict[str, Any], action_type: str) -> Dict[str, Any]:
        """Process secrets in recalled attributes for potential decryption."""
        if not attributes:
            return attributes
        
        secret_refs = attributes.get("_secret_refs", [])
        if not secret_refs:
            return attributes
        
        should_decrypt = action_type in getattr(self.secrets_service.filter.detection_config, "auto_decrypt_for_actions", ["speak", "tool"])
        
        if should_decrypt:
            attributes_str = json.dumps(attributes, cls=DateTimeEncoder)
            
            decapsulated_attributes = await self.secrets_service.decapsulate_secrets_in_parameters(
                attributes,
                action_type,
                {
                    "operation": "recall", 
                    "auto_decrypt": True
                }
            )
            
            if decapsulated_attributes != attributes:
                logger.info(f"Auto-decrypted secrets in recalled data for {action_type}")
                # Type assertion: decapsulate_secrets_in_parameters should return dict
                assert isinstance(decapsulated_attributes, dict)
                return decapsulated_attributes
        
        return attributes

    async def _process_secrets_for_forget(self, attributes: Dict[str, Any]) -> None:
        """Clean up secrets when forgetting a node."""
        if not attributes:
            return
        
        # Check for secret references
        secret_refs = attributes.get("_secret_refs", [])
        if secret_refs:
            # Note: We don't automatically delete secrets on FORGET since they might be
            # referenced elsewhere. This would need to be a conscious decision by the agent.
            logger.info(f"Node being forgotten contained {len(secret_refs)} secret references")
            
            # Could implement reference counting here in the future if needed
    
    async def recall_timeseries(self, scope: str = "default", hours: int = 24, correlation_types: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Recall time-series data from TSDB correlations.
        
        Args:
            scope: The memory scope to search (mapped to TSDB tags)
            hours: Number of hours to look back
            correlation_types: Optional filter by correlation types
            
        Returns:
            List of time-series data points from correlations
        """
        try:
            # Import correlation models here to avoid circular imports
            from ciris_engine.persistence.models.correlations import get_correlations_by_type_and_time
            from ciris_engine.schemas.correlation_schemas_v1 import CorrelationType
            
            # Calculate time window
            end_time = datetime.now(timezone.utc)
            start_time = end_time - timedelta(hours=hours)
            
            # Convert to ISO format strings for database query
            start_time_str = start_time.isoformat()
            end_time_str = end_time.isoformat()
            
            # Default correlation types if not specified
            enum_correlation_types: List[CorrelationType]
            if correlation_types is None:
                enum_correlation_types = [CorrelationType.METRIC_DATAPOINT, CorrelationType.LOG_ENTRY, CorrelationType.AUDIT_EVENT]
            else:
                # Convert string types to enum
                enum_correlation_types = []
                for corr_type in correlation_types:
                    try:
                        enum_correlation_types.append(CorrelationType(corr_type))
                    except ValueError:
                        # Try enum name lookup - skip if not valid
                        if hasattr(CorrelationType, corr_type):
                            enum_correlation_types.append(getattr(CorrelationType, corr_type))
                        else:
                            logger.warning(f"Skipping invalid correlation type: {corr_type}")
                            continue
            
            # Query correlations for each type
            all_correlations = []
            for corr_type in enum_correlation_types:
                correlations = get_correlations_by_type_and_time(
                    correlation_type=corr_type,
                    start_time=start_time_str,
                    end_time=end_time_str,
                    limit=1000,  # Large limit for time series data
                    db_path=self.db_path
                )
                
                # Filter by scope if it's in tags
                for correlation in correlations:
                    # Access Pydantic model attributes directly
                    tags = correlation.tags if hasattr(correlation, 'tags') and correlation.tags else {}
                    
                    # Include if scope matches or if no scope filtering requested
                    if scope == "default" or tags.get('scope') == scope:
                        all_correlations.append({
                            'timestamp': correlation.timestamp,
                            'correlation_type': correlation.correlation_type,
                            'metric_name': getattr(correlation, 'metric_name', None),
                            'metric_value': getattr(correlation, 'metric_value', None),
                            'log_level': getattr(correlation, 'log_level', None),
                            'action_type': getattr(correlation, 'action_type', None),
                            'tags': tags,
                            'request_data': getattr(correlation, 'request_data', None),
                            'response_data': getattr(correlation, 'response_data', None),
                            'content': getattr(correlation, 'content', None),
                            'data_type': corr_type.value if hasattr(corr_type, 'value') else str(corr_type)
                        })
            
            # Sort by timestamp - ensure we have a datetime object for comparison
            def get_timestamp_for_sort(item: Dict[str, Any]) -> datetime:
                ts = item.get('timestamp')
                if isinstance(ts, datetime):
                    return ts
                return datetime.min.replace(tzinfo=timezone.utc)
            
            all_correlations.sort(key=get_timestamp_for_sort)
            
            return all_correlations
            
        except Exception as e:
            logger.exception(f"Error recalling timeseries data: {e}")
            return []
    
    async def memorize_metric(self, metric_name: str, value: float, tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """
        Convenience method to memorize a metric as both a graph node and TSDB correlation.
        """
        try:
            # Import correlation models here to avoid circular imports
            from ciris_engine.persistence.models.correlations import add_correlation
            from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus
            
            # Create specialized TSDB graph node for the metric
            node = TSDBGraphNode.create_metric_node(
                metric_name=metric_name,
                value=value,
                tags=tags,
                scope=GraphScope(scope),
                retention_policy="raw"
            )
            
            # Store in graph memory
            memory_result = await self.memorize(node)
            
            # Also store as TSDB correlation
            correlation = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="memory",
                handler_name="memory_service",
                action_type="memorize_metric",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=datetime.now(timezone.utc),
                metric_name=metric_name,
                metric_value=value,
                tags={**tags, "scope": scope} if tags else {"scope": scope},
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy="raw"
            )
            
            add_correlation(correlation, db_path=self.db_path)
            
            return memory_result
            
        except Exception as e:
            logger.exception(f"Error memorizing metric {metric_name}: {e}")
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))
    
    async def memorize_log(self, log_message: str, log_level: str = "INFO", tags: Optional[Dict[str, str]] = None, scope: str = "local") -> MemoryOpResult:
        """
        Convenience method to memorize a log entry as both a graph node and TSDB correlation.
        """
        try:
            # Import correlation models here to avoid circular imports
            from ciris_engine.persistence.models.correlations import add_correlation
            from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus
            
            # Create specialized TSDB graph node for the log entry
            node = TSDBGraphNode.create_log_node(
                log_message=log_message,
                log_level=log_level,
                tags=tags,
                scope=GraphScope(scope),
                retention_policy="raw"
            )
            
            # Store in graph memory
            memory_result = await self.memorize(node)
            
            # Also store as TSDB correlation
            correlation = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="memory",
                handler_name="memory_service", 
                action_type="memorize_log",
                correlation_type=CorrelationType.LOG_ENTRY,
                timestamp=datetime.now(timezone.utc),
                log_level=log_level,
                tags={**tags, "scope": scope, "message": log_message} if tags else {"scope": scope, "message": log_message},
                request_data={"message": log_message, "log_level": log_level},
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy="raw"
            )
            
            add_correlation(correlation, db_path=self.db_path)
            
            return memory_result
            
        except Exception as e:
            logger.exception(f"Error memorizing log entry: {e}")
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))


