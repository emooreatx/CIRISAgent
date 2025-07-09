"""
TSDB Consolidation Service - Main service class.

This service runs every 6 hours to consolidate telemetry and memory data
into permanent summary records with proper edge connections.
"""

import asyncio
import logging
from typing import List, Optional, TYPE_CHECKING, Dict, Any
from datetime import datetime, timedelta, timezone

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry

from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType
from ciris_engine.schemas.services.operations import MemoryQuery, MemoryOpStatus
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.services.graph.base import BaseGraphService
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus

from .period_manager import PeriodManager
from .query_manager import QueryManager
from .edge_manager import EdgeManager
from .consolidators import (
    MetricsConsolidator,
    ConversationConsolidator,
    TraceConsolidator,
    AuditConsolidator,
    TaskConsolidator,
    MemoryConsolidator
)

logger = logging.getLogger(__name__)


class TSDBConsolidationService(BaseGraphService):
    """
    Refactored TSDB Consolidation Service.
    
    Key improvements:
    1. Consolidates BOTH graph nodes AND service correlations
    2. Creates proper edges in graph_edges table
    3. Links summaries to ALL nodes in the period
    4. Includes task summaries with outcomes
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
            time_service: Time service for consistent timestamps
            consolidation_interval_hours: How often to run (default: 6)
            raw_retention_hours: How long to keep raw data (default: 24)
        """
        super().__init__(memory_bus=memory_bus, time_service=time_service)
        self.service_name = "TSDBConsolidationService"
        
        # Initialize components
        self._period_manager = PeriodManager(consolidation_interval_hours)
        self._query_manager = QueryManager(memory_bus)
        self._edge_manager = EdgeManager()
        
        # Initialize all consolidators
        self._metrics_consolidator = MetricsConsolidator(memory_bus)
        self._memory_consolidator = MemoryConsolidator(memory_bus)
        self._task_consolidator = TaskConsolidator(memory_bus)
        self._conversation_consolidator = ConversationConsolidator(memory_bus)
        self._trace_consolidator = TraceConsolidator(memory_bus)
        self._audit_consolidator = AuditConsolidator(memory_bus)
        
        self._consolidation_interval = timedelta(hours=consolidation_interval_hours)
        self._raw_retention = timedelta(hours=raw_retention_hours)
        
        # Task management
        self._consolidation_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Track last successful consolidation
        self._last_consolidation: Optional[datetime] = None
        self._start_time: Optional[datetime] = None
    
    def _set_service_registry(self, registry: "ServiceRegistry") -> None:
        """Set the service registry for accessing services."""
        self._service_registry = registry
        
        # Only get time service from registry if not provided
        if not self._time_service and registry:
            from ciris_engine.schemas.runtime.enums import ServiceType
            time_services = registry.get_services_by_type(ServiceType.TIME)
            if time_services:
                self._time_service = time_services[0]
    
    def _now(self) -> datetime:
        """Get current time from time service."""
        return self._time_service.now() if self._time_service else datetime.now(timezone.utc)
    
    async def start(self) -> None:
        """Start the consolidation service."""
        if self._running:
            logger.warning("TSDBConsolidationService already running")
            return
        
        await super().start()
        self._running = True
        self._start_time = self._now()
        
        # Start the consolidation loop
        self._consolidation_task = asyncio.create_task(self._consolidation_loop())
        logger.info("TSDBConsolidationService started - consolidating every 6 hours")
    
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
        
        await super().stop()
        logger.info("TSDBConsolidationService stopped")
    
    async def _consolidation_loop(self) -> None:
        """Main consolidation loop that runs every 6 hours."""
        while self._running:
            try:
                # Calculate next run time
                next_run = self._period_manager.get_next_period_start(self._now())
                wait_seconds = (next_run - self._now()).total_seconds()
                
                if wait_seconds > 0:
                    logger.info(f"Next consolidation at {next_run} ({wait_seconds:.0f}s)")
                    await asyncio.sleep(wait_seconds)
                
                if self._running:
                    await self._run_consolidation()
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Consolidation loop error: {e}", exc_info=True)
                await asyncio.sleep(300)  # 5 minutes
    
    async def _run_consolidation(self) -> None:
        """Run a single consolidation cycle."""
        try:
            logger.info("Starting TSDB consolidation cycle")
            
            # Find periods that need consolidation
            now = self._now()
            cutoff_time = now - timedelta(hours=24)
            
            # Get oldest unconsolidated data
            oldest_data = await self._find_oldest_unconsolidated_period()
            if not oldest_data:
                logger.info("No unconsolidated data found")
                return
            
            # Process periods
            current_start, _ = self._period_manager.get_period_boundaries(oldest_data)
            periods_consolidated = 0
            max_periods = 30  # Limit per run
            
            while current_start < cutoff_time and periods_consolidated < max_periods:
                current_end = current_start + self._consolidation_interval
                
                # Check if already consolidated
                if not await self._query_manager.check_period_consolidated(current_start):
                    logger.info(f"Consolidating period: {current_start} to {current_end}")
                    
                    summaries = await self._consolidate_period(current_start, current_end)
                    if summaries:
                        logger.info(f"Created {len(summaries)} summaries for period")
                        periods_consolidated += 1
                
                current_start = current_end
            
            if periods_consolidated > 0:
                logger.info(f"Consolidated {periods_consolidated} periods")
            
            # Cleanup old data
            await self._cleanup_old_data()
            
            # Cleanup orphaned edges
            await self._edge_manager.cleanup_orphaned_edges()
            
            self._last_consolidation = now
            
        except Exception as e:
            logger.error(f"Consolidation failed: {e}", exc_info=True)
    
    async def _consolidate_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[GraphNode]:
        """
        Consolidate all data for a specific period.
        
        This is the main consolidation logic that:
        1. Queries all nodes and correlations
        2. Creates summary nodes
        3. Creates proper edges
        
        Args:
            period_start: Start of period
            period_end: End of period
            
        Returns:
            List of created summary nodes
        """
        period_label = self._period_manager.get_period_label(period_start)
        summaries_created = []
        
        # 1. Query ALL data for the period
        logger.info(f"Querying all data for period {period_label}")
        
        # Get all graph nodes in the period
        nodes_by_type = await self._query_manager.query_all_nodes_in_period(
            period_start, period_end
        )
        
        # Get all correlations in the period
        correlations = await self._query_manager.query_service_correlations(
            period_start, period_end
        )
        
        # Get tasks completed in the period
        tasks = await self._query_manager.query_tasks_in_period(
            period_start, period_end
        )
        
        # 2. Create summaries
        
        # Metrics summary (TSDB data + correlations)
        tsdb_nodes = nodes_by_type.get('tsdb_data', [])
        metric_correlations = correlations.get('metric_datapoint', [])
        
        if tsdb_nodes or metric_correlations:
            metric_summary = await self._metrics_consolidator.consolidate(
                period_start, period_end, period_label,
                tsdb_nodes, metric_correlations
            )
            if metric_summary:
                summaries_created.append(metric_summary)
        
        # Task summary
        if tasks:
            task_summary = await self._task_consolidator.consolidate(
                period_start, period_end, period_label, tasks
            )
            if task_summary:
                summaries_created.append(task_summary)
        
        # Memory consolidator doesn't create a summary, it only creates edges
        # We'll call it later in _create_all_edges
        
        # Conversation summary
        service_interactions = correlations.get('service_interaction', [])
        if service_interactions:
            conversation_summary = await self._conversation_consolidator.consolidate(
                period_start, period_end, period_label, service_interactions
            )
            if conversation_summary:
                summaries_created.append(conversation_summary)
                
                # Get participant data and create user edges
                participant_data = self._conversation_consolidator.get_participant_data(
                    service_interactions
                )
                if participant_data:
                    user_edges = await self._edge_manager.create_user_participation_edges(
                        conversation_summary,
                        participant_data,
                        period_label
                    )
                    logger.info(f"Created {user_edges} user participation edges")
        
        # Trace summary
        trace_spans = correlations.get('trace_span', [])
        if trace_spans:
            trace_summary = await self._trace_consolidator.consolidate(
                period_start, period_end, period_label, trace_spans
            )
            if trace_summary:
                summaries_created.append(trace_summary)
        
        # Audit summary
        audit_nodes = nodes_by_type.get('audit_entry', [])
        if audit_nodes:
            audit_summary = await self._audit_consolidator.consolidate(
                period_start, period_end, period_label, audit_nodes
            )
            if audit_summary:
                summaries_created.append(audit_summary)
        
        # 3. Create edges
        if summaries_created:
            await self._create_all_edges(
                summaries_created, 
                nodes_by_type,
                correlations,
                tasks,
                period_start,
                period_label
            )
        
        return summaries_created
    
    async def _create_all_edges(
        self,
        summaries: List[GraphNode],
        nodes_by_type: Dict[str, List[GraphNode]],
        correlations: Dict[str, List[Dict[str, Any]]],
        tasks: List[Dict[str, Any]],
        period_start: datetime,
        period_label: str
    ) -> None:
        """
        Create all necessary edges for the summaries.
        
        Args:
            summaries: List of summary nodes created
            nodes_by_type: All nodes in the period by type
            correlations: All correlations in the period by type
            tasks: All tasks in the period
            period_start: Start of the period
            period_label: Human-readable period label
        """
        all_edges = []
        
        # Collect edges from each consolidator based on summary type
        for summary in summaries:
            if summary.type == NodeType.TSDB_SUMMARY:
                # Get edges from metrics consolidator
                tsdb_nodes = nodes_by_type.get('tsdb_data', [])
                metric_correlations = correlations.get('metric_datapoint', [])
                edges = self._metrics_consolidator.get_edges(
                    summary, tsdb_nodes, metric_correlations
                )
                all_edges.extend(edges)
                
            elif summary.type == NodeType.CONVERSATION_SUMMARY:
                # Get edges from conversation consolidator
                service_interactions = correlations.get('service_interaction', [])
                edges = self._conversation_consolidator.get_edges(
                    summary, service_interactions
                )
                all_edges.extend(edges)
                
            elif summary.type == NodeType.TRACE_SUMMARY:
                # Get edges from trace consolidator
                trace_spans = correlations.get('trace_span', [])
                edges = self._trace_consolidator.get_edges(
                    summary, trace_spans
                )
                all_edges.extend(edges)
                
            elif summary.type == NodeType.AUDIT_SUMMARY:
                # Get edges from audit consolidator
                audit_nodes = nodes_by_type.get('audit_entry', [])
                edges = self._audit_consolidator.get_edges(
                    summary, audit_nodes
                )
                all_edges.extend(edges)
                
            elif summary.type == NodeType.TASK_SUMMARY:
                # Get edges from task consolidator
                edges = self._task_consolidator.get_edges(
                    summary, tasks
                )
                all_edges.extend(edges)
        
        # Get memory edges (links from summaries to memory nodes)
        memory_edges = await self._memory_consolidator.consolidate(
            period_start, period_start + self._consolidation_interval,
            period_label, nodes_by_type, summaries
        )
        all_edges.extend(memory_edges)
        
        # Create all edges in batch
        if all_edges:
            edges_created = await self._edge_manager.create_edges(all_edges)
            logger.info(f"Created {edges_created} edges for period {period_label}")
        
        # Create temporal edges to previous period summaries
        for summary in summaries:
            # Extract summary type from ID
            summary_type = summary.id.split('_')[0] + '_' + summary.id.split('_')[1]
            previous_period = period_start - self._consolidation_interval
            previous_id = await self._edge_manager.get_previous_summary_id(
                summary_type,
                previous_period.strftime('%Y%m%d_%H')
            )
            
            if previous_id:
                created = await self._edge_manager.create_temporal_edges(
                    summary, previous_id
                )
                if created:
                    logger.debug(f"Created {created} temporal edges for {summary.id}")
        
        # Also check if there's a next period already consolidated and link to it
        edges_to_next = await self._edge_manager.update_next_period_edges(
            period_start, summaries
        )
        if edges_to_next > 0:
            logger.info(f"Created {edges_to_next} edges to next period summaries")
    
    async def _find_oldest_unconsolidated_period(self) -> Optional[datetime]:
        """Find the oldest data that needs consolidation."""
        try:
            from ciris_engine.logic.persistence.db.core import get_db_connection
            
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Check for oldest TSDB data
                cursor.execute("""
                    SELECT MIN(created_at) as oldest
                    FROM graph_nodes
                    WHERE node_type = 'tsdb_data'
                """)
                row = cursor.fetchone()
                
                if row and row['oldest']:
                    return datetime.fromisoformat(row['oldest'].replace('Z', '+00:00'))
                
                # Check for oldest correlation
                cursor.execute("""
                    SELECT MIN(timestamp) as oldest
                    FROM service_correlations
                """)
                row = cursor.fetchone()
                
                if row and row['oldest']:
                    return datetime.fromisoformat(row['oldest'].replace('Z', '+00:00'))
                    
        except Exception as e:
            logger.error(f"Failed to find oldest data: {e}")
        
        return None
    
    async def _cleanup_old_data(self) -> None:
        """Clean up old consolidated data."""
        # TODO: Implement cleanup logic
        # This should mark nodes as consolidated and delete old data
        pass
    
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
                "consolidate_all_data",
                "create_proper_edges",
                "track_memory_events",
                "summarize_tasks"
            ],
            version="2.0.0",
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
            custom_metrics={}
        )
    
    def get_node_type(self) -> NodeType:
        """Get the node type this service manages."""
        return NodeType.TSDB_SUMMARY