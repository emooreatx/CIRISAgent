"""
TSDB Consolidation Service for CIRIS Agent.

This service runs every 6 hours to consolidate TSDB telemetry nodes into
permanent summary records. It implements the agent's long-term memory system,
enabling queries like "what did I do on June 3rd, 2025?" for extended periods.

Design principles:
- Rock solid reliability - no fancy features
- 24-hour retention for raw TSDB nodes
- 6-hour summaries kept for long-term history
- No coupling to other services
"""

import asyncio
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any, cast

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry
from datetime import datetime, timedelta, timezone
from collections import defaultdict

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, GraphEdgeAttributes
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpStatus
from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.services.graph.base import BaseGraphService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

logger = logging.getLogger(__name__)

class TSDBConsolidationService(BaseGraphService):
    """
    Consolidates TSDB telemetry nodes into 6-hour summaries.

    This service:
    1. Runs every 6 hours via asyncio task
    2. Queries TSDB nodes from the last 6-hour period
    3. Creates a single summary node with aggregated metrics
    4. Deletes raw TSDB nodes older than 24 hours
    5. Never deletes summary nodes (permanent memory)
    """

    def __init__(
        self,
        memory_bus: Optional[MemoryBus] = None,
        time_service: Optional[TimeServiceProtocol] = None,
        consolidation_interval_hours: int = 6,
        raw_retention_hours: int = 24
    ) -> None:
        """
        Initialize the consolidation service.

        Args:
            memory_bus: Bus for memory operations
            consolidation_interval_hours: How often to run (default: 6)
            raw_retention_hours: How long to keep raw TSDB nodes (default: 24)
        """
        super().__init__(memory_bus=memory_bus, time_service=time_service)
        self.service_name = "TSDBConsolidationService"
        self._consolidation_interval = timedelta(hours=consolidation_interval_hours)
        self._raw_retention = timedelta(hours=raw_retention_hours)

        # Task management
        self._consolidation_task: Optional[asyncio.Task] = None
        self._running = False

        # Track last successful consolidation
        self._last_consolidation: Optional[datetime] = None
        self._start_time: Optional[datetime] = None

    def _set_service_registry(self, registry: "ServiceRegistry") -> None:
        """Set the service registry for accessing memory bus and time service (internal method)."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                # MemoryBus requires TimeServiceProtocol, ensure we have it
                if self._time_service:
                    self._memory_bus = MemoryBus(registry, self._time_service)
                else:
                    logger.error("Cannot initialize MemoryBus without TimeService")
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")

        # Get time service from registry if not provided
        if not self._time_service and registry:
            from ciris_engine.schemas.runtime.enums import ServiceType
            time_services = registry.get_services_by_type(ServiceType.TIME)
            if time_services:
                self._time_service = time_services[0]


    def _now(self) -> datetime:
        """Get current time from time service (alias for compatibility)."""
        return self._time_service.now() if self._time_service else datetime.now(timezone.utc)

    async def start(self) -> None:
        """Start the consolidation service."""
        if self._running:
            logger.warning("TSDBConsolidationService already running")
            return

        # Call parent start method
        await super().start()
        self._running = True
        self._start_time = self._now()

        # Start the consolidation loop
        self._consolidation_task = asyncio.create_task(self._consolidation_loop())
        logger.info("TSDBConsolidationService started - consolidating telemetry every 6 hours")

    async def stop(self) -> None:
        """Stop the consolidation service gracefully."""
        self._running = False

        if self._consolidation_task and not self._consolidation_task.done():
            # Run one final consolidation
            logger.info("Running final consolidation before shutdown...")
            try:
                await self._run_consolidation()
            except Exception as e:
                logger.error(f"Final consolidation failed: {e}")

            # Cancel the task
            self._consolidation_task.cancel()
            try:
                await self._consolidation_task
            except asyncio.CancelledError:
                pass

        # Call parent stop method
        await super().stop()
        logger.info("TSDBConsolidationService stopped")

    async def _consolidation_loop(self) -> None:
        """Main consolidation loop that runs every 6 hours."""
        while self._running:
            try:
                # Calculate next 6-hour boundary
                next_run = self._calculate_next_run_time()
                wait_seconds = (next_run - self._now()).total_seconds()

                if wait_seconds > 0:
                    logger.info(f"Next consolidation at {next_run} ({wait_seconds:.0f}s)")
                    await asyncio.sleep(wait_seconds)

                if self._running:  # Check again after sleep
                    await self._run_consolidation()

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consolidation loop error: {e}", exc_info=True)
                # Wait before retry
                await asyncio.sleep(300)  # 5 minutes

    def _calculate_next_run_time(self) -> datetime:
        """Calculate the next 6-hour boundary (00:00, 06:00, 12:00, 18:00)."""
        now = self._now()
        # Round up to next 6-hour mark
        hour = now.hour
        next_hour = ((hour // 6) + 1) * 6
        if next_hour >= 24:
            # Next day
            next_run = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        else:
            next_run = now.replace(hour=next_hour, minute=0, second=0, microsecond=0)
        return next_run

    async def _verify_consolidation_ready(self) -> bool:
        """Verify all dependencies are ready before consolidation."""
        if not self._memory_bus:
            logger.error("Memory bus not available")
            return False
        
        if not self._time_service:
            logger.error("Time service not available")
            return False
        
        # Test memory bus operations
        try:
            test_query = MemoryQuery(
                node_id="health_check_*",
                type=NodeType.TSDB_SUMMARY,
                scope=GraphScope.LOCAL,
                include_edges=False,
                depth=1
            )
            await self._memory_bus.recall(test_query, handler_name="tsdb_consolidation")
            logger.info("Memory bus health check passed")
            return True
        except Exception as e:
            logger.error(f"Memory bus health check failed: {e}")
            return False

    async def _run_consolidation(self) -> None:
        """Run a single consolidation cycle with enhanced error handling."""
        try:
            logger.info("Starting TSDB consolidation cycle")
            
            # Pre-flight checks
            if not await self._verify_consolidation_ready():
                logger.error("Pre-consolidation checks failed, skipping cycle")
                return
            
            # Log consolidation parameters
            logger.info(f"Consolidation parameters: interval={self._consolidation_interval}, retention={self._raw_retention}")

            # First, find the oldest unconsolidated period
            oldest_unconsolidated = await self._find_oldest_unconsolidated_period()
            
            if oldest_unconsolidated:
                # Process all periods from oldest to 24 hours ago
                now = self._now()
                cutoff_time = now - timedelta(hours=24)  # Don't consolidate data newer than 24 hours
                
                current_period_start = oldest_unconsolidated
                periods_consolidated = 0
                max_periods_per_run = 30  # Limit to prevent long-running consolidations
                
                while current_period_start < cutoff_time and periods_consolidated < max_periods_per_run:
                    period_end = current_period_start + self._consolidation_interval
                    
                    # Check if this period needs consolidation
                    if not await self._is_period_consolidated(current_period_start, period_end):
                        logger.info(f"Consolidating historical period: {current_period_start} to {period_end}")
                        
                        # Consolidate the period
                        summaries = await self._consolidate_period(current_period_start, period_end)
                        if summaries:
                            logger.info(f"Created {len(summaries)} summary nodes for period {current_period_start}")
                            periods_consolidated += 1
                        else:
                            logger.info(f"No data found for period {current_period_start} to {period_end}")
                    
                    # Move to next period
                    current_period_start = period_end
                
                if periods_consolidated > 0:
                    logger.info(f"Consolidated {periods_consolidated} historical periods")
            else:
                # No historical data found, process the most recent complete period
                now = self._now()
                period_end = now.replace(minute=0, second=0, microsecond=0)
                period_start = period_end - self._consolidation_interval

                # Don't consolidate current period or future
                if period_end > now - timedelta(hours=1):
                    period_end = period_end - self._consolidation_interval
                    period_start = period_start - self._consolidation_interval

                logger.info(f"Consolidating recent period: {period_start} to {period_end}")

                # Check if already consolidated
                if await self._is_period_consolidated(period_start, period_end):
                    logger.info("Period already consolidated, skipping")
                else:
                    # Consolidate the period
                    summaries = await self._consolidate_period(period_start, period_end)
                    if summaries:
                        logger.info(f"Created {len(summaries)} summary nodes for period")

            # Clean up old raw nodes and consolidated correlations
            deleted_nodes = await self._cleanup_old_nodes()
            if deleted_nodes > 0:
                logger.info(f"Deleted {deleted_nodes} old TSDB nodes")
            
            # Delete consolidated correlations from database
            deleted_correlations = await self._delete_consolidated_correlations()
            if deleted_correlations > 0:
                logger.info(f"Deleted {deleted_correlations} consolidated correlations from database")

            self._last_consolidation = now

        except Exception as e:
            logger.error(f"Consolidation failed: {e}", exc_info=True)
            raise

    async def _find_oldest_unconsolidated_period(self) -> Optional[datetime]:
        """Find the oldest period that has TSDB data but no consolidation."""
        if not self._memory_bus:
            return None
        
        try:
            # Get the oldest TSDB data timestamp from the database
            from ciris_engine.logic.persistence.db.core import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT MIN(updated_at) as oldest
                    FROM graph_nodes 
                    WHERE node_type = 'tsdb_data'
                """)
                row = cursor.fetchone()
                
                if not row or not row['oldest']:
                    return None
                
                # Parse the timestamp
                oldest_timestamp = datetime.fromisoformat(row['oldest'].replace('Z', '+00:00'))
                
                # Round down to the nearest 6-hour boundary
                hour = oldest_timestamp.hour
                aligned_hour = (hour // 6) * 6
                period_start = oldest_timestamp.replace(
                    hour=aligned_hour, 
                    minute=0, 
                    second=0, 
                    microsecond=0
                )
                
                # Make sure it's timezone-aware
                if period_start.tzinfo is None:
                    period_start = period_start.replace(tzinfo=timezone.utc)
                
                return period_start
                
        except Exception as e:
            logger.error(f"Failed to find oldest unconsolidated period: {e}")
            return None

    async def _is_period_consolidated(self, period_start: datetime, period_end: datetime) -> bool:
        """Check if a period has already been consolidated."""
        if not self._memory_bus:
            return False

        # Query for existing summary
        query = MemoryQuery(
            node_id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}*",
            type=NodeType.TSDB_SUMMARY,  # Query for TSDB_SUMMARY type nodes
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )

        summaries = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
        return len(summaries) > 0

    async def _consolidate_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[GraphNode]:
        """Consolidate all correlation types for a specific 6-hour period."""
        if not self._memory_bus:
            logger.error("No memory bus available")
            return []

        summaries_created: List[GraphNode] = []
        
        # 1. METRIC_DATAPOINT → TSDBSummary
        metric_summary = await self._consolidate_metrics(period_start, period_end)
        if metric_summary:
            summaries_created.append(metric_summary)
        
        # 2. SERVICE_INTERACTION → ConversationSummaryNode
        conversation_summary = await self._consolidate_conversations(period_start, period_end)
        if conversation_summary:
            summaries_created.append(conversation_summary)
        
        # 3. LOG_ENTRY → Removed (logs stay on disk, incident service handles)
        
        # 4. TRACE_SPAN → TraceSummaryNode
        trace_summary = await self._consolidate_traces(period_start, period_end)
        if trace_summary:
            summaries_created.append(trace_summary)
        
        # 5. AUDIT_ENTRY nodes → AuditSummaryNode
        # Note: This consolidates graph nodes only. The cryptographic audit trail 
        # remains intact in ciris_audit.db with its hash chain
        audit_summary = await self._consolidate_audit_nodes(period_start, period_end)
        if audit_summary:
            summaries_created.append(audit_summary)
        
        # Create edges between all summaries in this period
        if len(summaries_created) > 1:
            await self._create_period_edges(summaries_created, period_start)
            # Also create cross-type edges for richer relationships
            await self._create_cross_type_edges(summaries_created, period_start)
        
        # Create edges to previous period summaries of the same type
        for summary in summaries_created:
            await self._create_temporal_edges(summary, period_start)
        
        return summaries_created
    
    async def _consolidate_metrics(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[TSDBSummary]:
        """Consolidate METRIC_DATAPOINT correlations into TSDBSummary."""
        # Query TSDB nodes for this period
        tsdb_nodes = await self._query_tsdb_nodes(period_start, period_end)

        if not tsdb_nodes:
            logger.info(f"No TSDB nodes found for period {period_start} to {period_end}")
            return None

        logger.info(f"Found {len(tsdb_nodes)} TSDB nodes to consolidate")

        # Aggregate metrics
        metrics_by_name = defaultdict(list)
        resource_totals = {
            "tokens": 0,
            "cost": 0.0,
            "carbon": 0.0,
            "energy": 0.0
        }
        action_counts: Dict[str, int] = defaultdict(int)
        error_count = 0
        success_count = 0
        total_operations = 0

        for node in tsdb_nodes:
            attrs = node.attributes
            # Handle both dict and GraphNodeAttributes
            if isinstance(attrs, dict):
                metric_name = attrs.get("metric_name", "unknown")
                value = float(attrs.get("value", 0))
            else:
                # For GraphNodeAttributes, convert to dict first
                attrs_dict = attrs.model_dump() if hasattr(attrs, 'model_dump') else {}
                metric_name = attrs_dict.get("metric_name", "unknown")
                value = float(attrs_dict.get("value", 0))

            # Collect all values for this metric
            metrics_by_name[metric_name].append(value)

            # Extract resource usage
            if "tokens_used" in metric_name:
                resource_totals["tokens"] += int(value)
            elif "cost_cents" in metric_name:
                resource_totals["cost"] += value
            elif "carbon_grams" in metric_name:
                resource_totals["carbon"] += value
            elif "energy_kwh" in metric_name:
                resource_totals["energy"] += value

            # Count actions
            if metric_name.startswith("action.") and metric_name.endswith(".count"):
                action_type = metric_name.split(".")[1].upper()
                action_counts[action_type] += int(value)
                total_operations += int(value)

            # Count errors and successes
            if "error" in metric_name and value > 0:
                error_count += int(value)
            elif "success" in metric_name:
                success_count += int(value)
                total_operations += int(value)

        # Calculate aggregates for each metric
        metric_summaries = {}
        for name, values in metrics_by_name.items():
            if values:
                metric_summaries[name] = {
                    "count": float(len(values)),
                    "sum": float(sum(values)),
                    "min": float(min(values)),
                    "max": float(max(values)),
                    "avg": float(sum(values) / len(values))
                }

        # Calculate success rate
        if total_operations > 0:
            success_rate = (total_operations - error_count) / total_operations
        else:
            success_rate = 1.0

        # Create summary node
        summary = TSDBSummary(
            id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
            period_start=period_start,
            period_end=period_end,
            period_label=self._get_period_label(period_start),
            metrics=metric_summaries,
            total_tokens=int(resource_totals["tokens"]),
            total_cost_cents=resource_totals["cost"],
            total_carbon_grams=resource_totals["carbon"],
            total_energy_kwh=resource_totals["energy"],
            action_counts=dict(action_counts),
            error_count=error_count,
            success_rate=success_rate,
            source_node_count=len(tsdb_nodes),
            scope=GraphScope.LOCAL,
            raw_data_expired=False,  # Add the missing required field
            attributes={}  # Required by GraphNode base class
        )

        # Store summary
        if self._memory_bus:
            result = await self._memory_bus.memorize(node=summary.to_graph_node(), handler_name="tsdb_consolidation")
            if result.status != MemoryOpStatus.OK:
                logger.error(f"Failed to store summary: {result.error}")
                return None
        else:
            logger.error("Memory bus not available")
            return None

        # Mark source correlations as consolidated in the database
        await self._mark_correlations_consolidated(
            correlation_type="METRIC_DATAPOINT",
            period_start=period_start,
            period_end=period_end,
            summary_id=summary.id
        )

        return summary.to_graph_node()

    async def _query_tsdb_nodes(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[GraphNode]:
        """Query TSDB nodes for a specific time period."""
        if not self._memory_bus:
            return []

        # Use timeseries recall with specific time range
        datapoints = await self._memory_bus.recall_timeseries(
            scope="local",
            correlation_types=["METRIC_DATAPOINT"],
            start_time=period_start,
            end_time=period_end,
            handler_name="tsdb_consolidation"
        )

        # Convert TimeSeriesDataPoint to GraphNode format for processing
        nodes = []
        for dp in datapoints:
            # Check if within our exact period
            # dp.timestamp is already a datetime object, no need to parse
            if period_start <= dp.timestamp < period_end:
                # Create a pseudo-GraphNode for processing
                # Generate a unique ID based on metric name and timestamp
                node_id = f"tsdb_{dp.metric_name}_{dp.timestamp.timestamp()}"
                node = GraphNode(
                    id=node_id,
                    type=NodeType.TSDB_DATA,
                    scope=GraphScope.LOCAL,
                    attributes={
                        "metric_name": dp.metric_name,
                        "value": dp.value,
                        "timestamp": dp.timestamp.isoformat(),  # Convert datetime to string for storage
                        "tags": dp.tags or {},
                        "consolidated": False
                    },
                    updated_by="tsdb_consolidation",
                    updated_at=self._now()
                )
                nodes.append(node)

        return nodes

    async def _cleanup_old_nodes(self) -> int:
        """Delete TSDB nodes older than retention period that have been consolidated."""
        if not self._memory_bus:
            return 0

        # Calculate cutoff time (24 hours ago)
        cutoff = self._now() - self._raw_retention
        deleted_count = 0

        try:
            # Query for consolidated nodes older than retention period
            # Include both TSDB_DATA and AUDIT_ENTRY nodes
            deleted_count_total = 0
            
            for node_type in [NodeType.TSDB_DATA, NodeType.AUDIT_ENTRY]:
                # Create a query to get all nodes of this type
                # MemoryQuery requires node_id, use a wildcard
                query = MemoryQuery(
                    node_id="*",  # Match all nodes
                    type=node_type,
                    scope=GraphScope.LOCAL,
                    include_edges=False,
                    depth=1
                )
                nodes_to_delete = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
                deleted_count = 0
                
                # Filter by timestamp
                for node in nodes_to_delete:
                    # Get timestamp attribute
                    if isinstance(node.attributes, dict):
                        node_timestamp = node.attributes.get("timestamp")
                    else:
                        attrs_dict = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
                        node_timestamp = attrs_dict.get("timestamp")
                    if node_timestamp:
                        # Parse timestamp
                        if isinstance(node_timestamp, str):
                            ts = datetime.fromisoformat(node_timestamp.replace('Z', '+00:00'))
                        else:
                            ts = node_timestamp
                        
                        # Check consolidated status
                        if isinstance(node.attributes, dict):
                            is_consolidated = node.attributes.get("consolidated") == True
                        else:
                            attrs_dict = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
                            is_consolidated = attrs_dict.get("consolidated") == True
                        
                        # Delete if older than cutoff and consolidated
                        if ts < cutoff and is_consolidated:
                            # Use the forget method to delete the node
                            # forget method takes a node, not node_id
                            result = await self._memory_bus.forget(node=node, handler_name="tsdb_consolidation")
                            
                            if result.status == MemoryOpStatus.OK:
                                deleted_count += 1
                            else:
                                logger.warning(f"Failed to delete node {node.id}: {result.error}")
                
                if deleted_count > 0:
                    logger.info(f"Deleted {deleted_count} consolidated {node_type.value} nodes older than {cutoff}")
                    deleted_count_total += deleted_count
                
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
            
        return deleted_count_total

    def _get_period_label(self, period_start: datetime) -> str:
        """Generate human-readable period label."""
        hour = period_start.hour
        date_str = period_start.strftime('%Y-%m-%d')

        if hour == 0:
            return f"{date_str}-night"
        elif hour == 6:
            return f"{date_str}-morning"
        elif hour == 12:
            return f"{date_str}-afternoon"
        elif hour == 18:
            return f"{date_str}-evening"
        else:
            return f"{date_str}-{hour:02d}"

    async def is_healthy(self) -> bool:
        """Check if the service is healthy."""
        return (
            self._running and
            self._memory_bus is not None and
            (self._consolidation_task is None or not self._consolidation_task.done())
        )

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="TSDBConsolidationService",
            actions=[
                "consolidate_tsdb_nodes",
                "create_6hour_summaries",
                "cleanup_old_telemetry",
                "permanent_memory_creation"
            ],
            version="1.0.0",
            dependencies=["MemoryService", "TimeService"],
            metadata={
                "consolidation_interval_hours": self._consolidation_interval.total_seconds() / 3600,
                "raw_retention_hours": self._raw_retention.total_seconds() / 3600
            }
        )

    def get_status(self) -> ServiceStatus:
        """Get service status."""
        current_time = self._now()
        uptime_seconds = 0.0
        if self._start_time:
            uptime_seconds = (current_time - self._start_time).total_seconds()
            
        return ServiceStatus(
            service_name="TSDBConsolidationService",
            service_type="graph_service",
            is_healthy=self._running and self._memory_bus is not None,
            uptime_seconds=uptime_seconds,
            metrics={
                "last_consolidation_timestamp": self._last_consolidation.timestamp() if self._last_consolidation else 0.0,
                "task_running": 1.0 if (self._consolidation_task and not self._consolidation_task.done()) else 0.0
            },
            last_error=None,
            last_health_check=current_time,
            custom_metrics={}  # Add the required field
        )

    async def _force_consolidation(self, period_start: datetime) -> Optional[TSDBSummary]:
        """Force consolidation of a specific 6-hour period (for testing/recovery) - internal method."""
        period_end = period_start + timedelta(hours=6)
        summaries = await self._consolidate_period(period_start, period_end)
        # Find the TSDB summary in the list
        for summary in summaries:
            if summary.type == NodeType.TSDB_SUMMARY and summary.id.startswith("tsdb_summary_"):
                # Convert back to TSDBSummary
                if hasattr(TSDBSummary, 'from_graph_node'):
                    try:
                        return TSDBSummary.from_graph_node(summary)
                    except Exception:
                        pass
        return None

    async def get_summary_for_period(self, period_start: datetime) -> Optional[TSDBSummary]:
        """
        Retrieve a TSDBSummary for a specific period.

        Args:
            period_start: Start of the 6-hour period

        Returns:
            TSDBSummary if found, None otherwise
        """
        if not self._memory_bus:
            return None

        # Query for the specific summary
        query = MemoryQuery(
            node_id=f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}",
            type=NodeType.TSDB_SUMMARY,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )

        nodes = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
        if nodes and len(nodes) > 0:
            # Convert GraphNode back to TSDBSummary using from_graph_node
            node = nodes[0]
            if hasattr(TSDBSummary, 'from_graph_node'):
                try:
                    return TSDBSummary.from_graph_node(node)
                except Exception as e:
                    logger.warning(f"Failed to convert GraphNode to TSDBSummary: {e}")
            return None

        return None
    def get_node_type(self) -> str:
        """Get the type of nodes this service manages."""
        return NodeType.TSDB_SUMMARY  # TSDBSummary nodes use TSDB_SUMMARY type

    async def store_in_graph(self, node: GraphNode) -> str:
        """Store a node in the graph using MemoryBus."""
        if not self._memory_bus:
            raise RuntimeError(f"{self.service_name}: Memory bus not available")

        result = await self._memory_bus.memorize(node, handler_name="tsdb_consolidation")
        return node.id if result.status == MemoryOpStatus.OK else ""

    async def query_graph(self, query: MemoryQuery) -> List[GraphNode]:
        """Query the graph using MemoryBus."""
        if not self._memory_bus:
            logger.warning(f"{self.service_name}: Memory bus not available for query")
            return []

        result = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")

        # Handle different result types
        if hasattr(result, 'status') and hasattr(result, 'data'):
            # It's a MemoryOpResult
            if result.status == MemoryOpStatus.OK and result.data:
                if isinstance(result.data, list):
                    return result.data
                else:
                    return [result.data]
        elif isinstance(result, list):
            # Direct list of nodes
            return result

        return []
    async def _consolidate_conversations(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[GraphNode]:
        """Consolidate SERVICE_INTERACTION correlations into ConversationSummaryNode."""
        from ciris_engine.schemas.services.conversation_summary_node import ConversationSummaryNode
        
        if not self._memory_bus:
            return None
        
        # Query SERVICE_INTERACTION correlations
        correlations = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=int((period_end - period_start).total_seconds() / 3600),
            correlation_types=["service_interaction"],
            handler_name="tsdb_consolidation"
        )
        
        if not correlations:
            logger.info(f"No SERVICE_INTERACTION correlations found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(correlations)} SERVICE_INTERACTION correlations to consolidate")
        
        # Group by channel and build conversation history
        conversations_by_channel: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        unique_users = set()
        action_counts: Dict[str, int] = defaultdict(int)
        service_calls: Dict[str, int] = defaultdict(int)
        total_response_time = 0.0
        response_count = 0
        error_count = 0
        
        for corr in correlations:
            # Extract from correlation
            if hasattr(corr, 'request_data') and corr.request_data:
                channel_id = corr.request_data.channel_id or "unknown"
                
                # Build message entry
                msg_entry = {
                    "timestamp": corr.timestamp.isoformat(),
                    "action_type": corr.action_type if hasattr(corr, 'action_type') else "unknown",
                    "correlation_id": corr.correlation_id if hasattr(corr, 'correlation_id') else "unknown"
                }
                
                # Extract based on action type
                if corr.action_type in ["speak", "observe"] if hasattr(corr, 'action_type') else False:
                    if hasattr(corr.request_data, 'parameters') and corr.request_data.parameters:
                        params = corr.request_data.parameters
                        msg_entry.update({
                            "content": params.get("content", ""),
                            "author_id": params.get("author_id", "unknown"),
                            "author_name": params.get("author_name", "Unknown")
                        })
                        
                        if params.get("author_id"):
                            unique_users.add(params["author_id"])
                
                conversations_by_channel[channel_id].append(msg_entry)
                action_counts[corr.action_type if hasattr(corr, 'action_type') else 'unknown'] += 1
                
                # Track service calls
                service_calls[corr.service_type if hasattr(corr, 'service_type') else 'unknown'] += 1
                
                # Track response times
                if hasattr(corr, 'response_data') and corr.response_data:
                    if hasattr(corr.response_data, 'execution_time_ms'):
                        total_response_time += corr.response_data.execution_time_ms
                        response_count += 1
                    
                    if not corr.response_data.success:
                        error_count += 1
        
        # Calculate metrics
        total_messages = sum(len(msgs) for msgs in conversations_by_channel.values())
        messages_by_channel = {ch: len(msgs) for ch, msgs in conversations_by_channel.items()}
        avg_response_time = total_response_time / response_count if response_count > 0 else 0.0
        success_rate = 1.0 - (error_count / len(correlations)) if len(correlations) > 0 else 1.0
        
        # Sort conversations by timestamp
        for channel_id in conversations_by_channel:
            conversations_by_channel[channel_id].sort(key=lambda x: x["timestamp"])
        
        # Create summary node
        summary = ConversationSummaryNode(
            id=f"conversation_summary_{period_start.strftime('%Y%m%d_%H')}",
            period_start=period_start,
            period_end=period_end,
            period_label=self._get_period_label(period_start),
            conversations_by_channel=dict(conversations_by_channel),
            total_messages=total_messages,
            messages_by_channel=messages_by_channel,
            unique_users=len(unique_users),
            user_list=list(unique_users),
            action_counts=dict(action_counts),
            service_calls=dict(service_calls),
            avg_response_time_ms=avg_response_time,
            total_processing_time_ms=total_response_time,
            error_count=error_count,
            success_rate=success_rate,
            source_correlation_count=len(correlations),
            scope=GraphScope.LOCAL,
            sentiment_summary=None,  # Add the required field
            attributes={}  # Required by GraphNode base class
        )
        
        # Store summary
        result = await self._memory_bus.memorize(node=summary.to_graph_node(), handler_name="tsdb_consolidation")
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store conversation summary: {result.error}")
            return None
        
        # Mark source correlations as consolidated
        await self._mark_correlations_consolidated(
            correlation_type="SERVICE_INTERACTION",
            period_start=period_start,
            period_end=period_end,
            summary_id=summary.id
        )
        
        return summary.to_graph_node()
    
    
    async def _consolidate_traces(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[GraphNode]:
        """Consolidate TRACE_SPAN correlations into TraceSummaryNode.
        
        Elegantly consolidates traces into task summaries showing:
        - Tasks processed with their final status
        - Handlers selected by each thought
        - Key performance metrics
        """
        from ciris_engine.schemas.services.trace_summary_node import TraceSummaryNode
        from collections import defaultdict
        
        if not self._memory_bus:
            return None
        
        # Query TRACE_SPAN correlations
        correlations = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=int((period_end - period_start).total_seconds() / 3600),
            correlation_types=["trace_span"],
            handler_name="tsdb_consolidation"
        )
        
        if not correlations:
            logger.info(f"No TRACE_SPAN correlations found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(correlations)} TRACE_SPAN correlations to consolidate")
        
        # Initialize metrics with focus on task summaries
        task_summaries = {}  # task_id -> {status, thoughts: [{id, handler}], duration}
        unique_tasks = set()
        unique_thoughts = set()
        tasks_by_status: Dict[str, int] = defaultdict(int)
        thoughts_by_type: Dict[str, int] = defaultdict(int)
        component_calls: Dict[str, int] = defaultdict(int)
        component_failures: Dict[str, int] = defaultdict(int)
        component_latencies: Dict[str, List[float]] = defaultdict(list)
        handler_actions: Dict[str, int] = defaultdict(int)
        errors_by_component: Dict[str, int] = defaultdict(int)
        task_processing_times = []
        total_errors = 0
        guardrail_violations: Dict[str, int] = defaultdict(int)
        dma_decisions: Dict[str, int] = defaultdict(int)
        
        # Build task summaries showing handler selections
        for corr in correlations:
            if hasattr(corr, 'tags') and corr.tags:
                task_id = corr.tags.get('task_id')
                thought_id = corr.tags.get('thought_id')
                component_type = corr.tags.get('component_type', 'unknown')
                
                # Initialize task summary if needed
                if task_id and task_id not in task_summaries:
                    task_summaries[task_id] = {
                        'status': 'processing',
                        'thoughts': [],
                        'start_time': corr.timestamp,
                        'end_time': corr.timestamp,
                        'handlers_selected': []
                    }
                    unique_tasks.add(task_id)
                
                # Track thoughts and their handler selections
                if thought_id:
                    unique_thoughts.add(thought_id)
                    if task_id and component_type == 'handler':
                        # Track handler selection for this thought
                        action_type = corr.tags.get('action_type', 'unknown')
                        thoughts_list = task_summaries[task_id].get('thoughts', [])
                        if isinstance(thoughts_list, list):
                            thoughts_list.append({
                                'thought_id': thought_id,
                                'handler': action_type,
                                'timestamp': corr.timestamp
                            })
                            task_summaries[task_id]['thoughts'] = thoughts_list
                        handlers_list = task_summaries[task_id].get('handlers_selected', [])
                        if isinstance(handlers_list, list):
                            handlers_list.append(action_type)
                            task_summaries[task_id]['handlers_selected'] = handlers_list
                        handler_actions[action_type] += 1
                
                # Track task completion
                if task_id and corr.tags.get('task_status'):
                    task_summaries[task_id]['status'] = corr.tags['task_status']
                    task_summaries[task_id]['end_time'] = corr.timestamp
                    tasks_by_status[corr.tags['task_status']] += 1
                
                # Component tracking
                component_calls[component_type] += 1
                
                # Extract metrics from response data
                if hasattr(corr, 'response_data') and corr.response_data:
                    if not corr.response_data.success:
                        component_failures[component_type] += 1
                        errors_by_component[component_type] += 1
                        total_errors += 1
                    
                    if hasattr(corr.response_data, 'execution_time_ms'):
                        component_latencies[component_type].append(corr.response_data.execution_time_ms)
                
                # Track thought type
                if thought_id and corr.tags.get('thought_type'):
                    thoughts_by_type[corr.tags['thought_type']] += 1
                
                # Track guardrail violations
                if component_type == 'guardrail':
                    guardrail_type = corr.tags.get('guardrail_type', 'unknown')
                    if corr.tags.get('violation') == 'true':
                        guardrail_violations[guardrail_type] += 1
                
                # Track DMA decisions
                if component_type == 'dma':
                    dma_type = corr.tags.get('dma_type', 'unknown')
                    dma_decisions[dma_type] += 1
        
        # Calculate latency percentiles
        component_latency_stats = {}
        for component, latencies in component_latencies.items():
            if latencies:
                sorted_latencies = sorted(latencies)
                component_latency_stats[component] = {
                    'avg': sum(latencies) / len(latencies),
                    'p95': sorted_latencies[int(len(sorted_latencies) * 0.95)],
                    'p99': sorted_latencies[int(len(sorted_latencies) * 0.99)]
                }
        
        # Calculate task processing times from summaries
        for task_id, summary in task_summaries.items():
            if summary['start_time'] and summary['end_time']:
                # Ensure times are datetime objects
                start_time = summary.get('start_time')
                end_time = summary.get('end_time')
                if start_time and end_time and isinstance(start_time, datetime) and isinstance(end_time, datetime):
                    duration_ms = (end_time - start_time).total_seconds() * 1000
                else:
                    duration_ms = 0.0
                task_processing_times.append(duration_ms)
        
        # Calculate task processing percentiles
        avg_task_time = 0.0
        p95_task_time = 0.0
        p99_task_time = 0.0
        if task_processing_times:
            sorted_times = sorted(task_processing_times)
            avg_task_time = sum(task_processing_times) / len(task_processing_times)
            p95_task_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_task_time = sorted_times[int(len(sorted_times) * 0.99)]
        
        # Calculate trace depth metrics
        trace_depths = []
        for s in task_summaries.values():
            thoughts = s.get('thoughts', [])
            if isinstance(thoughts, list):
                trace_depths.append(len(thoughts))
        
        max_trace_depth = max(trace_depths) if trace_depths else 0
        avg_trace_depth = sum(trace_depths) / len(trace_depths) if trace_depths else 0.0
        
        # Calculate error rate
        total_calls = sum(component_calls.values())
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0
        
        # Calculate avg thoughts per task
        avg_thoughts_per_task = len(unique_thoughts) / len(unique_tasks) if unique_tasks else 0.0
        
        # Create summary node with elegant task summaries
        summary_node = TraceSummaryNode(
            id=f"trace_summary_{period_start.strftime('%Y%m%d_%H')}",
            period_start=period_start,
            period_end=period_end,
            period_label=self._get_period_label(period_start),
            total_tasks_processed=len(unique_tasks),
            tasks_by_status=dict(tasks_by_status),
            unique_task_ids=unique_tasks,
            task_summaries=task_summaries,  # Include elegant task summaries
            total_thoughts_processed=len(unique_thoughts),
            thoughts_by_type=dict(thoughts_by_type),
            avg_thoughts_per_task=avg_thoughts_per_task,
            component_calls=dict(component_calls),
            component_failures=dict(component_failures),
            component_latency_ms=component_latency_stats,
            dma_decisions=dict(dma_decisions),
            guardrail_violations=dict(guardrail_violations),
            handler_actions=dict(handler_actions),
            avg_task_processing_time_ms=avg_task_time,
            p95_task_processing_time_ms=p95_task_time,
            p99_task_processing_time_ms=p99_task_time,
            total_processing_time_ms=sum(task_processing_times) if task_processing_times else 0.0,
            total_errors=total_errors,
            errors_by_component=dict(errors_by_component),
            error_rate=error_rate,
            max_trace_depth=max_trace_depth,
            avg_trace_depth=avg_trace_depth,
            source_correlation_count=len(correlations),
            scope=GraphScope.LOCAL,
            attributes={}  # Required by GraphNode base class
        )
        
        # Store summary
        result = await self._memory_bus.memorize(node=summary_node.to_graph_node(), handler_name="tsdb_consolidation")
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store trace summary: {result.error}")
            return None
        
        # Mark source correlations as consolidated
        await self._mark_correlations_consolidated(
            correlation_type="TRACE_SPAN",
            period_start=period_start,
            period_end=period_end,
            summary_id=summary_node.id
        )
        
        return summary_node.to_graph_node()
    
    async def _consolidate_audit_nodes(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[GraphNode]:
        """Consolidate AUDIT_ENTRY graph nodes into AuditSummaryNode with hash.
        
        Note: This only consolidates the graph representation. The full audit trail
        with cryptographic hash chain remains intact in ciris_audit.db.
        """
        from ciris_engine.schemas.services.audit_summary_node import AuditSummaryNode
        from collections import defaultdict
        
        if not self._memory_bus:
            return None
        
        # Query AUDIT_ENTRY nodes for this period
        # Import is already at the top of the file
        
        # Use query to get audit nodes
        audit_query = MemoryQuery(
            node_id="audit_*",  # Match all audit nodes
            type=NodeType.AUDIT_ENTRY,
            scope=GraphScope.LOCAL,
            include_edges=False,
            depth=1
        )
        
        # Get all audit nodes and filter by time period
        all_audit_nodes = await self._memory_bus.recall(audit_query, handler_name="tsdb_consolidation")
        
        # Filter by time period
        audit_nodes = []
        for node in all_audit_nodes:
            if isinstance(node.attributes, dict):
                timestamp_str = node.attributes.get('timestamp', node.attributes.get('created_at', ''))
            else:
                attrs_dict = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
                timestamp_str = attrs_dict.get('timestamp', attrs_dict.get('created_at', ''))
            
            if timestamp_str:
                try:
                    timestamp = datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
                    if period_start <= timestamp < period_end:
                        audit_nodes.append(node)
                except Exception:
                    pass
        
        if not audit_nodes:
            logger.info(f"No AUDIT_ENTRY nodes found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(audit_nodes)} AUDIT_ENTRY nodes to consolidate")
        
        # Collect metrics and event IDs for hashing
        event_ids = []
        events_by_type: Dict[str, int] = defaultdict(int)
        events_by_actor: Dict[str, int] = defaultdict(int)
        events_by_service: Dict[str, int] = defaultdict(int)
        failed_auth_attempts = 0
        permission_denials = 0
        emergency_shutdowns = 0
        config_changes = 0
        first_event_id = None
        last_event_id = None
        
        # Sort by timestamp to ensure chronological order
        # Sort nodes by timestamp
        def get_timestamp_str(node: GraphNode) -> str:
            if isinstance(node.attributes, dict):
                timestamp = node.attributes.get('timestamp', node.attributes.get('created_at', ''))
                return str(timestamp) if timestamp else ''
            else:
                attrs_dict = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
                timestamp = attrs_dict.get('timestamp', attrs_dict.get('created_at', ''))
                return str(timestamp) if timestamp else ''
        
        sorted_nodes = sorted(audit_nodes, key=get_timestamp_str)
        
        for i, node in enumerate(sorted_nodes):
            # Extract event ID (node id format is "audit_<event_id>")
            event_id = node.id.replace('audit_', '') if node.id.startswith('audit_') else node.id
            event_ids.append(event_id)
            
            if i == 0:
                first_event_id = event_id
            if i == len(sorted_nodes) - 1:
                last_event_id = event_id
            
            # Extract metrics from node attributes
            if isinstance(node.attributes, dict):
                attrs = node.attributes
            else:
                attrs = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
            
            action = attrs.get('action', 'unknown')
            actor = attrs.get('actor', 'unknown')
            
            # Get context data
            context = attrs.get('context', {})
            if isinstance(context, dict):
                service_name = context.get('service_name', 'unknown')
                event_type = context.get('additional_data', {}).get('event_type', action)
                severity = context.get('additional_data', {}).get('severity', 'info')
                outcome = context.get('additional_data', {}).get('outcome', 'success')
            else:
                service_name = 'unknown'
                event_type = action
                severity = 'info'
                outcome = 'success'
            
            events_by_type[event_type] += 1
            events_by_actor[actor] += 1
            events_by_service[service_name] += 1
            
            # Track security events based on action/event_type
            if 'AUTH_FAILURE' in event_type.upper() or outcome == 'failure' and 'auth' in event_type.lower():
                failed_auth_attempts += 1
            elif 'PERMISSION_DENIED' in event_type.upper() or 'permission' in event_type.lower() and outcome == 'failure':
                permission_denials += 1
            elif 'EMERGENCY_SHUTDOWN' in event_type.upper():
                emergency_shutdowns += 1
            elif any(cfg in event_type.upper() for cfg in ['CONFIG_CREATE', 'CONFIG_UPDATE', 'CONFIG_DELETE']):
                config_changes += 1
        
        # Compute audit hash
        audit_hash = AuditSummaryNode.compute_audit_hash(event_ids)
        
        # Create summary node
        summary = AuditSummaryNode(
            id=f"audit_summary_{period_start.strftime('%Y%m%d_%H')}",
            period_start=period_start,
            period_end=period_end,
            period_label=self._get_period_label(period_start),
            audit_hash=audit_hash,
            hash_algorithm="sha256",
            total_audit_events=len(audit_nodes),
            events_by_type=dict(events_by_type),
            events_by_actor=dict(events_by_actor),
            events_by_service=dict(events_by_service),
            failed_auth_attempts=failed_auth_attempts,
            permission_denials=permission_denials,
            emergency_shutdowns=emergency_shutdowns,
            config_changes=config_changes,
            first_event_id=first_event_id,
            last_event_id=last_event_id,
            source_correlation_count=len(audit_nodes),
            scope=GraphScope.LOCAL
        )
        
        # Store summary
        result = await self._memory_bus.memorize(node=summary.to_graph_node(), handler_name="tsdb_consolidation")
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store audit summary: {result.error}")
            return None
        
        # Mark source audit nodes for deletion
        # Since these are graph nodes, we need to mark them differently
        await self._mark_audit_nodes_consolidated(audit_nodes, summary.id)
        
        return summary.to_graph_node()
    
    async def _create_period_edges(self, summaries: List[GraphNode], period_start: datetime) -> None:
        """Create edges between all summaries in the same period."""
        if not self._memory_bus or len(summaries) < 2:
            return
        
        try:
            from ciris_engine.schemas.services.graph_core import GraphEdge
            
            # Create edges between each pair of summaries in this period
            for i in range(len(summaries)):
                for j in range(i + 1, len(summaries)):
                    edge = GraphEdge(
                        source=summaries[i].id,
                        target=summaries[j].id,
                        relationship="TEMPORAL_CORRELATION",
                        scope=GraphScope.LOCAL,
                        attributes=GraphEdgeAttributes(
                            context=f"Same period correlation for {period_start.isoformat()}"
                        )
                    )
                    
                    # Store edge using memory bus
                    result = await self._memory_bus.memorize(
                        node=GraphNode(
                            id=f"edge_{summaries[i].id}_{summaries[j].id}",
                            type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                            scope=GraphScope.LOCAL,
                            attributes={
                                "edge_data": edge.model_dump()
                            },
                            updated_by="tsdb_consolidation",
                            updated_at=self._now()
                        ),
                        handler_name="tsdb_consolidation"
                    )
                    
                    if result.status == MemoryOpStatus.OK:
                        logger.debug(f"Created edge between {summaries[i].type} and {summaries[j].type} for period {period_start}")
                    
        except Exception as e:
            logger.error(f"Failed to create period edges: {e}")
    
    async def _create_temporal_edges(self, summary: GraphNode, period_start: datetime) -> None:
        """Create edges between summaries of the same type across consecutive periods."""
        if not self._memory_bus:
            return
        
        try:
            from ciris_engine.schemas.services.graph_core import GraphEdge
            
            # Find the previous period summary of the same type
            prev_period_start = period_start - self._consolidation_interval
            prev_period_id_pattern = f"{summary.type.lower()}_{prev_period_start.strftime('%Y%m%d_%H')}*"
            
            # Query for previous period summaries
            query = MemoryQuery(
                node_id=prev_period_id_pattern,
                type=summary.type,
                scope=GraphScope.LOCAL,
                include_edges=False,
                depth=1
            )
            
            prev_summaries = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
            
            if prev_summaries:
                # Create edge from previous to current
                prev_summary = prev_summaries[0]
                edge = GraphEdge(
                    source=prev_summary.id,
                    target=summary.id,
                    relationship="TEMPORAL_SEQUENCE",
                    scope=GraphScope.LOCAL,
                    attributes=GraphEdgeAttributes(
                        context=f"Consecutive periods: {prev_period_start.isoformat()} to {period_start.isoformat()} for {summary.type.value}"
                    )
                )
                
                # Store edge
                result = await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_temporal_{prev_summary.id}_{summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={
                            "edge_data": edge.model_dump()
                        },
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                    handler_name="tsdb_consolidation"
                )
                
                if result.status == MemoryOpStatus.OK:
                    logger.debug(f"Created temporal edge for {summary.type} from {prev_period_start} to {period_start}")
                    
        except Exception as e:
            logger.error(f"Failed to create temporal edge for {summary.type}: {e}")
    
    async def _create_cross_type_edges(self, summaries: List[GraphNode], period_start: datetime) -> None:
        """
        Create cross-type temporal edges to enable powerful queries like:
        - "Show me how trace errors correlate with conversation volume"
        - "What conversations led to high resource usage?"
        - "How do guardrail violations affect user experience?"
        
        This creates edges between different summary types that have meaningful relationships.
        """
        if not self._memory_bus or len(summaries) < 2:
            return
        
        try:
            from ciris_engine.schemas.services.graph_core import GraphEdge
            
            # Find each type of summary
            tsdb_summary = None
            conversation_summary = None
            trace_summary = None
            audit_summary = None
            
            for summary in summaries:
                # All summaries may use NodeType.TSDB_SUMMARY, check by ID prefix
                if summary.id.startswith("tsdb_summary_"):
                    tsdb_summary = summary
                elif summary.id.startswith("conversation_summary_"):
                    conversation_summary = summary
                elif summary.id.startswith("trace_summary_"):
                    trace_summary = summary
                elif summary.id.startswith("audit_summary_"):
                    audit_summary = summary
            
            # Create meaningful cross-type relationships
            
            # 1. Link conversations to traces (conversations drive tasks)
            if conversation_summary and trace_summary:
                edge = GraphEdge(
                    source=conversation_summary.id,
                    target=trace_summary.id,
                    relationship="TEMPORAL_CORRELATION",
                    scope=GraphScope.LOCAL,
                    weight=1.0,
                    attributes=GraphEdgeAttributes(
                        context="User interactions in conversations trigger task processing"
                    )
                )
                
                await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_cross_{conversation_summary.id}_to_{trace_summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={"edge_data": edge.model_dump()},
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                    handler_name="tsdb_consolidation"
                )
            
            # 2. Link traces to metrics (task processing drives resource usage)
            if trace_summary and tsdb_summary:
                edge = GraphEdge(
                    source=trace_summary.id,
                    target=tsdb_summary.id,
                    relationship="TEMPORAL_CORRELATION",
                    scope=GraphScope.LOCAL,
                    weight=1.0,
                    attributes=GraphEdgeAttributes(
                        context="Task processing patterns directly impact resource consumption"
                    )
                )
                
                await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_cross_{trace_summary.id}_to_{tsdb_summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={"edge_data": edge.model_dump()},
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                    handler_name="tsdb_consolidation"
                )
            
            # 3. Link metrics back to conversations (resource usage affects user experience)
            if tsdb_summary and conversation_summary:
                edge = GraphEdge(
                    source=tsdb_summary.id,
                    target=conversation_summary.id,
                    relationship="TEMPORAL_CORRELATION",
                    scope=GraphScope.LOCAL,
                    weight=1.0,
                    attributes=GraphEdgeAttributes(
                        context="High resource usage or errors may impact response quality"
                    )
                )
                
                await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_cross_{tsdb_summary.id}_to_{conversation_summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={"edge_data": edge.model_dump()},
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                    handler_name="tsdb_consolidation"
                )
                
            # 4. Link audit to traces (security events during task processing)
            if audit_summary and trace_summary:
                edge = GraphEdge(
                    source=audit_summary.id,
                    target=trace_summary.id,
                    relationship="TEMPORAL_CORRELATION",
                    scope=GraphScope.LOCAL,
                    weight=1.0,
                    attributes=GraphEdgeAttributes(
                        context="Security events and permissions affect task execution"
                    )
                )
                
                await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_cross_{audit_summary.id}_to_{trace_summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={"edge_data": edge.model_dump()},
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                    handler_name="tsdb_consolidation"
                )
            
            # 5. Link traces to audit (task processing generates audit events)
            if trace_summary and audit_summary:
                edge = GraphEdge(
                    source=trace_summary.id,
                    target=audit_summary.id,
                    relationship="TEMPORAL_CORRELATION",
                    scope=GraphScope.LOCAL,
                    weight=1.0,
                    attributes=GraphEdgeAttributes(
                        context="Task execution creates audit trail for compliance"
                    )
                )
                
                await self._memory_bus.memorize(
                    node=GraphNode(
                        id=f"edge_cross_{trace_summary.id}_to_{audit_summary.id}",
                        type=NodeType.TSDB_SUMMARY,  # NodeType doesn't have EDGE
                        scope=GraphScope.LOCAL,
                        attributes={"edge_data": edge.model_dump()},
                        updated_by="tsdb_consolidation",
                        updated_at=self._now()
                    ),
                )
            
            logger.info(f"Created cross-type temporal edges for period {period_start}")
                
        except Exception as e:
            logger.error(f"Failed to create cross-type edges: {e}")
    
    async def _mark_correlations_consolidated(
        self,
        correlation_type: str,
        period_start: datetime,
        period_end: datetime,
        summary_id: str
    ) -> None:
        """Mark correlations as consolidated in the database."""
        try:
            # Direct database update to mark correlations as consolidated
            # This is a performance optimization to avoid loading all correlations into memory
            import sqlite3
            from pathlib import Path
            
            db_path = Path("data/ciris_engine.db")
            if db_path.exists():
                conn = sqlite3.connect(str(db_path))
                cursor = conn.cursor()
                
                # Update correlations to mark them as consolidated
                cursor.execute("""
                    UPDATE service_correlations
                    SET 
                        tags = json_set(
                            COALESCE(tags, '{}'),
                            '$.consolidated', true,
                            '$.summary_id', ?
                        )
                    WHERE 
                        correlation_type = ? AND
                        timestamp >= ? AND
                        timestamp < ?
                """, (summary_id, correlation_type, period_start.isoformat(), period_end.isoformat()))
                
                affected_rows = cursor.rowcount
                conn.commit()
                conn.close()
                
                if affected_rows > 0:
                    logger.info(f"Marked {affected_rows} {correlation_type} correlations as consolidated for period {period_start}")
                    
        except Exception as e:
            logger.error(f"Failed to mark correlations as consolidated: {e}")
    
    async def _delete_consolidated_correlations(self) -> int:
        """Delete correlations that have been consolidated and are older than retention period."""
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path("data/ciris_engine.db")
            if not db_path.exists():
                return 0
                
            conn = sqlite3.connect(str(db_path))
            cursor = conn.cursor()
            
            # Calculate cutoff time
            cutoff = (self._now() - self._raw_retention).isoformat()
            
            # Delete consolidated correlations older than retention period
            cursor.execute("""
                DELETE FROM service_correlations
                WHERE 
                    json_extract(tags, '$.consolidated') = true AND
                    timestamp < ? AND
                    correlation_type IN ('METRIC_DATAPOINT', 'SERVICE_INTERACTION', 'TRACE_SPAN')
            """, (cutoff,))
            
            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()
            
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} consolidated correlations older than {cutoff}")
                
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete consolidated correlations: {e}")
            return 0
    
    async def _mark_audit_nodes_consolidated(self, audit_nodes: List[GraphNode], summary_id: str) -> None:
        """Mark audit nodes as consolidated so they can be deleted.
        
        Since graph nodes are immutable, we'll track consolidated nodes
        for deletion during cleanup.
        """
        if not self._memory_bus:
            return
            
        try:
            # For each audit node, we'll update it with a consolidated flag
            # This requires re-storing the node with updated attributes
            for node in audit_nodes:
                # Add consolidated metadata
                # Need to update attributes properly based on type
                if isinstance(node.attributes, dict):
                    node.attributes["consolidated"] = True
                    node.attributes["summary_id"] = summary_id
                    node.attributes["consolidation_timestamp"] = self._now().isoformat()
                else:
                    # For GraphNodeAttributes, we need to create a new dict
                    attrs_dict = node.attributes.model_dump() if hasattr(node.attributes, 'model_dump') else {}
                    attrs_dict["consolidated"] = True
                    attrs_dict["summary_id"] = summary_id
                    attrs_dict["consolidation_timestamp"] = self._now().isoformat()
                    node.attributes = attrs_dict
                
                # Re-store the node with updated attributes
                # Note: This creates a new version, the old one should be cleaned up
                result = await self._memory_bus.memorize(node=node)
                
                if result.status != MemoryOpStatus.OK:
                    logger.warning(f"Failed to mark audit node {node.id} as consolidated: {result.error}")
            
            logger.info(f"Marked {len(audit_nodes)} audit nodes as consolidated")
            
        except Exception as e:
            logger.error(f"Failed to mark audit nodes as consolidated: {e}")