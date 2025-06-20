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
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult, MemoryQuery
from ciris_engine.protocols.services import MemoryService
from ciris_engine.schemas.protocol_schemas_v1 import IdentityUpdateRequest, EnvironmentUpdateRequest, TimeSeriesDataPoint
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

    async def recall(self, recall_query: MemoryQuery) -> List[GraphNode]:
        """Recall nodes from memory based on query."""
        try:
            # Get the primary node
            stored = persistence.get_graph_node(recall_query.node_id, recall_query.scope, db_path=self.db_path)
            if not stored:
                return []
            
            # Process secrets in the node's attributes
            if stored.attributes:
                processed_attrs = await self._process_secrets_for_recall(stored.attributes, "recall")
                stored = GraphNode(
                    id=stored.id,
                    type=stored.type,
                    scope=stored.scope,
                    attributes=processed_attrs
                )
            
            nodes = [stored]
            
            # If include_edges is True, fetch connected nodes up to specified depth
            if recall_query.include_edges and recall_query.depth > 0:
                # TODO: Implement graph traversal for connected nodes
                pass
            
            return nodes
        except Exception as e:
            logger.exception("Error recalling nodes for query %s: %s", recall_query.node_id, e)
            return []

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

    async def export_identity_context(self) -> str:
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

    async def update_identity_graph(self, update_data: IdentityUpdateRequest) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        from datetime import datetime, timezone
        
        # Validate the update request
        if update_data.source != "wa" or not update_data.node_id:
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Identity updates require WA source and node_id"
            )
        
        try:
            # Apply the updates to the specified node
            existing_node = persistence.get_graph_node(
                update_data.node_id, 
                GraphScope.IDENTITY, 
                db_path=self.db_path
            )
            
            if existing_node:
                # Update existing node attributes
                attrs = existing_node.attributes or {}
                attrs.update(update_data.updates)
                attrs["updated_by"] = update_data.source
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                attrs["update_reason"] = update_data.reason
                
                updated_node = GraphNode(
                    id=update_data.node_id,
                    type=existing_node.type,
                    scope=GraphScope.IDENTITY,
                    attributes=attrs,
                )
                persistence.add_graph_node(updated_node, db_path=self.db_path)
                
                return MemoryOpResult(
                    status=MemoryOpStatus.OK,
                    data={
                        "node_updated": update_data.node_id,
                        "updates_applied": len(update_data.updates)
                    }
                )
            else:
                # Create new node if it doesn't exist
                attrs = update_data.updates.copy()
                attrs["created_by"] = update_data.source
                attrs["created_at"] = datetime.now(timezone.utc).isoformat()
                if update_data.reason:
                    attrs["creation_reason"] = update_data.reason
                
                new_node = GraphNode(
                    id=update_data.node_id,
                    type=NodeType.CONCEPT,
                    scope=GraphScope.IDENTITY,
                    attributes=attrs,
                )
                persistence.add_graph_node(new_node, db_path=self.db_path)
                
                return MemoryOpResult(
                    status=MemoryOpStatus.OK,
                    data={
                        "node_created": update_data.node_id,
                        "attributes_set": len(update_data.updates)
                    }
                )
                
        except Exception as e:
            logger.error(f"Error updating identity graph: {e}")
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                error=str(e)
            )

    async def update_environment_graph(self, update_data: EnvironmentUpdateRequest) -> MemoryOpResult:
        """Update environment graph based on adapter data."""
        from datetime import datetime, timezone
        
        try:
            # Create node ID from adapter type and timestamp
            node_id = f"env_{update_data.adapter_type}_{int(update_data.timestamp.timestamp())}"
            
            # Merge environment data with metadata
            attrs = update_data.environment_data.copy()
            attrs.update({
                "adapter_type": update_data.adapter_type,
                "timestamp": update_data.timestamp.isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat()
            })
            
            env_node = GraphNode(
                id=node_id,
                type=NodeType.CONCEPT,
                scope=GraphScope.ENVIRONMENT,
                attributes=attrs,
            )
            persistence.add_graph_node(env_node, db_path=self.db_path)
            
            # Create edges based on environment data
            edges_created = 0
            
            # If location is provided in environment_data, create location edge
            if "location" in update_data.environment_data:
                location = update_data.environment_data["location"]
                location_edge = GraphEdge(
                    source=node_id,
                    target=f"location_{location}",
                    relationship="measured_at",
                    scope=GraphScope.ENVIRONMENT,
                    weight=1.0,
                    attributes={"adapter_type": update_data.adapter_type}
                )
                persistence.add_graph_edge(location_edge, db_path=self.db_path)
                edges_created += 1
            
            return MemoryOpResult(
                status=MemoryOpStatus.OK,
                data={
                    "node_updated": node_id,
                    "edges_created": edges_created,
                    "environment_data_keys": list(update_data.environment_data.keys())
                }
            )
            
        except Exception as e:
            logger.error(f"Error updating environment graph: {e}")
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                error=str(e)
            )

    def _validate_identity_update(self, update_data: IdentityUpdateRequest) -> bool:
        """Validate identity update structure."""
        # With typed schema, basic validation is handled by Pydantic
        # Additional business logic validation can go here
        if update_data.source != "wa":
            return False
        if not update_data.node_id:
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
    
    async def recall_timeseries(self, scope: str = "default", hours: int = 24, correlation_types: Optional[List[str]] = None) -> List[TimeSeriesDataPoint]:
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
            
            # Convert to TimeSeriesDataPoint objects
            data_points: List[TimeSeriesDataPoint] = []
            for corr in all_correlations:
                # Ensure we have the required fields
                timestamp = corr.get('timestamp')
                if not isinstance(timestamp, datetime):
                    continue  # Skip invalid entries
                    
                metric_name = corr.get('metric_name')
                if not metric_name or not isinstance(metric_name, str):
                    continue  # Skip entries without valid metric name
                    
                metric_value = corr.get('metric_value')
                if metric_value is None or not isinstance(metric_value, (int, float)):
                    continue  # Skip entries without valid value
                
                tags_raw = corr.get('tags')
                point_tags: Optional[Dict[str, str]] = None
                if isinstance(tags_raw, dict):
                    # Ensure all tag values are strings
                    point_tags = {str(k): str(v) for k, v in tags_raw.items()}
                
                # Get correlation type and source as strings
                correlation_type = str(corr.get('data_type', 'METRIC_DATAPOINT'))
                source_raw = corr.get('source')
                source: Optional[str] = str(source_raw) if source_raw is not None else None
                
                data_point = TimeSeriesDataPoint(
                    timestamp=timestamp,
                    metric_name=metric_name,
                    value=float(metric_value),
                    correlation_type=correlation_type,
                    tags=point_tags,
                    source=source
                )
                data_points.append(data_point)
            
            # Sort by timestamp
            data_points.sort(key=lambda x: x.timestamp)
            
            return data_points
            
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


