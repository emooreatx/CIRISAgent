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
from typing import List, Optional, TYPE_CHECKING, Dict, Any

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry
from datetime import datetime, timedelta, timezone
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
                summaries = await self._consolidate_period(period_start, period_end)
                if summaries:
                    logger.info(f"Created {len(summaries)} summary nodes for period")

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
    ) -> List[GraphNode]:
        """Consolidate all correlation types for a specific 6-hour period."""
        if not self._memory_bus:
            logger.error("No memory bus available")
            return []

        summaries_created = []
        
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
        
        # 5. AUDIT_EVENT → AuditSummaryNode
        audit_summary = await self._consolidate_audits(period_start, period_end)
        if audit_summary:
            summaries_created.append(audit_summary)
        
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

        if result.status != MemoryOpStatus.OK:
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
    async def _consolidate_conversations(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[GraphNode]:
        """Consolidate SERVICE_INTERACTION correlations into ConversationSummaryNode."""
        from ciris_engine.schemas.services.conversation_summary_node import ConversationSummaryNode
        from ciris_engine.logic.persistence import get_correlations_by_channel
        
        if not self._memory_bus:
            return None
        
        # Query SERVICE_INTERACTION correlations
        correlations = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=int((period_end - period_start).total_seconds() / 3600),
            correlation_types=["service_interaction"]
        )
        
        if not correlations:
            logger.info(f"No SERVICE_INTERACTION correlations found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(correlations)} SERVICE_INTERACTION correlations to consolidate")
        
        # Group by channel and build conversation history
        conversations_by_channel: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
        unique_users = set()
        action_counts = defaultdict(int)
        service_calls = defaultdict(int)
        total_response_time = 0.0
        response_count = 0
        error_count = 0
        
        for corr in correlations:
            # Extract from correlation
            if hasattr(corr, 'request_data') and corr.request_data:
                channel_id = corr.request_data.channel_id or "unknown"
                
                # Build message entry
                msg_entry = {
                    "timestamp": corr.timestamp.isoformat() if corr.timestamp else corr.created_at.isoformat(),
                    "action_type": corr.action_type,
                    "correlation_id": corr.correlation_id
                }
                
                # Extract based on action type
                if corr.action_type in ["speak", "observe"]:
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
                action_counts[corr.action_type] += 1
                
                # Track service calls
                service_calls[corr.service_type] += 1
                
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
            scope=GraphScope.LOCAL
        )
        
        # Store summary
        result = await self._memory_bus.memorize(
            node=summary.to_graph_node(),
            handler_name="tsdb_consolidation",
            metadata={"consolidated_conversation": True}
        )
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store conversation summary: {result.error}")
            return None
        
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
            correlation_types=["trace_span"]
        )
        
        if not correlations:
            logger.info(f"No TRACE_SPAN correlations found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(correlations)} TRACE_SPAN correlations to consolidate")
        
        # Initialize metrics with focus on task summaries
        task_summaries = {}  # task_id -> {status, thoughts: [{id, handler}], duration}
        unique_tasks = set()
        unique_thoughts = set()
        tasks_by_status = defaultdict(int)
        thoughts_by_type = defaultdict(int)
        component_calls = defaultdict(int)
        component_failures = defaultdict(int)
        component_latencies = defaultdict(list)
        handler_actions = defaultdict(int)
        errors_by_component = defaultdict(int)
        task_processing_times = []
        total_errors = 0
        guardrail_violations = defaultdict(int)
        dma_decisions = defaultdict(int)
        
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
                        task_summaries[task_id]['thoughts'].append({
                            'thought_id': thought_id,
                            'handler': action_type,
                            'timestamp': corr.timestamp
                        })
                        task_summaries[task_id]['handlers_selected'].append(action_type)
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
                duration_ms = (summary['end_time'] - summary['start_time']).total_seconds() * 1000
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
        
        # Calculate trace depth metrics (simplified)
        max_trace_depth = max(len(s['thoughts']) for s in task_summaries.values()) if task_summaries else 0
        avg_trace_depth = sum(len(s['thoughts']) for s in task_summaries.values()) / len(task_summaries) if task_summaries else 0.0
        
        # Calculate error rate
        total_calls = sum(component_calls.values())
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0
        
        # Calculate avg thoughts per task
        avg_thoughts_per_task = len(unique_thoughts) / len(unique_tasks) if unique_tasks else 0.0
        
        # Create summary node with elegant task summaries
        summary = TraceSummaryNode(
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
            scope=GraphScope.LOCAL
        )
        
        # Store summary
        result = await self._memory_bus.memorize(
            node=summary.to_graph_node(),
            handler_name="tsdb_consolidation",
            metadata={"consolidated_trace": True}
        )
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store trace summary: {result.error}")
            return None
        
        return summary.to_graph_node()
    
    async def _consolidate_audits(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Optional[GraphNode]:
        """Consolidate AUDIT_EVENT correlations into AuditSummaryNode with hash."""
        from ciris_engine.schemas.services.audit_summary_node import AuditSummaryNode
        from collections import defaultdict
        
        if not self._memory_bus:
            return None
        
        # Query AUDIT_EVENT correlations
        correlations = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=int((period_end - period_start).total_seconds() / 3600),
            correlation_types=["audit_event"]
        )
        
        if not correlations:
            logger.info(f"No AUDIT_EVENT correlations found for period {period_start} to {period_end}")
            return None
        
        logger.info(f"Found {len(correlations)} AUDIT_EVENT correlations to consolidate")
        
        # Collect metrics and event IDs for hashing
        event_ids = []
        events_by_type = defaultdict(int)
        events_by_actor = defaultdict(int)
        events_by_service = defaultdict(int)
        failed_auth_attempts = 0
        permission_denials = 0
        emergency_shutdowns = 0
        config_changes = 0
        first_event_id = None
        last_event_id = None
        
        # Sort by timestamp to ensure chronological order
        sorted_correlations = sorted(correlations, key=lambda c: c.timestamp if hasattr(c, 'timestamp') else c.created_at)
        
        for i, corr in enumerate(sorted_correlations):
            # Extract event ID
            event_id = corr.correlation_id
            event_ids.append(event_id)
            
            if i == 0:
                first_event_id = event_id
            if i == len(sorted_correlations) - 1:
                last_event_id = event_id
            
            # Extract metrics from tags
            if hasattr(corr, 'tags') and corr.tags:
                event_type = corr.tags.get('event_type', 'unknown')
                actor = corr.tags.get('actor', 'unknown')
                service = corr.tags.get('service', 'unknown')
                
                events_by_type[event_type] += 1
                events_by_actor[actor] += 1
                events_by_service[service] += 1
                
                # Track security events
                if event_type == 'AUTH_FAILURE':
                    failed_auth_attempts += 1
                elif event_type == 'PERMISSION_DENIED':
                    permission_denials += 1
                elif event_type == 'EMERGENCY_SHUTDOWN':
                    emergency_shutdowns += 1
                elif event_type in ['CONFIG_CREATE', 'CONFIG_UPDATE', 'CONFIG_DELETE']:
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
            total_audit_events=len(correlations),
            events_by_type=dict(events_by_type),
            events_by_actor=dict(events_by_actor),
            events_by_service=dict(events_by_service),
            failed_auth_attempts=failed_auth_attempts,
            permission_denials=permission_denials,
            emergency_shutdowns=emergency_shutdowns,
            config_changes=config_changes,
            first_event_id=first_event_id,
            last_event_id=last_event_id,
            source_correlation_count=len(correlations),
            scope=GraphScope.LOCAL
        )
        
        # Store summary
        result = await self._memory_bus.memorize(
            node=summary.to_graph_node(),
            handler_name="tsdb_consolidation",
            metadata={"consolidated_audit": True}
        )
        
        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store audit summary: {result.error}")
            return None
        
        return summary.to_graph_node()