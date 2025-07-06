from __future__ import annotations
import logging
from typing import Optional, Dict, List, Union, Any, TYPE_CHECKING
import json
from datetime import datetime, timedelta
from uuid import uuid4

# Optional import for psutil
try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    psutil = None  # type: ignore
    PSUTIL_AVAILABLE = False

if TYPE_CHECKING:
    from psutil import Process

from ciris_engine.logic.config import get_sqlite_db_full_path
from ciris_engine.logic.persistence import initialize_database, get_db_connection

from ciris_engine.schemas.services.graph_core import (
    GraphScope,
    GraphNode,
    NodeType,
    GraphNodeAttributes,
)
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.operations import MemoryOpStatus, MemoryOpResult, MemoryQuery
from ciris_engine.protocols.services import MemoryService, GraphMemoryServiceProtocol
from ciris_engine.schemas.runtime.memory import TimeSeriesDataPoint
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.secrets.service import DecapsulationContext
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.graph.memory import (
    MemorySearchFilter
)

logger = logging.getLogger(__name__)

class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles datetime objects."""

    def default(self, obj: object) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

class LocalGraphMemoryService(MemoryService, GraphMemoryServiceProtocol):
    """Graph memory backed by the persistence database."""

    def __init__(self, db_path: Optional[str] = None, secrets_service: Optional[SecretsService] = None, time_service: Optional[TimeServiceProtocol] = None) -> None:
        super().__init__()
        self.db_path = db_path or get_sqlite_db_full_path()
        initialize_database(db_path=self.db_path)
        self._time_service = time_service
        self.secrets_service = secrets_service  # Must be provided, not created here
        self._start_time: Optional[datetime] = None
        self._process: Optional["Process"] = None
        if PSUTIL_AVAILABLE and psutil is not None:
            try:
                self._process = psutil.Process()  # For memory tracking
            except Exception:
                pass  # Failed to create process object

    async def memorize(self, node: GraphNode) -> MemoryOpResult:
        """Store a node with automatic secrets detection and processing."""
        try:
            # Process secrets in node attributes before storing
            processed_node = await self._process_secrets_for_memorize(node)

            from ciris_engine.logic.persistence.models import graph as persistence
            if self._time_service:
                persistence.add_graph_node(processed_node, db_path=self.db_path, time_service=self._time_service)
            else:
                raise RuntimeError("TimeService is required for adding graph nodes")
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error storing node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def recall(self, recall_query: MemoryQuery) -> List[GraphNode]:
        """Recall nodes from memory based on query."""
        try:
            from ciris_engine.logic.persistence.models import graph as persistence
            from ciris_engine.logic.persistence import get_all_graph_nodes, get_nodes_by_type
            
            logger.info(f"[DEBUG] Memory recall called with node_id='{recall_query.node_id}', scope={recall_query.scope}, type={recall_query.type}")
            
            # Check if this is a wildcard query
            if recall_query.node_id in ["*", "%", "all"]:
                logger.info(f"[DEBUG DB TIMING] Memory recall: wildcard query with scope {recall_query.scope}, type {recall_query.type}")
                
                # Use the new get_all_graph_nodes function
                nodes = get_all_graph_nodes(
                    scope=recall_query.scope,
                    node_type=recall_query.type.value if recall_query.type else None,
                    limit=100,  # Reasonable default limit for wildcard queries
                    db_path=self.db_path
                )
                logger.info(f"[DEBUG] Wildcard query returned {len(nodes)} nodes")
                
                # Process secrets for all nodes
                processed_nodes = []
                for node in nodes:
                    if node.attributes:
                        processed_attrs = await self._process_secrets_for_recall(node.attributes, "recall")
                        processed_node = GraphNode(
                            id=node.id,
                            type=node.type,
                            scope=node.scope,
                            attributes=processed_attrs,
                            version=node.version,
                            updated_by=node.updated_by,
                            updated_at=node.updated_at
                        )
                        processed_nodes.append(processed_node)
                    else:
                        processed_nodes.append(node)
                
                return processed_nodes
            
            else:
                # Regular single node query
                logger.info(f"[DEBUG DB TIMING] Memory recall: getting node {recall_query.node_id} scope {recall_query.scope}")
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
                        attributes=processed_attrs,
                        version=stored.version,
                        updated_by=stored.updated_by,
                        updated_at=stored.updated_at
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
            from ciris_engine.logic.persistence.models import graph as persistence
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                await self._process_secrets_for_forget(stored.attributes)

            from ciris_engine.logic.persistence.models import graph as persistence
            persistence.delete_graph_node(node.id, node.scope, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error forgetting node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def export_identity_context(self) -> str:
        lines: List[str] = []
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

    async def _process_secrets_for_memorize(self, node: GraphNode) -> GraphNode:
        """Process secrets in node attributes during memorization."""
        if not node.attributes:
            return node

        # Convert attributes to JSON string for processing
        # Handle both dict and Pydantic model attributes
        if hasattr(node.attributes, 'model_dump'):
            attributes_dict = node.attributes.model_dump()
        else:
            attributes_dict = node.attributes
        attributes_str = json.dumps(attributes_dict, cls=DateTimeEncoder)

        # Process for secrets detection and replacement
        # SecretsService requires source_message_id
        if not self.secrets_service:
            return node
        processed_text, secret_refs = await self.secrets_service.process_incoming_text(
            attributes_str,
            source_message_id=f"memorize_{node.id}"
        )

        # Create new node with processed attributes
        processed_attributes = json.loads(processed_text) if processed_text != attributes_str else node.attributes

        # Add secret references to node metadata if any were found
        if secret_refs:
            if isinstance(processed_attributes, dict):
                processed_attributes.setdefault("_secret_refs", []).extend([ref.uuid for ref in secret_refs])
            logger.info(f"Stored {len(secret_refs)} secret references in memory node {node.id}")

        return GraphNode(
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=processed_attributes,
            version=node.version,
            updated_by=node.updated_by,
            updated_at=node.updated_at
        )

    async def _process_secrets_for_recall(self, attributes: Union[Dict[str, Union[str, int, float, bool, list, dict, None]], GraphNodeAttributes], action_type: str) -> Dict[str, Union[str, int, float, bool, list, dict, None]]:
        """Process secrets in recalled attributes for potential decryption."""
        if not attributes:
            return {}

        # Convert GraphNodeAttributes to dict if needed
        attributes_dict: Dict[str, Any]
        if hasattr(attributes, 'model_dump'):
            attributes_dict = attributes.model_dump()
        elif hasattr(attributes, 'dict'):
            attributes_dict = attributes.dict()
        elif isinstance(attributes, dict):
            attributes_dict = attributes
        else:
            attributes_dict = {}

        secret_refs = attributes_dict.get("_secret_refs", [])
        if not secret_refs:
            return attributes_dict

        should_decrypt = False
        if self.secrets_service and hasattr(self.secrets_service, 'filter'):
            should_decrypt = action_type in getattr(self.secrets_service.filter.detection_config, "auto_decrypt_for_actions", ["speak", "tool"])

        if should_decrypt:
            _attributes_str = json.dumps(attributes_dict, cls=DateTimeEncoder)

            if not self.secrets_service:
                return attributes_dict
            decapsulated_attributes = await self.secrets_service.decapsulate_secrets_in_parameters(
                action_type=action_type,
                action_params=attributes_dict,
                context=DecapsulationContext(
                    action_type=action_type,
                    thought_id="memory_recall",
                    user_id="system"
                )
            )

            if decapsulated_attributes != attributes_dict:
                logger.info(f"Auto-decrypted secrets in recalled data for {action_type}")
                # Type assertion: decapsulate_secrets_in_parameters should return dict
                assert isinstance(decapsulated_attributes, dict)
                return decapsulated_attributes

        return attributes_dict

    async def _process_secrets_for_forget(self, attributes: Union[Dict[str, Union[str, int, float, bool, list, dict, None]], GraphNodeAttributes]) -> None:
        """Clean up secrets when forgetting a node."""
        if not attributes:
            return

        # Convert GraphNodeAttributes to dict if needed
        attributes_dict: Dict[str, Any]
        if hasattr(attributes, 'model_dump'):
            attributes_dict = attributes.model_dump()
        elif hasattr(attributes, 'dict'):
            attributes_dict = attributes.dict()
        elif isinstance(attributes, dict):
            attributes_dict = attributes
        else:
            attributes_dict = {}

        # Check for secret references
        secret_refs = attributes_dict.get("_secret_refs", [])
        if secret_refs:
            # Note: We don't automatically delete secrets on FORGET since they might be
            # referenced elsewhere. This would need to be a conscious decision by the agent.
            if isinstance(secret_refs, list):
                logger.info(f"Node being forgotten contained {len(secret_refs)} secret references")
            else:
                logger.info("Node being forgotten contained secret references")

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
            from ciris_engine.logic.persistence.models.correlations import get_correlations_by_type_and_time
            from ciris_engine.schemas.telemetry.core import CorrelationType

            # Calculate time window
            if not self._time_service:
                raise RuntimeError("TimeService is required for recall_timeseries")
            end_time = self._time_service.now()
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
                        # Extract metric data if available
                        metric_name = None
                        metric_value = None
                        if hasattr(correlation, 'metric_data') and correlation.metric_data:
                            metric_name = correlation.metric_data.metric_name
                            metric_value = correlation.metric_data.metric_value

                        # Extract log level if available
                        log_level = None
                        if hasattr(correlation, 'log_data') and correlation.log_data:
                            log_level = correlation.log_data.log_level

                        all_correlations.append({
                            'timestamp': correlation.timestamp,
                            'correlation_type': correlation.correlation_type,
                            'metric_name': metric_name,
                            'metric_value': metric_value,
                            'log_level': log_level,
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

                metric_name_raw = corr.get('metric_name')
                if not metric_name_raw or not isinstance(metric_name_raw, str):
                    continue  # Skip entries without valid metric name
                metric_name = metric_name_raw

                metric_value_raw = corr.get('metric_value')
                if metric_value_raw is None or not isinstance(metric_value_raw, (int, float)):
                    continue  # Skip entries without valid value
                metric_value = metric_value_raw

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
                    tags=point_tags or {},
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
            from ciris_engine.logic.persistence.models.correlations import add_correlation
            from ciris_engine.schemas.telemetry.core import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus

            # Create a graph node for the metric
            if not self._time_service:
                raise RuntimeError("TimeService is required for memorize_metric")
            now = self._time_service.now()
            node_id = f"metric_{metric_name}_{int(now.timestamp())}"

            # Create typed attributes with metric-specific data
            attrs_dict = {
                "created_at": now,
                "updated_at": now,
                "created_by": "memory_service",
                "tags": ["metric", metric_name],
                "metric_name": metric_name,
                "value": value,
                "metric_tags": tags or {},
                "retention_policy": "raw"
            }

            node = GraphNode(
                id=node_id,
                type=NodeType.TSDB_DATA,
                scope=GraphScope(scope),
                attributes=attrs_dict,
                updated_by="memory_service",
                updated_at=now
            )

            # Store in graph memory
            memory_result = await self.memorize(node)

            # Also store as TSDB correlation
            from ciris_engine.schemas.telemetry.core import MetricData

            correlation = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="memory",
                handler_name="memory_service",
                action_type="memorize_metric",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=now,
                created_at=now,
                updated_at=now,
                metric_data=MetricData(
                    metric_name=metric_name,
                    metric_value=value,
                    metric_unit="count",  # Default unit
                    metric_type="gauge",
                    labels=tags or {},
                    min_value=value,
                    max_value=value,
                    mean_value=value
                ),
                tags={**tags, "scope": scope} if tags else {"scope": scope},
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy="raw",
                request_data=None,
                response_data=None,
                log_data=None,
                trace_context=None,
                ttl_seconds=None,
                parent_correlation_id=None
            )

            if self._time_service:
                add_correlation(correlation, db_path=self.db_path, time_service=self._time_service)
            else:
                raise RuntimeError("TimeService is required for add_correlation")

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
            from ciris_engine.logic.persistence.models.correlations import add_correlation
            from ciris_engine.schemas.telemetry.core import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus

            # Create a graph node for the log entry
            if not self._time_service:
                raise RuntimeError("TimeService is required for memorize_log")
            now = self._time_service.now()
            node_id = f"log_{log_level}_{int(now.timestamp())}"

            # Create typed attributes with log-specific data
            attrs_dict = {
                "created_at": now,
                "updated_at": now,
                "created_by": "memory_service",
                "tags": ["log", log_level.lower()],
                "log_message": log_message,
                "log_level": log_level,
                "log_tags": tags or {},
                "retention_policy": "raw"
            }

            node = GraphNode(
                id=node_id,
                type=NodeType.TSDB_DATA,
                scope=GraphScope(scope),
                attributes=attrs_dict,
                updated_by="memory_service",
                updated_at=now
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
                timestamp=now,
                created_at=now,
                updated_at=now,
                tags={**tags, "scope": scope, "message": log_message} if tags else {"scope": scope, "message": log_message},
                status=ServiceCorrelationStatus.COMPLETED,
                retention_policy="raw",
                request_data=None,
                response_data=None,
                metric_data=None,
                log_data=None,
                trace_context=None,
                ttl_seconds=None,
                parent_correlation_id=None
            )

            if self._time_service:
                add_correlation(correlation, db_path=self.db_path, time_service=self._time_service)
            else:
                raise RuntimeError("TimeService is required for add_correlation")

            return memory_result

        except Exception as e:
            logger.exception(f"Error memorizing log entry: {e}")
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    # ============================================================================
    # GRAPH PROTOCOL METHODS
    # ============================================================================

    async def search(self, query: str, filters: Optional[MemorySearchFilter] = None) -> List[GraphNode]:
        """Search memories in the graph."""
        logger.info(f"[DEBUG DB TIMING] Memory search START: query='{query}', filters={filters}")
        try:
            from ciris_engine.logic.persistence import get_all_graph_nodes, get_nodes_by_type
            
            # Extract filters
            scope = filters.scope if filters and hasattr(filters, 'scope') else GraphScope.LOCAL
            node_type = filters.node_type if filters and hasattr(filters, 'node_type') else None
            limit = filters.limit if filters and hasattr(filters, 'limit') else 100
            
            # Parse query string for additional filters
            query_parts = query.split() if query else []
            for part in query_parts:
                if part.startswith("type:"):
                    # Override node_type from query string if provided
                    node_type = part.split(":")[1]
                elif part.startswith("scope:"):
                    # Override scope from query string if provided
                    scope = GraphScope(part.split(":")[1].lower())
            
            # Use the new persistence functions
            if node_type:
                nodes = get_nodes_by_type(
                    node_type=node_type,
                    scope=scope if isinstance(scope, GraphScope) else GraphScope.LOCAL,
                    limit=limit,
                    db_path=self.db_path
                )
            else:
                nodes = get_all_graph_nodes(
                    scope=scope if isinstance(scope, GraphScope) else GraphScope.LOCAL,
                    limit=limit,
                    db_path=self.db_path
                )
            
            # If query contains text search terms (not just filters), filter by content
            if query and not all(part.startswith(("type:", "scope:")) for part in query_parts):
                search_terms = [part.lower() for part in query_parts if not part.startswith(("type:", "scope:"))]
                filtered_nodes = []
                
                for node in nodes:
                    # Search in node ID
                    if any(term in node.id.lower() for term in search_terms):
                        filtered_nodes.append(node)
                        continue
                    
                    # Search in attributes
                    if node.attributes:
                        attrs_str = json.dumps(node.attributes, cls=DateTimeEncoder).lower()
                        if any(term in attrs_str for term in search_terms):
                            filtered_nodes.append(node)
                
                nodes = filtered_nodes
            
            # Process secrets for recall
            processed_nodes = []
            for node in nodes:
                if node.attributes:
                    processed_attrs = await self._process_secrets_for_recall(node.attributes, "search")
                    processed_node = GraphNode(
                        id=node.id,
                        type=node.type,
                        scope=node.scope,
                        attributes=processed_attrs,
                        version=node.version,
                        updated_by=node.updated_by,
                        updated_at=node.updated_at
                    )
                    processed_nodes.append(processed_node)
                else:
                    processed_nodes.append(node)
            
            return processed_nodes
            
        except Exception as e:
            logger.exception(f"Error searching graph: {e}")
            return []

    # ============================================================================
    # SERVICE PROTOCOL METHODS
    # ============================================================================

    async def start(self) -> None:
        """Start the memory service."""
        if self._time_service:
            self._start_time = self._time_service.now()
        logger.info("LocalGraphMemoryService started")

    async def stop(self) -> None:
        """Stop the memory service."""
        logger.info("LocalGraphMemoryService stopped")

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="MemoryService",
            actions=[
                "memorize",
                "recall",
                "forget",
                "memorize_metric",
                "memorize_log",
                "recall_timeseries",
                "export_identity_context",
                "search"
            ],
            version="1.0.0",
            dependencies=["SecretsService", "TimeService"],
            metadata={
                "storage_backend": "sqlite",
                "supports_graph_traversal": True
            }
        )

    def get_status(self) -> ServiceStatus:
        """Get service status."""
        # Calculate uptime
        uptime_seconds = 0.0
        if self._time_service and self._start_time:
            uptime_seconds = (self._time_service.now() - self._start_time).total_seconds()

        # Calculate memory usage
        memory_mb = 0.0
        try:
            if self._process:
                memory_info = self._process.memory_info()
                memory_mb = memory_info.rss / 1024 / 1024  # Convert bytes to MB
        except Exception as e:
            logger.debug(f"Could not get memory info: {e}")
        
        # Count graph nodes for metrics
        node_count = 0
        try:
            with get_db_connection(db_path=self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM graph_nodes")
                result = cursor.fetchone()
                node_count = result[0] if result else 0
        except Exception:
            pass
        
        return ServiceStatus(
            service_name="MemoryService",
            service_type="graph_service",
            is_healthy=True,
            uptime_seconds=uptime_seconds,
            metrics={
                "secrets_enabled": 1.0 if self.secrets_service else 0.0,
                "memory_mb": memory_mb,
                "graph_node_count": float(node_count)
            },
            last_error=None,
            last_health_check=self._time_service.now() if self._time_service else None,
            custom_metrics={}
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        try:
            # Try a simple database operation
            with get_db_connection(db_path=self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM graph_nodes")
                cursor.fetchone()
            return True
        except Exception:
            return False

    async def store_in_graph(self, node: GraphNode) -> str:
        """Store a node in the graph."""
        result = await self.memorize(node)
        return node.id if result.status == MemoryOpStatus.OK else ""

    async def query_graph(self, query: MemoryQuery) -> List[GraphNode]:
        """Query the graph."""
        return await self.recall(query)

    def get_node_type(self) -> str:
        """Get the type of nodes this service manages."""
        return "ALL"  # Memory service manages all node types
