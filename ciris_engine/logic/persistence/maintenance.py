import logging
from datetime import timedelta
from pathlib import Path
import asyncio
from typing import List, Optional, Any

from ciris_engine.logic.persistence import (
    get_all_tasks,
    update_task_status,
    get_task_by_id,
    get_tasks_by_status,
    delete_tasks_by_ids,
    get_tasks_older_than,
    get_thoughts_by_status,
    get_thoughts_by_task_id,
    delete_thoughts_by_ids,
    update_thought_status,
    get_thoughts_older_than,
)
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

class DatabaseMaintenanceService:
    """
    Service for performing database maintenance tasks like cleanup and archiving.
    """
    def __init__(self, time_service: TimeServiceProtocol, archive_dir_path: str = "data_archive", archive_older_than_hours: int = 24, config_service: Optional[Any] = None) -> None:
        self.time_service = time_service
        self.archive_dir = Path(archive_dir_path)
        self.archive_older_than_hours = archive_older_than_hours
        # No special treatment - "no kings"
        self._maintenance_task: Optional[asyncio.Task] = None
        self._shutdown_event: Optional[asyncio.Event] = None
        self.config_service = config_service

    def _ensure_shutdown_event(self) -> None:
        """Ensure shutdown event is created when needed in async context."""
        if self._shutdown_event is None:
            try:
                self._shutdown_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create shutdown event outside of async context")

    async def start(self) -> None:
        """Start the maintenance service with periodic tasks."""
        self._ensure_shutdown_event()
        self._maintenance_task = asyncio.create_task(self._maintenance_loop())

    async def stop(self) -> None:
        """Properly stop the maintenance service."""
        if self._shutdown_event:
            self._shutdown_event.set()
        if self._maintenance_task:
            try:
                await asyncio.wait_for(self._maintenance_task, timeout=5.0)
            except asyncio.TimeoutError:
                logger.warning("Maintenance task did not finish in time")
                self._maintenance_task.cancel()
        await self._final_cleanup()

    async def _maintenance_loop(self) -> None:
        """Periodic maintenance loop."""
        while not (self._shutdown_event and self._shutdown_event.is_set()):
            try:
                if self._shutdown_event:
                    await asyncio.wait_for(
                        self._shutdown_event.wait(),
                        timeout=3600  # Run every hour
                    )
                else:
                    await asyncio.sleep(3600)  # Run every hour
            except asyncio.TimeoutError:
                await self._perform_periodic_maintenance()

    async def _perform_periodic_maintenance(self) -> None:
        """Run periodic maintenance tasks."""
        logger.info("Periodic maintenance tasks executed.")

    async def _final_cleanup(self) -> None:
        """Final cleanup before shutdown."""
        logger.info("Final maintenance cleanup executed.")

    async def perform_startup_cleanup(self, time_service: Optional[TimeServiceProtocol] = None) -> None:
        """
        Performs database cleanup at startup:
        1. Removes orphaned active tasks and thoughts.
        2. Archives tasks and thoughts older than the configured threshold.
        3. Cleans up thoughts with invalid context.
        Logs actions taken.
        """
        # Use provided time_service or fallback to instance time_service
        ts = time_service or self.time_service
        logger.info("Starting database cleanup")
        self.archive_dir.mkdir(parents=True, exist_ok=True)

        # --- Clean up thoughts with invalid/malformed context ---
        await self._cleanup_invalid_thoughts()
        
        # --- Clean up runtime-specific configuration from previous runs ---
        await self._cleanup_runtime_config()

        # Skip WAKEUP cleanup - "no kings" principle

        # --- 1. Remove orphaned active tasks and thoughts ---
        orphaned_tasks_deleted_count = 0
        orphaned_thoughts_deleted_count = 0

        active_tasks = get_tasks_by_status(TaskStatus.ACTIVE)
        task_ids_to_delete: List[Any] = []

        for task in active_tasks:
            if not hasattr(task, 'task_id'):
                logger.error(f"Item in active_tasks is not a Task object, it's a {type(task)}: {task}")
                continue # Skip this item

            is_orphan = False
            if task.task_id.startswith("shutdown_") and task.parent_task_id is None:
                pass # Shutdown tasks are valid root tasks
            elif task.parent_task_id:
                parent_task = get_task_by_id(task.parent_task_id)
                if not parent_task or parent_task.status not in [TaskStatus.ACTIVE, TaskStatus.COMPLETED]:
                    is_orphan = True
            elif task.parent_task_id is None:
                # Root tasks without parents are allowed
                pass

            if is_orphan:
                logger.info(f"Orphaned active task found: {task.task_id} ('{task.description}'). Parent missing or not active/completed. Marking for deletion.")
                task_ids_to_delete.append(task.task_id)

        if task_ids_to_delete:
            orphaned_tasks_deleted_count = delete_tasks_by_ids(task_ids_to_delete)
            logger.info(f"Deleted {orphaned_tasks_deleted_count} orphaned active tasks (and their thoughts via cascade).")

        pending_thoughts = get_thoughts_by_status(ThoughtStatus.PENDING)
        processing_thoughts = get_thoughts_by_status(ThoughtStatus.PROCESSING)
        all_potentially_orphaned_thoughts = pending_thoughts + processing_thoughts
        thought_ids_to_delete_orphan: List[Any] = []

        for thought in all_potentially_orphaned_thoughts:
            source_task = get_task_by_id(thought.source_task_id)
            if not source_task or source_task.status != TaskStatus.ACTIVE:
                logger.info(f"Orphaned thought found: {thought.thought_id} (Task: {thought.source_task_id} not found or not active). Marking for deletion.")
                thought_ids_to_delete_orphan.append(thought.thought_id)

        if thought_ids_to_delete_orphan:
            unique_thought_ids_to_delete = list(set(thought_ids_to_delete_orphan))
            count = delete_thoughts_by_ids(unique_thought_ids_to_delete)
            orphaned_thoughts_deleted_count += count
            logger.info(f"Deleted {count} additional orphaned active/processing thoughts.")

        logger.info(f"Orphan cleanup: {orphaned_tasks_deleted_count} tasks, {orphaned_thoughts_deleted_count} thoughts removed.")

        # --- 2. Archive thoughts older than configured hours ---
        # Tasks are now managed by TSDB consolidator, not archived here
        archived_tasks_count = 0
        archived_thoughts_count = 0

        now = ts.now()
        archive_timestamp_str = now.strftime("%Y%m%d_%H%M%S")
        older_than_timestamp = (now - timedelta(hours=self.archive_older_than_hours)).isoformat()

        # Skip task archival - handled by TSDB consolidator
        logger.info("Task archival skipped - tasks are now managed by TSDB consolidator")
        task_ids_actually_archived_and_deleted: set[str] = set()

        thoughts_to_archive = get_thoughts_older_than(older_than_timestamp)
        if thoughts_to_archive:
            thought_archive_file = self.archive_dir / f"archive_thoughts_{archive_timestamp_str}.jsonl"
            thought_ids_to_delete_for_archive: List[Any] = []

            with open(thought_archive_file, "w") as f:
                for thought in thoughts_to_archive:
                    # Archive all thoughts older than threshold
                    f.write(thought.model_dump_json() + "\n")
                    thought_ids_to_delete_for_archive.append(thought.thought_id)

            if thought_ids_to_delete_for_archive:
                archived_thoughts_count = delete_thoughts_by_ids(thought_ids_to_delete_for_archive)
                logger.info(f"Archived and deleted {archived_thoughts_count} thoughts older than {self.archive_older_than_hours} hours to {thought_archive_file}.")
            else:
                logger.info(f"No thoughts older than {self.archive_older_than_hours} hours to archive.")
        else:
            logger.info(f"No thoughts older than {self.archive_older_than_hours} hours found for archiving.")

        logger.info(f"Archival: {archived_tasks_count} tasks, {archived_thoughts_count} thoughts archived and removed.")
        logger.info("Database cleanup completed")

    async def _cleanup_invalid_thoughts(self) -> None:
        """Clean up thoughts with invalid or malformed context."""
        from ciris_engine.logic.persistence import get_db_connection

        logger.info("Cleaning up thoughts with invalid context...")

        # Get all thoughts with empty or invalid context
        sql = """
            SELECT thought_id, context_json
            FROM thoughts
            WHERE context_json = '{}'
               OR context_json IS NULL
               OR context_json NOT LIKE '%task_id%'
               OR context_json NOT LIKE '%correlation_id%'
        """

        invalid_thought_ids = []

        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                cursor.execute(sql)
                rows = cursor.fetchall()

                for row in rows:
                    invalid_thought_ids.append(row["thought_id"])

                if invalid_thought_ids:
                    # Delete these invalid thoughts
                    placeholders = ",".join("?" * len(invalid_thought_ids))
                    delete_sql = f"DELETE FROM thoughts WHERE thought_id IN ({placeholders})"
                    cursor.execute(delete_sql, invalid_thought_ids)
                    conn.commit()

                    logger.info(f"Deleted {len(invalid_thought_ids)} thoughts with invalid context")
                else:
                    logger.info("No thoughts with invalid context found")

        except Exception as e:
            logger.error(f"Failed to clean up invalid thoughts: {e}", exc_info=True)
    
    async def _cleanup_runtime_config(self) -> None:
        """Clean up runtime-specific configuration from previous runs."""
        try:
            # Use injected config service
            if not self.config_service:
                logger.warning("Cannot clean up runtime config - config service not available")
                return
            
            # Get all config entries
            all_configs = await self.config_service.list_configs()
            
            runtime_config_patterns = [
                "adapter.",  # Adapter configurations
                "runtime.",  # Runtime-specific settings
                "session.",  # Session-specific data
                "temp.",     # Temporary configurations
            ]
            
            deleted_count = 0
            
            for key, value in all_configs.items():
                # Check if this is a runtime-specific config
                is_runtime_config = any(key.startswith(pattern) for pattern in runtime_config_patterns)
                
                if is_runtime_config:
                    # Get the actual config node to check if it should be deleted
                    config_node = await self.config_service.get_config(key)
                    if config_node:
                        # Skip configs created by system_bootstrap (essential configs)
                        if config_node.updated_by == "system_bootstrap":
                            logger.debug(f"Preserving bootstrap config: {key}")
                            continue
                            
                        # Convert to GraphNode and use memory service to forget it
                        graph_node = config_node.to_graph_node()
                        await self.config_service.graph.forget(graph_node)
                        deleted_count += 1
                        logger.debug(f"Deleted runtime config node: {key}")
            
            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} runtime-specific configuration entries from previous runs")
            else:
                logger.info("No runtime-specific configuration entries to clean up")
                
        except Exception as e:
            logger.error(f"Failed to clean up runtime config: {e}", exc_info=True)
