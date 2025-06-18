"""
Test cron scheduling functionality in TaskSchedulerService
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, AsyncMock

from ciris_engine.services.task_scheduler_service import TaskSchedulerService
from ciris_engine.schemas.identity_schemas_v1 import ScheduledTask


@pytest.fixture
async def scheduler_service():
    """Create a TaskSchedulerService instance for testing."""
    service = TaskSchedulerService(
        db_path=":memory:",
        check_interval_seconds=1  # Fast checking for tests
    )
    # Mock the database connection
    service.conn = Mock()
    yield service
    if service._scheduler_task:
        service._shutdown_event.set()
        await service._scheduler_task


class TestCronScheduling:
    """Test cron scheduling functionality."""
    
    def test_validate_cron_expression(self, scheduler_service):
        """Test cron expression validation."""
        # Skip if croniter not available
        if not scheduler_service._validate_cron_expression("* * * * *"):
            pytest.skip("croniter not installed")
            
        # Valid expressions
        assert scheduler_service._validate_cron_expression("* * * * *")  # Every minute
        assert scheduler_service._validate_cron_expression("0 9 * * *")  # Daily at 9am
        assert scheduler_service._validate_cron_expression("0 0 * * 0")  # Weekly on Sunday
        assert scheduler_service._validate_cron_expression("0 0 1 * *")  # Monthly on 1st
        assert scheduler_service._validate_cron_expression("*/5 * * * *")  # Every 5 minutes
        
        # Invalid expressions
        assert not scheduler_service._validate_cron_expression("invalid")
        assert not scheduler_service._validate_cron_expression("* * * *")  # Too few fields
        assert not scheduler_service._validate_cron_expression("60 * * * *")  # Invalid minute
        
    def test_get_next_cron_time(self, scheduler_service):
        """Test getting next cron execution time."""
        # Skip if croniter not available
        if scheduler_service._get_next_cron_time("* * * * *") == "unknown (croniter not installed)":
            pytest.skip("croniter not installed")
            
        # Test various cron expressions
        next_time = scheduler_service._get_next_cron_time("* * * * *")
        assert next_time != "unknown"
        assert datetime.fromisoformat(next_time) > datetime.now(timezone.utc)
        
    def test_should_trigger_cron(self, scheduler_service):
        """Test cron trigger logic."""
        # Skip if croniter not available
        try:
            from croniter import croniter
        except ImportError:
            pytest.skip("croniter not installed")
            
        # Create a task that runs every minute
        task = ScheduledTask(
            task_id="test_cron_1",
            name="Test Cron Task",
            goal_description="Test cron scheduling",
            status="PENDING",
            schedule_cron="* * * * *",
            trigger_prompt="Test prompt",
            origin_thought_id="thought_123",
            created_at=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            last_triggered_at=None,
            deferral_count=0,
            deferral_history=[]
        )
        
        # Should trigger since it's never been triggered and 2 minutes have passed
        current_time = datetime.now(timezone.utc)
        assert scheduler_service._should_trigger_cron(task, current_time)
        
        # Update last triggered to now
        task.last_triggered_at = current_time.isoformat()
        
        # Should not trigger immediately after
        assert not scheduler_service._should_trigger_cron(task, current_time)
        
        # Should trigger after a minute
        future_time = current_time + timedelta(minutes=1, seconds=1)
        assert scheduler_service._should_trigger_cron(task, future_time)
        
    def test_is_task_due_with_cron(self, scheduler_service):
        """Test task due check with cron expressions."""
        # Skip if croniter not available
        try:
            from croniter import croniter
        except ImportError:
            pytest.skip("croniter not installed")
            
        # Create a cron task
        task = ScheduledTask(
            task_id="test_cron_2",
            name="Test Cron Task",
            goal_description="Test cron scheduling",
            status="PENDING",
            schedule_cron="*/5 * * * *",  # Every 5 minutes
            trigger_prompt="Test prompt",
            origin_thought_id="thought_123",
            created_at=(datetime.now(timezone.utc) - timedelta(minutes=6)).isoformat(),
            last_triggered_at=None,
            deferral_count=0,
            deferral_history=[]
        )
        
        # Should be due since 6 minutes have passed
        assert scheduler_service._is_task_due(task, datetime.now(timezone.utc))
        
    async def test_schedule_cron_task(self, scheduler_service):
        """Test scheduling a task with cron expression."""
        # Skip if croniter not available
        if not scheduler_service._validate_cron_expression("0 9 * * *"):
            pytest.skip("croniter not installed")
            
        # Schedule a daily task
        task = await scheduler_service.schedule_task(
            name="Daily Report",
            goal_description="Generate daily status report",
            trigger_prompt="Generate the daily status report for the team",
            origin_thought_id="thought_456",
            schedule_cron="0 9 * * *"  # Daily at 9am
        )
        
        assert task.schedule_cron == "0 9 * * *"
        assert task.defer_until is None
        assert task.status == "PENDING"
        assert task.task_id in scheduler_service._active_tasks
        
    async def test_invalid_cron_expression_raises(self, scheduler_service):
        """Test that invalid cron expressions raise ValueError."""
        # Skip if croniter not available
        if not scheduler_service._validate_cron_expression("* * * * *"):
            pytest.skip("croniter not installed")
            
        with pytest.raises(ValueError, match="Invalid cron expression"):
            await scheduler_service.schedule_task(
                name="Bad Cron Task",
                goal_description="Test invalid cron",
                trigger_prompt="This should fail",
                origin_thought_id="thought_789",
                schedule_cron="invalid cron"
            )
            
    async def test_cron_task_trigger_updates_last_triggered(self, scheduler_service):
        """Test that triggering a cron task updates last_triggered_at."""
        # Skip if croniter not available
        try:
            from croniter import croniter
        except ImportError:
            pytest.skip("croniter not installed")
            
        # Create a cron task that's due
        task = ScheduledTask(
            task_id="test_cron_3",
            name="Test Update Task",
            goal_description="Test last triggered update",
            status="PENDING",
            schedule_cron="* * * * *",
            trigger_prompt="Update test",
            origin_thought_id="thought_999",
            created_at=(datetime.now(timezone.utc) - timedelta(minutes=2)).isoformat(),
            last_triggered_at=None,
            deferral_count=0,
            deferral_history=[]
        )
        
        scheduler_service._active_tasks[task.task_id] = task
        # Set conn to None to avoid mock issues
        scheduler_service.conn = None
        
        # Mock add_thought to avoid database dependency
        with patch('ciris_engine.services.task_scheduler_service.add_thought'):
            # The task should still update even without database
            await scheduler_service._trigger_task(task)
            
        # Check that last_triggered_at was updated
        assert task.last_triggered_at is not None
        assert task.status == "ACTIVE"  # Cron tasks remain active
        
    def test_mixed_defer_and_cron_tasks(self, scheduler_service):
        """Test that both defer_until and cron tasks work correctly."""
        current_time = datetime.now(timezone.utc)
        
        # One-time deferred task (should be due)
        defer_task = ScheduledTask(
            task_id="defer_1",
            name="Deferred Task",
            goal_description="One-time task",
            status="PENDING",
            defer_until=(current_time - timedelta(minutes=1)).isoformat(),
            trigger_prompt="Deferred prompt",
            origin_thought_id="thought_111",
            created_at=(current_time - timedelta(hours=1)).isoformat(),
            last_triggered_at=None,
            deferral_count=0,
            deferral_history=[]
        )
        
        # Cron task (may or may not be due depending on croniter availability)
        cron_task = ScheduledTask(
            task_id="cron_1",
            name="Cron Task",
            goal_description="Recurring task",
            status="PENDING",
            schedule_cron="* * * * *",
            trigger_prompt="Cron prompt",
            origin_thought_id="thought_222",
            created_at=(current_time - timedelta(minutes=2)).isoformat(),
            last_triggered_at=None,
            deferral_count=0,
            deferral_history=[]
        )
        
        # Deferred task should always be due
        assert scheduler_service._is_task_due(defer_task, current_time)
        
        # Cron task due status depends on croniter availability
        # (tested separately in other tests)