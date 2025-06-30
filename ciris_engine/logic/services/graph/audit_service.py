"""
Consolidated Graph Audit Service

Combines functionality from:
- AuditService (file-based)
- SignedAuditService (cryptographic signatures)
- GraphAuditService (graph-based storage)

This service provides:
1. Graph-based storage (everything is memory)
2. Optional file export for compliance
3. Cryptographic hash chain for tamper evidence
4. Unified interface for all audit operations
"""

import asyncio
import json
import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import List, Optional, TYPE_CHECKING
from uuid import uuid4

if TYPE_CHECKING:
    from ciris_engine.logic.registries.base import ServiceRegistry

from ciris_engine.protocols.services import AuditService as AuditServiceProtocol, GraphServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.schemas.runtime.enums import HandlerActionType
from ciris_engine.schemas.runtime.audit import AuditActionContext, AuditConscienceResult, AuditRequest
# TSDB functionality integrated into graph nodes
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.nodes import AuditEntry as AuditEntryNode, AuditEntryContext
# Type alias for protocol compatibility
AuditEntry = AuditEntryNode
from ciris_engine.schemas.services.operations import MemoryOpStatus
from ciris_engine.schemas.services.graph.audit import (
    AuditEventData, VerificationReport, AuditQuery
)
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.audit.hash_chain import AuditHashChain
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.logic.audit.verifier import AuditVerifier

logger = logging.getLogger(__name__)

try:
    from ciris_engine.logic.audit.signature_manager import AuditSignatureManager
except ImportError as e:
    logger.error(f"Failed to import AuditSignatureManager: {e}")
    raise

class GraphAuditService(AuditServiceProtocol, GraphServiceProtocol, ServiceProtocol):
    """
    Consolidated audit service that stores all audit entries in the graph.

    Features:
    - Primary storage in graph (everything is memory)
    - Optional file export for compliance
    - Cryptographic hash chain for integrity
    - Digital signatures for non-repudiation
    - Unified interface for all audit operations
    """

    def __init__(
        self,
        memory_bus: Optional[MemoryBus] = None,
        time_service: Optional[TimeServiceProtocol] = None,
        # File export options
        export_path: Optional[str] = None,
        export_format: str = "jsonl",  # jsonl, csv, or sqlite
        # Hash chain options
        enable_hash_chain: bool = True,
        db_path: str = "ciris_audit.db",
        key_path: str = "audit_keys",
        # Retention options
        retention_days: int = 90,
        cache_size: int = 1000
    ) -> None:
        """
        Initialize the consolidated audit service.

        Args:
            memory_bus: Bus for graph storage operations
            time_service: Time service for consistent timestamps
            export_path: Optional path for file exports
            export_format: Format for exports (jsonl, csv, sqlite)
            enable_hash_chain: Whether to maintain cryptographic hash chain
            db_path: Path for hash chain database
            key_path: Directory for signing keys
            retention_days: How long to retain audit data
            cache_size: Size of in-memory cache
        """
        super().__init__()
        if not time_service:
            raise RuntimeError("CRITICAL: TimeService is required for GraphAuditService")
        self._memory_bus = memory_bus
        self._time_service = time_service
        self._service_registry: Optional['ServiceRegistry'] = None

        # Export configuration
        self.export_path = Path(export_path) if export_path else None
        self.export_format = export_format

        # Hash chain configuration
        self.enable_hash_chain = enable_hash_chain
        self.db_path = Path(db_path)
        self.key_path = Path(key_path)

        # Retention configuration
        self.retention_days = retention_days

        # Cache for recent entries
        self._recent_entries: List[AuditRequest] = []
        self._max_cached_entries = cache_size

        # Hash chain components
        self.hash_chain: Optional[AuditHashChain] = None
        self.signature_manager: Optional[AuditSignatureManager] = None
        self.verifier: Optional[AuditVerifier] = None
        self._db_connection: Optional[sqlite3.Connection] = None

        # Export buffer
        self._export_buffer: List[AuditRequest] = []
        self._export_task: Optional[asyncio.Task] = None

    def set_service_registry(self, registry: object) -> None:
        """Set the service registry for accessing memory bus."""
        from ciris_engine.logic.registries.base import ServiceRegistry
        if isinstance(registry, ServiceRegistry):
            self._service_registry = registry
        if not self._memory_bus and registry:
            try:
                from ciris_engine.logic.buses import MemoryBus
                self._memory_bus = MemoryBus(registry, self._time_service)
            except Exception as e:
                logger.error(f"Failed to initialize memory bus: {e}")

    async def start(self) -> None:
        """Start the audit service."""
        logger.info("Starting consolidated GraphAuditService")

        # Initialize hash chain if enabled
        if self.enable_hash_chain:
            await self._initialize_hash_chain()

        # Create export directory if needed
        if self.export_path:
            self.export_path.parent.mkdir(parents=True, exist_ok=True)

        # Start export task if configured
        if self.export_path:
            self._export_task = asyncio.create_task(self._export_worker())

        logger.info("GraphAuditService started - all audit data flows through graph")

    async def stop(self) -> None:
        """Stop the audit service."""
        # Flush export buffer
        if self._export_buffer:
            await self._flush_exports()

        # Cancel export task
        if self._export_task:
            self._export_task.cancel()
            try:
                await self._export_task
            except asyncio.CancelledError:
                pass

        # Log final shutdown event BEFORE closing database
        from ciris_engine.schemas.services.graph.audit import AuditEventData
        shutdown_event = AuditEventData(
            entity_id="audit_service",
            actor="system",
            outcome="success",
            severity="info",
            action="shutdown",
            metadata={
                "cached_entries": len(self._recent_entries),
                "pending_exports": len(self._export_buffer)
            }
        )
        try:
            await self.log_event("audit_service_shutdown", shutdown_event)
        except Exception as e:
            logger.warning(f"Failed to log shutdown event: {e}")

        # Close database connection AFTER logging
        if self._db_connection:
            self._db_connection.close()

        logger.info("GraphAuditService stopped")

    async def log_action(
        self,
        action_type: HandlerActionType,
        context: AuditActionContext,
        outcome: Optional[str] = None
    ) -> None:
        """Log an action by storing it in the graph."""
        try:
            # Create audit entry
            entry = AuditRequest(
                entry_id=str(uuid4()),
                timestamp=self._time_service.now(),
                entity_id=context.thought_id,
                event_type=action_type.value,
                actor=context.handler_name or "system",
                details={
                    "action_type": action_type.value,
                    "thought_id": context.thought_id,
                    "task_id": context.task_id,
                    "handler_name": context.handler_name,
                    "metadata": str(getattr(context, "metadata", {}))
                },
                outcome=outcome
            )

            # Store in graph
            await self._store_entry_in_graph(entry, action_type)

            # Add to hash chain if enabled
            if self.enable_hash_chain:
                await self._add_to_hash_chain(entry)

            # Cache for quick access
            self._cache_entry(entry)

            # Queue for export if configured
            if self.export_path:
                self._export_buffer.append(entry)

        except Exception as e:
            logger.error(f"Failed to log action {action_type}: {e}")

    async def log_event(
        self,
        event_type: str,
        event_data: AuditEventData
    ) -> None:
        """Log a general event."""
        try:
            # Create audit entry with string-only details
            details_dict = {}
            for key, value in event_data.model_dump().items():
                if value is not None:
                    details_dict[key] = str(value) if not isinstance(value, str) else value

            entry = AuditRequest(
                entry_id=str(uuid4()),
                timestamp=self._time_service.now(),
                entity_id=event_data.entity_id,
                event_type=event_type,
                actor=event_data.actor,
                details=details_dict,
                outcome=event_data.outcome
            )

            # Create graph node
            node = AuditEntryNode(
                id=f"audit_{entry.entry_id}",
                action=event_type,
                actor=entry.actor,
                timestamp=entry.timestamp,
                context=AuditEntryContext(
                    service_name=self.__class__.__name__,
                    correlation_id=entry.entry_id,
                    additional_data={
                        "event_type": event_type,
                        "severity": event_data.severity,
                        "outcome": entry.outcome or "logged"
                    }
                ),
                scope=GraphScope.LOCAL,
                attributes={
                    "event_id": entry.entry_id,
                    "severity": event_data.severity
                }
            )

            # Store in graph
            if self._memory_bus:
                await self._memory_bus.memorize(
                    node=node.to_graph_node(),
                    handler_name="audit_service",
                    metadata={
                        "audit_entry": entry.model_dump(),
                        "event": True,
                        "immutable": True
                    }
                )

            # Add to hash chain if enabled
            if self.enable_hash_chain:
                await self._add_to_hash_chain(entry)

            # Cache and export
            self._cache_entry(entry)
            if self.export_path:
                self._export_buffer.append(entry)

        except Exception as e:
            logger.error(f"Failed to log event {event_type}: {e}")

    async def log_conscience_event(
        self,
        conscience_name: str,
        action_type: str,
        result: AuditConscienceResult
    ) -> None:
        """Log conscience check events."""
        # Create proper AuditEventData object
        from ciris_engine.schemas.services.graph.audit import AuditEventData

        event_data = AuditEventData(
            entity_id=conscience_name,
            actor="conscience_system",
            outcome="allowed" if result.allowed else "denied",
            severity="high" if not result.allowed else "info",
            action=action_type,
            reason=result.reason,
            metadata={
                "conscience_name": conscience_name,
                "allowed": result.allowed,
                "risk_level": result.risk_level or "unknown",
                "modifications": json.dumps(result.modifications) if result.modifications else "{}"
            }
        )

        await self.log_event("conscience_check", event_data)

    async def get_audit_trail(
        self,
        entity_id: str,
        limit: int = 100
    ) -> List[AuditRequest]:
        """Get audit trail for an entity."""
        # Check cache first
        cached = [e for e in self._recent_entries if e.entity_id == entity_id]
        if len(cached) >= limit:
            return cached[:limit]

        # Query from graph
        if not self._memory_bus:
            logger.error("Memory bus not available for audit queries")
            return cached

        try:
            # Query timeseries data
            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=24 * 30,  # 30 days
                correlation_types=["AUDIT_EVENT"],
                handler_name="audit_service"
            )

            # Convert to AuditEntry objects
            results = self._convert_timeseries_to_entries(timeseries_data, entity_id)

            # Combine with cache and deduplicate
            all_entries = {e.entry_id: e for e in cached}
            all_entries.update({e.entry_id: e for e in results})

            # Sort and limit
            sorted_entries = sorted(
                all_entries.values(),
                key=lambda x: x.timestamp,
                reverse=True
            )

            return sorted_entries[:limit]

        except Exception as e:
            logger.error(f"Failed to get audit trail: {e}")
            return cached

    async def query_audit_trail(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        action_types: Optional[List[str]] = None,
        thought_id: Optional[str] = None,
        task_id: Optional[str] = None,
        limit: int = 100
    ) -> List[AuditEntry]:
        """Query audit trail with filters."""
        try:
            
            # Calculate time range
            hours = self._calculate_hours(start_time, end_time)

            # Query from graph
            if not self._memory_bus:
                return []

            timeseries_data = await self._memory_bus.recall_timeseries(
                scope="local",
                hours=hours,
                correlation_types=["AUDIT_EVENT"],
                handler_name="audit_service"
            )

            # Filter and convert
            results = []
            for data in timeseries_data:
                # Apply filters
                if not self._matches_filters(
                    data, start_time, end_time, action_types, thought_id, task_id
                ):
                    continue

                # Convert to AuditEntry
                audit_request = self._tsdb_to_audit_entry(data)
                if audit_request:
                    # Convert AuditRequest to AuditEntry for API
                    audit_entry = AuditEntryNode(
                        id=f"audit_{audit_request.entry_id}",
                        action=audit_request.event_type,
                        actor=audit_request.actor,
                        timestamp=audit_request.timestamp,
                        context=AuditEntryContext(
                            service_name=audit_request.details.get("handler_name", ""),
                            correlation_id=audit_request.entity_id,
                            additional_data=audit_request.details
                        ),
                        signature=None,  # Would be in the data if present
                        hash_chain=None,  # Would be in the data if present
                        scope=GraphScope.LOCAL
                    )
                    results.append(audit_entry)

            # Sort and limit
            results.sort(key=lambda x: x.timestamp, reverse=True)
            return results[:limit]

        except Exception as e:
            logger.error(f"Failed to query audit trail: {e}")
            return []

    async def verify_audit_integrity(self) -> VerificationReport:
        """Verify the integrity of the audit trail."""
        start_time = self._time_service.now()

        if not self.enable_hash_chain or not self.verifier:
            return VerificationReport(
                verified=False,
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                chain_intact=False,
                verification_started=start_time,
                verification_completed=self._time_service.now(),
                duration_ms=0,
                errors=["Hash chain not enabled"]
            )

        try:
            result = await asyncio.to_thread(self.verifier.verify_complete_chain)
            end_time = self._time_service.now()

            return VerificationReport(
                verified=result.get("valid", False),
                total_entries=result.get("total_entries", 0),
                valid_entries=result.get("valid_entries", 0),
                invalid_entries=result.get("invalid_entries", 0),
                chain_intact=result.get("chain_valid", False),
                last_valid_entry=result.get("last_valid_entry"),
                first_invalid_entry=result.get("first_invalid_entry"),
                verification_started=start_time,
                verification_completed=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                errors=result.get("errors", []),
                warnings=result.get("warnings", [])
            )
        except Exception as e:
            logger.error(f"Audit verification failed: {e}")
            end_time = self._time_service.now()
            return VerificationReport(
                verified=False,
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                chain_intact=False,
                verification_started=start_time,
                verification_completed=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                errors=[str(e)]
            )

    async def get_verification_report(self) -> VerificationReport:
        """Generate a comprehensive audit verification report."""
        start_time = self._time_service.now()

        if not self.enable_hash_chain or not self.verifier:
            return VerificationReport(
                verified=False,
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                chain_intact=False,
                verification_started=start_time,
                verification_completed=self._time_service.now(),
                duration_ms=0,
                errors=["Hash chain not enabled"]
            )

        try:
            # Delegate to verify_audit_integrity which already returns VerificationReport
            return await self.verify_audit_integrity()
        except Exception as e:
            logger.error(f"Failed to generate verification report: {e}")
            end_time = self._time_service.now()
            return VerificationReport(
                verified=False,
                total_entries=0,
                valid_entries=0,
                invalid_entries=0,
                chain_intact=False,
                verification_started=start_time,
                verification_completed=end_time,
                duration_ms=(end_time - start_time).total_seconds() * 1000,
                errors=[str(e)]
            )

    async def export_audit_data(
        self,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        format: Optional[str] = None
    ) -> str:
        """Export audit data to file."""
        format = format or self.export_format

        # Query data
        entries = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
            limit=10000  # Higher limit for exports
        )

        # Generate filename
        timestamp = self._time_service.now().strftime("%Y%m%d_%H%M%S")
        filename = self.export_path.parent / f"audit_export_{timestamp}.{format}"

        # Export based on format
        if format == "jsonl":
            await self._export_jsonl(entries, filename)
        elif format == "csv":
            await self._export_csv(entries, filename)
        elif format == "sqlite":
            await self._export_sqlite(entries, filename)
        else:
            raise ValueError(f"Unsupported export format: {format}")

        return str(filename)

    # ========== GraphServiceProtocol Implementation ==========

    async def store_in_graph(self, node: GraphNode) -> str:
        """Store a node in the graph."""
        if not self._memory_bus:
            raise RuntimeError("Memory bus not available")
        result = await self._memory_bus.memorize(node)
        return node.id if result.status == MemoryOpStatus.OK else ""

    async def query_graph(self, query: AuditQuery) -> List[AuditRequest]:
        """Query the graph."""
        if not self._memory_bus:
            return []
        # Convert AuditQuery to parameters
        if query.start_time and query.end_time:
            hours = int((query.end_time - query.start_time).total_seconds() / 3600)
        else:
            hours = 24  # Default to last 24 hours

        # Query timeseries data
        nodes = await self._memory_bus.recall_timeseries(
            scope="local",
            hours=hours,
            correlation_types=["AUDIT_EVENT"]
        )

        # Convert nodes to AuditEntry objects using proper conversion
        entries = []
        for node in nodes:
            entry = self._tsdb_to_audit_entry(node)
            if entry:
                entries.append(entry)

        # Apply filters
        if query.event_type:
            entries = [e for e in entries if e.event_type == query.event_type]
        if query.actor:
            entries = [e for e in entries if e.actor == query.actor]
        if query.entity_id:
            entries = [e for e in entries if e.entity_id == query.entity_id]

        # Sort and limit
        entries.sort(key=lambda e: e.timestamp, reverse=query.order_desc)
        if query.limit:
            entries = entries[query.offset:query.offset + query.limit]

        return entries

    def get_node_type(self) -> str:
        """Get the type of nodes this service manages."""
        return "AUDIT"

    # ========== ServiceProtocol Implementation ==========

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="GraphAuditService",
            actions=[
                "log_action", "log_event", "log_conscience_event",
                "get_audit_trail", "query_audit_trail",
                "verify_audit_integrity", "get_verification_report",
                "export_audit_data", "store_in_graph", "query_graph"
            ],
            version="2.0.0",
            dependencies=["MemoryService"]
        )

    def get_status(self) -> ServiceStatus:
        """Get service status."""
        return ServiceStatus(
            service_name="GraphAuditService",
            service_type="audit",
            is_healthy=self._memory_bus is not None,
            uptime_seconds=0.0,  # TODO: Track uptime
            metrics={
                "cached_entries": float(len(self._recent_entries)),
                "pending_exports": float(len(self._export_buffer)),
                "hash_chain_enabled": float(self.enable_hash_chain)
            }
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._memory_bus is not None

    # ========== Private Helper Methods ==========

    async def _store_entry_in_graph(
        self,
        entry: AuditRequest,
        action_type: HandlerActionType
    ) -> None:
        """Store an audit entry in the graph."""
        if not self._memory_bus:
            logger.error("Memory bus not available for audit storage")
            return

        # Create specialized audit node
        node = AuditEntryNode(
            id=f"audit_{action_type.value}_{entry.entry_id}",
            action=action_type.value,
            actor=entry.actor,
            timestamp=entry.timestamp,
            context=AuditEntryContext(
                service_name=entry.details.get("handler_name", ""),
                correlation_id=entry.entry_id,
                additional_data={
                    "thought_id": entry.details.get("thought_id", ""),
                    "task_id": entry.details.get("task_id", ""),
                    "outcome": entry.outcome or "success",
                    "severity": self._get_severity(action_type)
                }
            ),
            scope=GraphScope.LOCAL,
            attributes={
                "action_type": action_type.value,
                "event_id": entry.entry_id
            }
        )

        # Store via memory bus
        result = await self._memory_bus.memorize(
            node=node.to_graph_node(),
            handler_name="audit_service",
            metadata={
                "audit_entry": entry.model_dump(),
                "immutable": True
            }
        )

        if result.status != MemoryOpStatus.OK:
            logger.error(f"Failed to store audit entry in graph: {result}")

    async def _initialize_hash_chain(self) -> None:
        """Initialize hash chain components."""
        try:
            # Ensure directories exist
            self.key_path.mkdir(parents=True, exist_ok=True)

            # Initialize database
            await self._init_database()

            # Initialize components
            self.hash_chain = AuditHashChain(str(self.db_path))
            logger.debug(f"Initializing AuditSignatureManager with key_path={self.key_path}, db_path={self.db_path}, time_service={self._time_service}")

            # Ensure time_service is not None
            if not self._time_service:
                raise RuntimeError("TimeService is None - cannot initialize AuditSignatureManager")

            # Check actual types
            logger.debug(f"Types: key_path={type(self.key_path)}, db_path={type(self.db_path)}, time_service={type(self._time_service)}")

            self.signature_manager = AuditSignatureManager(str(self.key_path), str(self.db_path), self._time_service)
            self.verifier = AuditVerifier(str(self.db_path), str(self.key_path), self._time_service)

            # Initialize in thread
            await asyncio.to_thread(self._init_components_sync)

            logger.info("Hash chain audit system initialized")

        except Exception as e:
            logger.error(f"Failed to initialize hash chain: {e}", exc_info=True)
            self.enable_hash_chain = False

    def _init_components_sync(self) -> None:
        """Synchronous initialization of audit components."""
        if not self.hash_chain or not self.signature_manager or not self.verifier:
            raise RuntimeError("Hash chain components not initialized")

        self.hash_chain.initialize()
        self.signature_manager.initialize()
        self.verifier.initialize()

        if not self.signature_manager.test_signing():
            raise RuntimeError("Signing test failed")

    async def _init_database(self) -> None:
        """Initialize the audit database."""
        def _create_tables() -> None:
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            cursor = conn.cursor()

            # Audit log table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log_v2 (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    originator_id TEXT NOT NULL,
                    target_id TEXT,
                    event_summary TEXT,
                    event_payload TEXT,
                    sequence_number INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    signing_key_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sequence_number)
                )
            """)

            # Signing keys table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_signing_keys (
                    key_id TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                    key_size INTEGER NOT NULL DEFAULT 2048,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TEXT
                )
            """)

            # Indexes
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_v2_event_timestamp
                ON audit_log_v2(event_timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_v2_event_type
                ON audit_log_v2(event_type)
            """)

            conn.commit()
            conn.close()

        await asyncio.to_thread(_create_tables)
        self._db_connection = sqlite3.connect(str(self.db_path), check_same_thread=False)

    async def _add_to_hash_chain(self, entry: AuditRequest) -> None:
        """Add an entry to the hash chain."""
        if not self.enable_hash_chain:
            return

        def _write_to_chain() -> None:
            entry_dict = {
                "event_id": entry.entry_id,
                "event_timestamp": entry.timestamp.isoformat(),
                "event_type": entry.event_type,
                "originator_id": entry.entity_id,
                "event_payload": json.dumps(entry.details)
            }

            if not self.hash_chain or not self.signature_manager:
                raise RuntimeError("Hash chain not available")

            prepared = self.hash_chain.prepare_entry(entry_dict)
            signature = self.signature_manager.sign_entry(prepared["entry_hash"])

            if not self._db_connection:
                raise RuntimeError("Database connection not available")

            cursor = self._db_connection.cursor()
            cursor.execute("""
                INSERT INTO audit_log_v2
                (event_id, event_timestamp, event_type, originator_id,
                 event_summary, event_payload, sequence_number, previous_hash,
                 entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.entry_id,
                entry.timestamp.isoformat(),
                entry.event_type,
                entry.entity_id,
                f"{entry.event_type} by {entry.actor}",
                json.dumps(entry.details),
                prepared["sequence_number"],
                prepared["previous_hash"],
                prepared["entry_hash"],
                signature,
                self.signature_manager.key_id or "unknown"
            ))

            self._db_connection.commit()

        try:
            await asyncio.to_thread(_write_to_chain)
        except Exception as e:
            logger.error(f"Failed to add to hash chain: {e}")

    def _cache_entry(self, entry: AuditRequest) -> None:
        """Add entry to cache."""
        self._recent_entries.append(entry)
        if len(self._recent_entries) > self._max_cached_entries:
            self._recent_entries = self._recent_entries[-self._max_cached_entries:]

    async def _export_worker(self) -> None:
        """Background task to export audit data."""
        while True:
            try:
                await asyncio.sleep(60)  # Export every minute
                if self._export_buffer:
                    await self._flush_exports()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Export worker error: {e}")

    async def _flush_exports(self) -> None:
        """Flush export buffer to file."""
        if not self._export_buffer or not self.export_path:
            return

        try:
            if self.export_format == "jsonl":
                await self._export_jsonl(self._export_buffer, self.export_path)
            elif self.export_format == "csv":
                await self._export_csv(self._export_buffer, self.export_path)
            elif self.export_format == "sqlite":
                await self._export_sqlite(self._export_buffer, self.export_path)

            self._export_buffer.clear()
        except Exception as e:
            logger.error(f"Failed to flush exports: {e}")

    async def _export_jsonl(self, entries: List[AuditRequest], path: Path) -> None:
        """Export entries to JSONL format."""
        def _write_jsonl() -> None:
            with open(path, "a") as f:
                for entry in entries:
                    f.write(json.dumps(entry.model_dump(), default=str) + "\n")

        await asyncio.to_thread(_write_jsonl)

    async def _export_csv(self, entries: List[AuditRequest], path: Path) -> None:
        """Export entries to CSV format."""
        import csv

        def _write_csv() -> None:
            file_exists = path.exists()
            with open(path, "a", newline="") as f:
                writer = csv.writer(f)

                # Write header if new file
                if not file_exists:
                    writer.writerow([
                        "entry_id", "timestamp", "entity_id", "event_type",
                        "actor", "outcome", "details"
                    ])

                # Write entries
                for entry in entries:
                    writer.writerow([
                        entry.entry_id,
                        entry.timestamp.isoformat(),
                        entry.entity_id,
                        entry.event_type,
                        entry.actor,
                        entry.outcome,
                        json.dumps(entry.details)
                    ])

        await asyncio.to_thread(_write_csv)

    async def _export_sqlite(self, entries: List[AuditRequest], path: Path) -> None:
        """Export entries to SQLite format."""
        def _write_sqlite() -> None:
            conn = sqlite3.connect(str(path), check_same_thread=False)
            cursor = conn.cursor()

            # Create table if needed
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_export (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    outcome TEXT,
                    details TEXT
                )
            """)

            # Insert entries
            for entry in entries:
                cursor.execute("""
                    INSERT OR REPLACE INTO audit_export
                    (entry_id, timestamp, entity_id, event_type, actor, outcome, details)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    entry.entry_id,
                    entry.timestamp.isoformat(),
                    entry.entity_id,
                    entry.event_type,
                    entry.actor,
                    entry.outcome,
                    json.dumps(entry.details)
                ))

            conn.commit()
            conn.close()

        await asyncio.to_thread(_write_sqlite)

    def _get_severity(self, action: HandlerActionType) -> str:
        """Determine severity level for an action."""
        if action in [HandlerActionType.DEFER, HandlerActionType.REJECT, HandlerActionType.FORGET]:
            return "high"
        elif action in [HandlerActionType.TOOL, HandlerActionType.MEMORIZE, HandlerActionType.TASK_COMPLETE]:
            return "medium"
        else:
            return "low"

    def _calculate_hours(
        self,
        start_time: Optional[datetime],
        end_time: Optional[datetime]
    ) -> int:
        """Calculate hours for time range."""
        if start_time and end_time:
            return int((end_time - start_time).total_seconds() / 3600)
        elif start_time:
            return int((self._time_service.now() - start_time).total_seconds() / 3600)
        else:
            return 24 * 30  # Default 30 days

    def _matches_filters(
        self,
        data: GraphNode,
        start_time: Optional[datetime],
        end_time: Optional[datetime],
        action_types: Optional[List[str]],
        thought_id: Optional[str],
        task_id: Optional[str]
    ) -> bool:
        """Check if data matches query filters."""
        # Time filters
        timestamp = data.attributes.created_at if hasattr(data.attributes, 'created_at') else data.updated_at
        if timestamp:
            if start_time and timestamp < start_time:
                return False
            if end_time and timestamp > end_time:
                return False

        # Action type filter
        tags = data.attributes.tags if hasattr(data.attributes, 'tags') else []
        _tag_dict = {tag: True for tag in tags}  # Convert list to dict for lookup

        # Check attributes dict as well
        attrs = data.attributes.model_dump() if hasattr(data.attributes, 'model_dump') else {}

        if action_types and attrs.get("action_type") not in action_types:
            return False

        # Entity filters
        if thought_id and attrs.get("thought_id") != thought_id:
            return False
        if task_id and attrs.get("task_id") != task_id:
            return False

        return True

    def _tsdb_to_audit_entry(self, data: GraphNode) -> Optional[AuditRequest]:
        """Convert TSDB node to AuditEntry."""
        # Check if this is an AuditEntryNode by looking for the marker
        attrs = data.attributes if isinstance(data.attributes, dict) else {}

        # If it's an AuditEntryNode stored with to_graph_node(), convert back
        if attrs.get("_node_class") == "AuditEntry":
            try:
                audit_node = AuditEntryNode.from_graph_node(data)
                # Convert from AuditEntryNode to runtime AuditRequest
                return AuditRequest(
                    entry_id=audit_node.id.replace("audit_", ""),
                    timestamp=audit_node.timestamp,
                    entity_id=audit_node.context.correlation_id or "",
                    event_type=audit_node.action,
                    actor=audit_node.actor,
                    details={
                        "action_type": audit_node.action,
                        "thought_id": audit_node.context.additional_data.get("thought_id", "") if audit_node.context.additional_data else "",
                        "task_id": audit_node.context.additional_data.get("task_id", "") if audit_node.context.additional_data else "",
                        "handler_name": audit_node.context.service_name or "",
                        "context": audit_node.context.model_dump()
                    },
                    outcome=audit_node.context.additional_data.get("outcome") if audit_node.context.additional_data else None
                )
            except Exception as e:
                logger.warning(f"Failed to convert AuditEntryNode: {e}, falling back to manual parsing")

        # Fallback: manual parsing for backwards compatibility
        # Extract attributes
        attrs = data.attributes.model_dump() if hasattr(data.attributes, 'model_dump') else {}
        _tags = data.attributes.tags if hasattr(data.attributes, 'tags') else []

        # Look for action_type in attributes
        action_type = attrs.get("action_type")
        if not action_type and "action_type" in attrs:
            action_type = attrs["action_type"]

        if not action_type:
            return None

        # Get timestamp
        timestamp = data.attributes.created_at if hasattr(data.attributes, 'created_at') else data.updated_at
        if not timestamp:
            timestamp = self._time_service.now()

        return AuditRequest(
            entry_id=attrs.get("event_id", str(uuid4())),
            timestamp=timestamp,
            entity_id=attrs.get("thought_id", "") or attrs.get("task_id", ""),
            event_type=action_type,
            actor=attrs.get("actor", attrs.get("handler_name", "system")),
            details={
                "action_type": action_type,
                "thought_id": attrs.get("thought_id", ""),
                "task_id": attrs.get("task_id", ""),
                "handler_name": attrs.get("handler_name", ""),
                "attributes": attrs
            },
            outcome=attrs.get("outcome")
        )

    def _convert_timeseries_to_entries(
        self,
        timeseries_data: List[GraphNode],
        entity_id: Optional[str] = None
    ) -> List[AuditRequest]:
        """Convert timeseries data to audit entries."""
        results = []

        for data in timeseries_data:
            # Filter by entity if specified
            if entity_id:
                tags = data.tags or {}
                if entity_id not in [tags.get("thought_id"), tags.get("task_id")]:
                    continue

            # Convert to entry
            entry = self._tsdb_to_audit_entry(data)
            if entry:
                results.append(entry)

        return results

    async def query_events(
        self,
        event_type: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100
    ) -> List[dict]:
        """Query audit events."""
        # Call query_audit_trail directly with parameters
        entries = await self.query_audit_trail(
            start_time=start_time,
            end_time=end_time,
            action_types=[event_type] if event_type else None,
            limit=limit
        )

        # Convert to dict format expected by protocol
        return [
            {
                "event_id": entry.entry_id,
                "event_type": entry.event_type,
                "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                "user_id": entry.actor,  # Using actor as user_id
                "data": entry.details,
                "metadata": {"outcome": entry.outcome} if entry.outcome else {}
            }
            for entry in entries
        ]

    async def get_event_by_id(self, event_id: str) -> Optional[dict]:
        """Get specific audit event by ID."""
        # Query for the specific event
        from ciris_engine.schemas.services.operations import MemoryQuery

        query = MemoryQuery(
            node_id=event_id,
            scope=GraphScope.LOCAL,
            type=NodeType.AUDIT,
            include_edges=False,
            depth=1
        )

        if self._memory_bus:
            nodes = await self._memory_bus.recall(query)
            if nodes and len(nodes) > 0:
                # Convert node to AuditEntry using proper conversion
                entry = self._tsdb_to_audit_entry(nodes[0])
                if entry:
                    return {
                        "event_id": entry.entry_id,
                        "event_type": entry.event_type,
                        "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                        "user_id": entry.actor,
                        "data": entry.details,
                        "metadata": {"outcome": entry.outcome} if entry.outcome else {}
                    }

        # Also check recent cache
        for entry in self._recent_entries:
            if entry.entry_id == event_id:
                return {
                    "event_id": entry.entry_id,
                    "event_type": entry.event_type,
                    "timestamp": entry.timestamp.isoformat() if entry.timestamp else None,
                    "user_id": entry.actor,
                    "data": entry.details,
                    "metadata": {"outcome": entry.outcome} if entry.outcome else {}
                }

        return None
