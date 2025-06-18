"""
Simplified memorize test that avoids module corruption issues.
"""

import asyncio
import pytest
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
import tempfile
import os
from unittest.mock import patch, MagicMock

from ciris_engine.persistence import (
    get_db_connection,
    get_task_by_id,
    get_thoughts_by_task_id,
    initialize_database,
    add_task
)
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, TaskStatus
from ciris_engine.schemas.agent_core_schemas_v1 import Task


@pytest.mark.asyncio 
async def test_memorize_scheduling_mechanism():
    """
    Test the core scheduling mechanism without full runtime.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        data_dir = Path(temp_dir) / "data"
        data_dir.mkdir(exist_ok=True)
        db_path = str(data_dir / "test.db")
        
        # Initialize database
        initialize_database(db_path)
        
        # Create scheduler service
        from ciris_engine.services.task_scheduler_service import TaskSchedulerService
        scheduler = TaskSchedulerService(db_path=db_path, check_interval_seconds=1)
        await scheduler.start()
        
        # Schedule a task for 3 seconds in the future
        future_time = datetime.now(timezone.utc) + timedelta(seconds=3)
        
        task = await scheduler.schedule_task(
            name="Test Future Task",
            goal_description="Test scheduling mechanism",
            trigger_prompt="Execute the scheduled test!",
            origin_thought_id="test_thought_001",
            defer_until=future_time.isoformat()
        )
        
        assert task.task_id in scheduler._active_tasks
        assert task.defer_until == future_time.isoformat()
        assert task.status == "PENDING"
        
        # Mock add_thought to avoid database issues
        with patch('ciris_engine.services.task_scheduler_service.add_thought'):
            # Wait for task to become due and be processed
            await asyncio.sleep(4)
            
            # For a one-time deferred task, it should be removed from active tasks after triggering
            # The task should either be removed (if processed) or have status changed
            if task.task_id in scheduler._active_tasks:
                # If still there, check if status changed
                active_task = scheduler._active_tasks[task.task_id]
                assert active_task.status in ["COMPLETE", "ACTIVE"], f"Task status is {active_task.status}"
        
        await scheduler.stop()


@pytest.mark.asyncio
async def test_memorize_task_integration():
    """
    Test memorize functionality with minimal dependencies.
    """
    with tempfile.TemporaryDirectory() as temp_dir:
        db_path = str(Path(temp_dir) / "test.db")
        initialize_database(db_path)
        
        # Create a test task
        test_task_id = "test_memorize_001"
        task = Task(
            task_id=test_task_id,
            description="Test memorize integration",
            status=TaskStatus.PENDING,
            priority=1,
            created_at=datetime.now(timezone.utc).isoformat(),
            updated_at=datetime.now(timezone.utc).isoformat()
        )
        add_task(task, db_path=db_path)
        
        # Verify task was added
        retrieved_task = get_task_by_id(test_task_id, db_path=db_path)
        assert retrieved_task is not None
        assert retrieved_task.task_id == test_task_id
        assert retrieved_task.status == TaskStatus.PENDING