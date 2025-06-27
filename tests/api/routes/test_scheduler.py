"""
Unit tests for scheduler API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi.testclient import TestClient

from ciris_engine.schemas.runtime.extended import ScheduledTaskInfo, ScheduledTask
from ciris_engine.api.routes.scheduler import (
    CreateTaskRequest,
    TaskListResponse,
    TaskDetailResponse,
    ExecutionHistoryResponse,
    ExecutionHistoryItem,
    UpcomingExecutionsResponse
)

# Test fixtures

@pytest.fixture
def mock_scheduler_service():
    """Create mock scheduler service."""
    service = Mock()
    service.get_scheduled_tasks = AsyncMock()
    service.schedule_task = AsyncMock()
    service.cancel_task = AsyncMock()
    return service

@pytest.fixture
def mock_time_service():
    """Create mock time service."""
    service = Mock()
    service.get_current_time = Mock(return_value=datetime.now(timezone.utc))
    return service

@pytest.fixture
def sample_scheduled_task_info():
    """Create sample scheduled task info."""
    now = datetime.now(timezone.utc)
    return ScheduledTaskInfo(
        task_id="task-001",
        name="Daily Report",
        goal_description="Generate daily activity report",
        status="PENDING",
        defer_until=(now + timedelta(hours=1)).isoformat(),
        schedule_cron=None,
        created_at=now.isoformat(),
        last_triggered_at=None,
        deferral_count=0
    )

@pytest.fixture
def sample_recurring_task_info():
    """Create sample recurring task info."""
    now = datetime.now(timezone.utc)
    return ScheduledTaskInfo(
        task_id="task-002",
        name="Hourly Check",
        goal_description="Check system status every hour",
        status="ACTIVE",
        defer_until=None,
        schedule_cron="0 * * * *",
        created_at=(now - timedelta(days=1)).isoformat(),
        last_triggered_at=(now - timedelta(minutes=30)).isoformat(),
        deferral_count=0
    )

@pytest.fixture
def sample_scheduled_task():
    """Create sample scheduled task (full object)."""
    now = datetime.now(timezone.utc)
    return ScheduledTask(
        task_id="task-003",
        name="Test Task",
        goal_description="Test task for unit tests",
        status="PENDING",
        defer_until=(now + timedelta(hours=2)).isoformat(),
        schedule_cron=None,
        trigger_prompt="Execute test task",
        origin_thought_id="thought-001",
        created_at=now.isoformat(),
        last_triggered_at=None,
        deferral_count=0,
        deferral_history=[]
    )

@pytest.fixture
def app_with_scheduler(mock_scheduler_service, mock_time_service, mock_auth_service):
    """Create FastAPI app with scheduler routes."""
    from fastapi import FastAPI
    from ciris_engine.api.routes.scheduler import router
    
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add services to app state
    app.state.task_scheduler_service = mock_scheduler_service
    app.state.time_service = mock_time_service
    app.state.auth_service = mock_auth_service
    
    return app

# Tests

class TestSchedulerEndpoints:
    """Test scheduler API endpoints."""
    
    def test_list_scheduled_tasks_success(self, app_with_scheduler, mock_scheduler_service,
                                         sample_scheduled_task_info, sample_recurring_task_info,
                                         mock_observer_auth):
        """Test successful task listing."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [
            sample_scheduled_task_info,
            sample_recurring_task_info
        ]
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["data"]["tasks"]) == 2
        assert data["data"]["total"] == 2
        assert data["data"]["pending_count"] == 1
        assert data["data"]["active_count"] == 1
        assert data["data"]["completed_count"] == 0
    
    def test_list_scheduled_tasks_with_filter(self, app_with_scheduler, mock_scheduler_service,
                                            sample_scheduled_task_info, sample_recurring_task_info,
                                            mock_observer_auth):
        """Test task listing with status filter."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [
            sample_scheduled_task_info,
            sample_recurring_task_info
        ]
        
        # Make request with filter
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks?status=PENDING",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["tasks"]) == 1
        assert data["data"]["tasks"][0]["status"] == "PENDING"
    
    def test_list_scheduled_tasks_pagination(self, app_with_scheduler, mock_scheduler_service,
                                           sample_scheduled_task_info, mock_observer_auth):
        """Test task listing with pagination."""
        # Setup mock with multiple tasks
        tasks = [sample_scheduled_task_info] * 5
        mock_scheduler_service.get_scheduled_tasks.return_value = tasks
        
        # Make request with pagination
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks?limit=2&offset=1",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["tasks"]) == 2
        assert data["data"]["total"] == 5
    
    def test_list_scheduled_tasks_no_service(self, app_with_scheduler, mock_observer_auth):
        """Test task listing when service unavailable."""
        # Remove service
        app_with_scheduler.state.task_scheduler_service = None
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify error response
        assert response.status_code == 503
        assert "Task scheduler service not available" in response.json()["detail"]
    
    def test_get_task_details_success(self, app_with_scheduler, mock_scheduler_service,
                                     sample_scheduled_task_info, mock_observer_auth):
        """Test getting task details."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [sample_scheduled_task_info]
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks/task-001",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["task"]["task_id"] == "task-001"
        assert data["data"]["task"]["name"] == "Daily Report"
        assert data["data"]["next_execution"] == sample_scheduled_task_info.defer_until
    
    def test_get_task_details_not_found(self, app_with_scheduler, mock_scheduler_service,
                                       mock_observer_auth):
        """Test getting non-existent task details."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = []
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/tasks/nonexistent",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify error response
        assert response.status_code == 404
        assert "Task nonexistent not found" in response.json()["detail"]
    
    def test_create_scheduled_task_success(self, app_with_scheduler, mock_scheduler_service,
                                         sample_scheduled_task, mock_admin_auth):
        """Test creating a scheduled task."""
        # Setup mock
        mock_scheduler_service.schedule_task.return_value = sample_scheduled_task
        
        # Create request body
        request_body = CreateTaskRequest(
            name="Test Task",
            goal_description="Test task for unit tests",
            trigger_prompt="Execute test task",
            origin_thought_id="thought-001",
            defer_until=(datetime.now(timezone.utc) + timedelta(hours=2)).isoformat()
        )
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.post(
                "/v1/scheduler/tasks",
                json=request_body.model_dump(),
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["task_id"] == "task-003"
        assert data["data"]["name"] == "Test Task"
        
        # Verify service was called
        mock_scheduler_service.schedule_task.assert_called_once()
    
    def test_create_scheduled_task_cron(self, app_with_scheduler, mock_scheduler_service,
                                       sample_scheduled_task, mock_admin_auth):
        """Test creating a recurring task with cron schedule."""
        # Modify sample task for cron
        sample_scheduled_task.schedule_cron = "0 * * * *"
        sample_scheduled_task.defer_until = None
        mock_scheduler_service.schedule_task.return_value = sample_scheduled_task
        
        # Create request body
        request_body = CreateTaskRequest(
            name="Hourly Task",
            goal_description="Run every hour",
            trigger_prompt="Execute hourly task",
            origin_thought_id="thought-001",
            schedule_cron="0 * * * *"
        )
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.post(
                "/v1/scheduler/tasks",
                json=request_body.model_dump(),
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["schedule_cron"] == "0 * * * *"
    
    def test_create_scheduled_task_missing_schedule(self, app_with_scheduler, mock_admin_auth):
        """Test creating task without scheduling info."""
        # Create request body without scheduling
        request_body = CreateTaskRequest(
            name="Invalid Task",
            goal_description="No scheduling info",
            trigger_prompt="Execute task",
            origin_thought_id="thought-001"
        )
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.post(
                "/v1/scheduler/tasks",
                json=request_body.model_dump(),
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "Either defer_until or schedule_cron must be provided" in response.json()["detail"]
    
    def test_create_scheduled_task_invalid_cron(self, app_with_scheduler, mock_scheduler_service,
                                               mock_admin_auth):
        """Test creating task with invalid cron expression."""
        # Setup mock to raise ValueError
        mock_scheduler_service.schedule_task.side_effect = ValueError("Invalid cron expression")
        
        # Create request body
        request_body = CreateTaskRequest(
            name="Invalid Cron Task",
            goal_description="Bad cron expression",
            trigger_prompt="Execute task",
            origin_thought_id="thought-001",
            schedule_cron="invalid cron"
        )
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.post(
                "/v1/scheduler/tasks",
                json=request_body.model_dump(),
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify error response
        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]
    
    def test_cancel_scheduled_task_success(self, app_with_scheduler, mock_scheduler_service,
                                         mock_admin_auth):
        """Test cancelling a scheduled task."""
        # Setup mock
        mock_scheduler_service.cancel_task.return_value = True
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.delete(
                "/v1/scheduler/tasks/task-001",
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert data["data"]["task_id"] == "task-001"
        assert data["data"]["status"] == "cancelled"
        
        # Verify service was called
        mock_scheduler_service.cancel_task.assert_called_once_with("task-001")
    
    def test_cancel_scheduled_task_not_found(self, app_with_scheduler, mock_scheduler_service,
                                            mock_admin_auth):
        """Test cancelling non-existent task."""
        # Setup mock
        mock_scheduler_service.cancel_task.return_value = False
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.delete(
                "/v1/scheduler/tasks/nonexistent",
                headers={"Authorization": f"Bearer {mock_admin_auth}"}
            )
        
        # Verify error response
        assert response.status_code == 404
        assert "Task nonexistent not found" in response.json()["detail"]
    
    def test_get_execution_history_success(self, app_with_scheduler, mock_scheduler_service,
                                         sample_recurring_task_info, mock_observer_auth):
        """Test getting execution history."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [sample_recurring_task_info]
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/history?hours=24",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["data"]["history"]) == 1
        assert data["data"]["history"][0]["task_id"] == "task-002"
        assert data["data"]["history"][0]["task_name"] == "Hourly Check"
    
    def test_get_execution_history_filtered(self, app_with_scheduler, mock_scheduler_service,
                                          sample_recurring_task_info, mock_observer_auth):
        """Test getting execution history with task filter."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [sample_recurring_task_info]
        
        # Make request with filter
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/history?hours=24&task_id=task-002",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["history"]) == 1
        
        # Request with different task ID
        response = client.get(
            "/v1/scheduler/history?hours=24&task_id=task-999",
            headers={"Authorization": f"Bearer {mock_observer_auth}"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data["data"]["history"]) == 0
    
    def test_get_upcoming_executions_success(self, app_with_scheduler, mock_scheduler_service,
                                           sample_scheduled_task_info, sample_recurring_task_info,
                                           mock_observer_auth):
        """Test getting upcoming executions."""
        # Setup mock
        mock_scheduler_service.get_scheduled_tasks.return_value = [
            sample_scheduled_task_info,
            sample_recurring_task_info
        ]
        
        # Make request
        with TestClient(app_with_scheduler) as client:
            response = client.get(
                "/v1/scheduler/upcoming?hours=24",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "success"
        assert len(data["data"]["upcoming"]) == 2
        assert data["data"]["within_hours"] == 24
        
        # Check task types
        upcoming_types = [task["type"] for task in data["data"]["upcoming"]]
        assert "one_time" in upcoming_types
        assert "recurring" in upcoming_types
    
    def test_authorization_required(self, app_with_scheduler):
        """Test that endpoints require authorization."""
        with TestClient(app_with_scheduler) as client:
            # Test each endpoint without auth
            endpoints = [
                ("GET", "/v1/scheduler/tasks"),
                ("GET", "/v1/scheduler/tasks/task-001"),
                ("POST", "/v1/scheduler/tasks"),
                ("DELETE", "/v1/scheduler/tasks/task-001"),
                ("GET", "/v1/scheduler/history"),
                ("GET", "/v1/scheduler/upcoming")
            ]
            
            for method, path in endpoints:
                if method == "GET":
                    response = client.get(path)
                elif method == "POST":
                    response = client.post(path, json={})
                elif method == "DELETE":
                    response = client.delete(path)
                
                assert response.status_code == 401
    
    def test_admin_only_endpoints(self, app_with_scheduler, mock_observer_auth):
        """Test that create/delete require admin role."""
        with TestClient(app_with_scheduler) as client:
            # Test create with observer auth (should fail)
            response = client.post(
                "/v1/scheduler/tasks",
                json={
                    "name": "Test",
                    "goal_description": "Test",
                    "trigger_prompt": "Test",
                    "origin_thought_id": "test",
                    "defer_until": datetime.now(timezone.utc).isoformat()
                },
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
            assert response.status_code == 403
            
            # Test delete with observer auth (should fail)
            response = client.delete(
                "/v1/scheduler/tasks/task-001",
                headers={"Authorization": f"Bearer {mock_observer_auth}"}
            )
            assert response.status_code == 403