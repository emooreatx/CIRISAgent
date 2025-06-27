"""
Unit tests for visibility API routes.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi import WebSocket
from fastapi.testclient import TestClient
import json

from ciris_engine.schemas.services.visibility import (
    VisibilitySnapshot,
    ReasoningTrace,
    TaskDecisionHistory,
    ThoughtStep,
    DecisionRecord
)
from ciris_engine.schemas.runtime.models import Task, Thought, FinalAction
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtType, ThoughtStatus
from ciris_engine.schemas.handlers.schemas import HandlerResult

# Test fixtures

@pytest.fixture
def mock_visibility_service():
    """Create mock visibility service."""
    service = Mock()
    service.get_current_state = AsyncMock()
    service.get_reasoning_trace = AsyncMock()
    service.get_decision_history = AsyncMock()
    service.explain_action = AsyncMock()
    return service

@pytest.fixture
def sample_task():
    """Create sample task."""
    now = datetime.now(timezone.utc)
    return Task(
        task_id="task-123",
        channel_id="test-channel",
        description="Test task",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        status=TaskStatus.ACTIVE
    )

@pytest.fixture
def sample_thought():
    """Create sample thought."""
    now = datetime.now(timezone.utc)
    return Thought(
        thought_id="thought-456",
        source_task_id="task-123",
        channel_id="test-channel",
        content="Analyzing the request",
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.COMPLETED,
        final_action=FinalAction(
            action_type="MEMORIZE",
            action_params={"key": "test", "value": "data"},
            confidence=0.95,
            reasoning="Need to store this information for future reference"
        )
    )

@pytest.fixture
def sample_snapshot(sample_task, sample_thought):
    """Create sample visibility snapshot."""
    return VisibilitySnapshot(
        current_task=sample_task,
        active_thoughts=[sample_thought],
        recent_decisions=[sample_thought],
        reasoning_depth=3
    )

@pytest.fixture
def app_with_visibility(mock_visibility_service, mock_auth_service):
    """Create FastAPI app with visibility routes."""
    from fastapi import FastAPI
    from ciris_engine.api.routes.visibility import router
    
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add services to app state
    app.state.visibility_service = mock_visibility_service
    app.state.auth_service = mock_auth_service
    
    # Add mock runtime for cognitive state
    mock_runtime = Mock()
    mock_runtime.cognitive_state = Mock(value="WORK")
    app.state.runtime = mock_runtime
    
    return app

# Tests

class TestVisibilityEndpoints:
    """Test visibility API endpoints."""
    
    def test_get_reasoning_trace(self, app_with_visibility, observer_headers, mock_visibility_service, sample_snapshot):
        """Test GET /v1/visibility/reasoning endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = sample_snapshot
        mock_visibility_service.get_reasoning_trace.return_value = ReasoningTrace(
            task=sample_snapshot.current_task,
            thought_steps=[
                ThoughtStep(
                    thought=sample_snapshot.active_thoughts[0],
                    handler_result=HandlerResult(success=True, message="Success")
                )
            ],
            total_thoughts=1,
            actions_taken=["MEMORIZE"],
            processing_time_ms=150.0
        )
        
        # Make request
        response = client.get(
            "/v1/visibility/reasoning",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["current_task_id"] == "task-123"
        assert data["reasoning_depth"] == 3
        assert data["reasoning_trace"] is not None
        assert len(data["reasoning_trace"]["thought_steps"]) == 1
    
    def test_get_reasoning_trace_specific_task(self, app_with_visibility, observer_headers, mock_visibility_service):
        """Test GET /v1/visibility/reasoning with specific task ID."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = VisibilitySnapshot()
        mock_visibility_service.get_reasoning_trace.return_value = ReasoningTrace(
            task=Task(
                task_id="specific-task",
                channel_id="test-channel",
                description="Specific",
                created_at=datetime.now(timezone.utc).isoformat(),
                updated_at=datetime.now(timezone.utc).isoformat(),
                status=TaskStatus.COMPLETED
            ),
            total_thoughts=5,
            actions_taken=["SPEAK", "MEMORIZE"]
        )
        
        # Make request
        response = client.get(
            "/v1/visibility/reasoning?task_id=specific-task",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["reasoning_trace"]["task"]["task_id"] == "specific-task"
        assert data["reasoning_trace"]["total_thoughts"] == 5
    
    def test_get_recent_thoughts(self, app_with_visibility, observer_headers, mock_visibility_service, sample_snapshot):
        """Test GET /v1/visibility/thoughts endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = sample_snapshot
        
        # Make request
        response = client.get(
            "/v1/visibility/thoughts?limit=5",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["thoughts"]) == 2  # sample_thought appears in both active and recent
        assert data["total"] == 2
        assert data["has_more"] is False
        assert data["thoughts"][0]["thought_id"] == "thought-456"
    
    def test_get_thoughts_pagination(self, app_with_visibility, observer_headers, mock_visibility_service):
        """Test GET /v1/visibility/thoughts with pagination."""
        client = TestClient(app_with_visibility)
        
        # Create multiple thoughts
        now = datetime.now(timezone.utc)
        thoughts = [
            Thought(
                thought_id=f"thought-{i}",
                source_task_id="task-123",
                channel_id="test-channel",
                content=f"Thought {i}",
                created_at=(now - timedelta(minutes=i)).isoformat(),
                updated_at=(now - timedelta(minutes=i)).isoformat(),
                thought_type=ThoughtType.STANDARD,
                status=ThoughtStatus.COMPLETED
            )
            for i in range(20)
        ]
        
        # Setup mock
        snapshot = VisibilitySnapshot(active_thoughts=thoughts[:10], recent_decisions=thoughts[10:])
        mock_visibility_service.get_current_state.return_value = snapshot
        
        # Make request with offset
        response = client.get(
            "/v1/visibility/thoughts?limit=5&offset=5",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["thoughts"]) == 5
        assert data["total"] == 20
        assert data["has_more"] is True
    
    def test_get_decision_history(self, app_with_visibility, observer_headers, mock_visibility_service, sample_thought):
        """Test GET /v1/visibility/decisions endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        decision = DecisionRecord(
            decision_id="dec-001",
            timestamp=datetime.now(timezone.utc),
            thought_id="thought-456",
            action_type="MEMORIZE",
            parameters={"key": "test"},
            rationale="Need to store this data",
            executed=True,
            success=True
        )
        
        history = TaskDecisionHistory(
            task_id="task-123",
            task_description="Test task",
            created_at=datetime.now(timezone.utc),
            decisions=[decision],
            total_decisions=1,
            successful_decisions=1,
            final_status="completed"
        )
        
        mock_visibility_service.get_current_state.return_value = VisibilitySnapshot(recent_decisions=[sample_thought])
        mock_visibility_service.get_decision_history.return_value = history
        
        # Make request
        response = client.get(
            "/v1/visibility/decisions?task_id=task-123",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["decisions"]) == 1
        assert data["decisions"][0]["action_type"] == "MEMORIZE"
        assert data["by_task"]["task-123"] == 1
    
    def test_get_cognitive_state(self, app_with_visibility, observer_headers, mock_visibility_service, sample_snapshot):
        """Test GET /v1/visibility/state endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = sample_snapshot
        
        # Make request (runtime already mocked in app_with_visibility)
        response = client.get(
            "/v1/visibility/state",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["cognitive_state"] == "WORK"
        assert data["snapshot"]["reasoning_depth"] == 3
        assert data["state_duration_seconds"] == 0.0
    
    def test_get_action_explanations(self, app_with_visibility, observer_headers, mock_visibility_service, sample_thought):
        """Test GET /v1/visibility/explanations endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock for specific action
        mock_visibility_service.explain_action.return_value = "I performed this action to store the user's request data"
        mock_visibility_service.get_current_state.return_value = VisibilitySnapshot(recent_decisions=[sample_thought])
        
        # Test specific action explanation
        response = client.get(
            "/v1/visibility/explanations?action_id=action-789",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["explanations"]) == 1
        assert data["explanations"][0]["action_id"] == "action-789"
        assert "performed this action" in data["explanations"][0]["explanation"]
    
    def test_get_recent_explanations(self, app_with_visibility, observer_headers, mock_visibility_service, sample_thought):
        """Test GET /v1/visibility/explanations without action_id."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = VisibilitySnapshot(recent_decisions=[sample_thought])
        
        # Make request
        response = client.get(
            "/v1/visibility/explanations",
            headers=observer_headers
        )
        
        # Verify response
        assert response.status_code == 200
        data = response.json()["data"]
        assert len(data["explanations"]) == 1
        assert data["explanations"][0]["action_type"] == "MEMORIZE"
        assert data["explanations"][0]["explanation"] == "Analyzing the request"
    
    def test_service_unavailable(self, app_with_visibility, observer_headers):
        """Test when visibility service is not available."""
        client = TestClient(app_with_visibility)
        
        # Remove service
        del app_with_visibility.state.visibility_service
        
        # Make request
        response = client.get(
            "/v1/visibility/reasoning",
            headers=observer_headers
        )
        
        # Verify error response
        assert response.status_code == 503
        assert "Visibility service not available" in response.json()["detail"]
    
    def test_websocket_stream(self, app_with_visibility, mock_visibility_service, sample_snapshot):
        """Test WebSocket /v1/visibility/stream endpoint."""
        client = TestClient(app_with_visibility)
        
        # Setup mock
        mock_visibility_service.get_current_state.return_value = sample_snapshot
        
        with client.websocket_connect("/v1/visibility/stream?token=test-token") as websocket:
            # Receive initial state
            data = websocket.receive_json()
            assert data["type"] == "state"
            assert data["data"]["reasoning_depth"] == 3
            assert data["data"]["current_task"] == "task-123"
            
            # Send ping
            websocket.send_json({"type": "ping"})
            
            # Should receive updates (in real implementation)
            # For tests, we'd need to mock the continuous updates
    
    def test_websocket_no_auth(self, app_with_visibility):
        """Test WebSocket without authentication."""
        client = TestClient(app_with_visibility)
        
        with client.websocket_connect("/v1/visibility/stream") as websocket:
            data = websocket.receive_json()
            assert data["type"] == "error"
            assert "Authentication required" in data["data"]["message"]
    
    def test_error_handling(self, app_with_visibility, observer_headers, mock_visibility_service):
        """Test error handling in routes."""
        client = TestClient(app_with_visibility)
        
        # Setup mock to raise exception
        mock_visibility_service.get_current_state.side_effect = Exception("Service error")
        
        # Make request
        response = client.get(
            "/v1/visibility/reasoning",
            headers=observer_headers
        )
        
        # Verify error response
        assert response.status_code == 500
        assert "Service error" in response.json()["detail"]