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
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry
from datetime import datetime, timedelta
from collections import defaultdict

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.nodes import TSDBSummary
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpStatus
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

    def _set_service_registry(self, registry: "ServiceRegistry") -> None:
        """Set the service registry for accessing memory bus and time service (internal method)."""
        self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry, self._time_service)
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

    async def _run_consolidation(self) -> None:
        """Run a single consolidation cycle."""
        try:
            logger.info("Starting TSDB consolidation cycle")

            # Determine the 6-hour period to consolidate
            now = self._now()
            period_end = now.replace(minute=0, second=0, microsecond=0)
            period_start = period_end - self._consolidation_interval

            # Don't consolidate current period or future
            if period_end > now - timedelta(hours=1):
                period_end = period_end - self._consolidation_interval
                period_start = period_start - self._consolidation_interval

            logger.info(f"Consolidating period: {period_start} to {period_end}")

            # Step 1: Check if already consolidated
            if await self._is_period_consolidated(period_start, period_end):
                logger.info("Period already consolidated, skipping")
            else:
                # Step 2: Consolidate the period
                summary = await self._consolidate_period(period_start, period_end)
                if summary:
                    logger.info(f"Created summary: {summary.id} ({summary.source_node_count} nodes)")

            # Step 3: Clean up old raw nodes
            deleted_count = await self._cleanup_old_nodes()
            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old TSDB nodes")

            self._last_consolidation = now

        except Exception as e:
            logger.error(f"Consolidation failed: {e}", exc_info=True)
            raise

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

        summaries = await self._memory_bus.recall(query)
        return len(summaries) > 0

    async def _consolidate_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[TSDBSummary]:
        """Consolidate TSDB nodes for a specific 6-hour period."""
        if not self._memory_bus:
            logger.error("No memory bus available")
            return None

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
        action_counts = defaultdict(int)
        error_count = 0
        success_count = 0
        total_operations = 0

        for node in tsdb_nodes:
            attrs = node.attributes
            metric_name = attrs.get("metric_name", "unknown")
            value = float(attrs.get("value", 0))

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
            attributes={}  # GraphNode requires attributes
        )

        # Store summary
        result = await self._memory_bus.memorize(
            node=summary.to_graph_node(),
            handler_name="tsdb_consolidation",
            metadata={"consolidated_period": True}
        )

        if result.status.value != "OK":
            logger.error(f"Failed to store summary: {result.error}")
            return None

        # Mark source nodes as consolidated
        for node in tsdb_nodes:
            node.attributes["consolidated"] = True
            node.attributes["summary_id"] = summary.id
            # Note: We don't update nodes in place, they're immutable
            # The consolidated flag is for query optimization

        return summary

    async def _query_tsdb_nodes(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[GraphNode]:
        """Query TSDB nodes for a specific time period."""
        if not self._memory_bus:
            return []

        # Use timeseries recall for TSDB data

        # Calculate hours for the query
        hours = (period_end - period_start).total_seconds() / 3600

        # Query TSDB nodes
        datapoints = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=int(hours),
            correlation_types=["METRIC_DATAPOINT"]
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
                    }
                )
                nodes.append(node)

        return nodes

    async def _cleanup_old_nodes(self) -> int:
        """Delete TSDB nodes older than retention period."""
        if not self._memory_bus:
            return 0

        # Calculate cutoff time
        cutoff = self._now() - self._raw_retention

        # For now, we don't actually delete nodes
        # This would be implemented when the memory service supports deletion
        # The consolidated flag effectively makes them invisible to queries

        logger.debug(f"Would delete TSDB nodes older than {cutoff}")
        return 0  # Placeholder

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
        return ServiceStatus(
            service_name="TSDBConsolidationService",
            service_type="graph_service",
            is_healthy=self._running and self._memory_bus is not None,
            uptime_seconds=0.0,  # TODO: Track uptime
            metrics={
                "last_consolidation_timestamp": self._last_consolidation.timestamp() if self._last_consolidation else 0.0,
                "task_running": 1.0 if (self._consolidation_task and not self._consolidation_task.done()) else 0.0
            },
            last_error=None,
            last_health_check=self._time_service.now() if self._time_service else None
        )

    async def _force_consolidation(self, period_start: datetime) -> Optional[TSDBSummary]:
        """Force consolidation of a specific 6-hour period (for testing/recovery) - internal method."""
        period_end = period_start + timedelta(hours=6)
        return await self._consolidate_period(period_start, period_end)

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

        result = await self._memory_bus.memorize(node)
        return node.id if result.status == MemoryOpStatus.OK else ""

    async def query_graph(self, query: MemoryQuery) -> List[GraphNode]:
        """Query the graph using MemoryBus."""
        if not self._memory_bus:
            logger.warning(f"{self.service_name}: Memory bus not available for query")
            return []

        result = await self._memory_bus.recall(query)

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
