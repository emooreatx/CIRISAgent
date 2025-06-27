"""
Tests for adaptive filter service API routes.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.filters import router
from ciris_engine.schemas.api.auth import AuthContext, UserRole
from ciris_engine.schemas.services.filters_core import (
    FilterResult, FilterHealth, FilterStats, FilterPriority,
    FilterTrigger, TriggerType, AdaptiveFilterConfig
)
from ciris_engine.schemas.services.operations import MemoryRecallResult
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_filter_service():
    """Create mock filter service."""
    service = AsyncMock()
    service.get_health = MagicMock(return_value=FilterHealth(
        is_healthy=True,
        warnings=[],
        errors=[],
        stats=FilterStats(
            total_messages_processed=1000,
            total_filtered=100,
            by_priority={
                FilterPriority.CRITICAL: 10,
                FilterPriority.HIGH: 20,
                FilterPriority.MEDIUM: 30,
                FilterPriority.LOW: 40,
                FilterPriority.IGNORE: 0
            },
            by_trigger_type={
                TriggerType.REGEX: 50,
                TriggerType.COUNT: 30,
                TriggerType.LENGTH: 20
            },
            false_positive_reports=5,
            true_positive_confirmations=95
        ),
        config_version=1
    ))
    return service


@pytest.fixture
def mock_memory_service():
    """Create mock memory service."""
    service = AsyncMock()
    return service


@pytest.fixture
def sample_filter_config():
    """Create sample filter configuration."""
    return AdaptiveFilterConfig(
        attention_triggers=[
            FilterTrigger(
                trigger_id="t1",
                name="DM Detection",
                pattern_type=TriggerType.CUSTOM,
                pattern="is_dm",
                priority=FilterPriority.CRITICAL,
                description="Direct messages",
                enabled=True
            )
        ],
        review_triggers=[
            FilterTrigger(
                trigger_id="t2",
                name="Spam Pattern",
                pattern_type=TriggerType.REGEX,
                pattern="buy.*now",
                priority=FilterPriority.HIGH,
                description="Common spam pattern",
                enabled=True
            )
        ],
        llm_filters=[],
        version=1
    )


@pytest.fixture
def auth_headers():
    """Create auth headers for different roles."""
    return {
        "observer": {"Authorization": "Bearer test_observer_key"},
        "admin": {"Authorization": "Bearer test_admin_key"},
        "authority": {"Authorization": "Bearer test_authority_key"}
    }


@pytest.fixture
def mock_auth_service():
    """Create mock auth service that validates test keys."""
    service = AsyncMock()
    
    async def validate_key(key):
        if key == "test_observer_key":
            return MagicMock(user_id="observer_user", role=UserRole.OBSERVER)
        elif key == "test_admin_key":
            return MagicMock(user_id="admin_user", role=UserRole.ADMIN)
        elif key == "test_authority_key":
            return MagicMock(user_id="authority_user", role=UserRole.AUTHORITY)
        return None
    
    service.validate_api_key = validate_key
    service._get_key_id = lambda key: f"key_{key[:10]}"
    return service


def setup_app_state(app, mock_filter_service, mock_auth_service, mock_memory_service=None):
    """Set up app state with mock services."""
    app.state.adaptive_filter_service = mock_filter_service
    app.state.auth_service = mock_auth_service
    if mock_memory_service:
        app.state.memory_service = mock_memory_service


class TestFilterRules:
    """Test GET /v1/filters/rules endpoint."""
    
    def test_get_rules_success(self, client, app, mock_filter_service, mock_auth_service, auth_headers, sample_filter_config):
        """Test successful retrieval of filter rules."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        # Mock filter service get_config
        mock_filter_service.get_config = MagicMock(return_value=sample_filter_config)
        
        response = client.get("/v1/filters/rules", headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert len(data["attention_triggers"]) == 1
        assert len(data["review_triggers"]) == 1
        assert data["total_active"] == 2
        assert data["config_version"] == 1
    
    def test_get_rules_with_disabled(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test retrieval including disabled filters."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        sample_config = AdaptiveFilterConfig(
            attention_triggers=[
                FilterTrigger(
                    trigger_id="t1",
                    name="Active Filter",
                    pattern_type=TriggerType.CUSTOM,
                    pattern="test",
                    priority=FilterPriority.HIGH,
                    description="Active",
                    enabled=True
                ),
                FilterTrigger(
                    trigger_id="t2",
                    name="Disabled Filter",
                    pattern_type=TriggerType.CUSTOM,
                    pattern="test",
                    priority=FilterPriority.HIGH,
                    description="Disabled",
                    enabled=False
                )
            ]
        )
        
        mock_filter_service.get_config = MagicMock(return_value=sample_config)
        
        # Without include_disabled
        response = client.get("/v1/filters/rules", headers=auth_headers["observer"])
        assert response.status_code == 200
        assert len(response.json()["data"]["attention_triggers"]) == 1
        
        # With include_disabled
        response = client.get("/v1/filters/rules?include_disabled=true", headers=auth_headers["observer"])
        assert response.status_code == 200
        assert len(response.json()["data"]["attention_triggers"]) == 2
    
    def test_get_rules_no_auth(self, client, app, mock_filter_service, mock_auth_service):
        """Test unauthorized access."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        response = client.get("/v1/filters/rules")
        assert response.status_code == 401


class TestFilterTest:
    """Test POST /v1/filters/test endpoint."""
    
    def test_filter_test_success(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test successful message filtering."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        mock_filter_service.filter_message.return_value = FilterResult(
            message_id="test_123",
            priority=FilterPriority.HIGH,
            triggered_filters=["spam_detector"],
            should_process=True,
            should_defer=False,
            reasoning="Message contains spam indicators",
            confidence=0.85
        )
        
        request_data = {
            "message": "Buy our product now!",
            "adapter_type": "discord",
            "is_llm_response": False
        }
        
        response = client.post("/v1/filters/test", json=request_data, headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["priority"] == "high"
        assert data["triggered_filters"] == ["spam_detector"]
        assert data["should_process"] is True
        assert data["confidence"] == 0.85
    
    def test_filter_test_with_context(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test filtering with user and channel context."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        mock_filter_service.filter_message.return_value = FilterResult(
            message_id="test_456",
            priority=FilterPriority.CRITICAL,
            triggered_filters=["dm_filter"],
            should_process=True,
            should_defer=False,
            reasoning="Direct message from user",
            confidence=1.0
        )
        
        request_data = {
            "message": "Hello there",
            "adapter_type": "discord",
            "is_llm_response": False,
            "user_id": "user123",
            "channel_id": "dm_channel"
        }
        
        response = client.post("/v1/filters/test", json=request_data, headers=auth_headers["observer"])
        assert response.status_code == 200
        
        # Verify the service was called with proper context
        mock_filter_service.filter_message.assert_called_once()
        call_args = mock_filter_service.filter_message.call_args
        assert call_args[1]["adapter_type"] == "discord"
        assert call_args[1]["is_llm_response"] is False


class TestFilterStats:
    """Test GET /v1/filters/stats endpoint."""
    
    def test_get_stats_success(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test successful stats retrieval."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        response = client.get("/v1/filters/stats", headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["total_messages_processed"] == 1000
        assert data["total_filtered"] == 100
        assert data["filter_rate"] == 10.0  # 100/1000 * 100
        assert data["false_positive_rate"] == 0.05  # 5/100
        assert data["effectiveness_score"] == 0.95  # 95/100
        
        # Check priority breakdown
        assert len(data["by_priority"]) == 5  # All priority levels
        critical_stats = next(p for p in data["by_priority"] if p["priority"] == "critical")
        assert critical_stats["count"] == 10
        assert critical_stats["percentage"] == 10.0  # 10/100 * 100
        
        # Check trigger type breakdown
        assert len(data["by_trigger_type"]) == 6  # All trigger types
        regex_stats = next(t for t in data["by_trigger_type"] if t["trigger_type"] == "regex")
        assert regex_stats["count"] == 50
        assert regex_stats["percentage"] == 50.0  # 50/100 * 100


class TestFilterConfig:
    """Test PUT /v1/filters/config endpoint."""
    
    def test_update_config_add_trigger(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test adding new filter triggers."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        # Mock existing config
        existing_config = AdaptiveFilterConfig(
            attention_triggers=[],
            review_triggers=[],
            llm_filters=[],
            version=1
        )
        
        mock_filter_service.get_config = MagicMock(return_value=existing_config)
        
        new_trigger = {
            "trigger_id": "new_spam",
            "name": "New Spam Pattern",
            "pattern_type": "regex",
            "pattern": "click.*here",
            "priority": "high",
            "description": "New spam detection",
            "enabled": True
        }
        
        request_data = {
            "add_triggers": [new_trigger]
        }
        
        response = client.put("/v1/filters/config", json=request_data, headers=auth_headers["admin"])
        assert response.status_code == 200
        
        # Verify service methods called
        mock_filter_service.add_filter_trigger.assert_called_once()
        
        data = response.json()["data"]
        assert data["version"] == 2  # Version incremented
        assert len(data["review_triggers"]) == 1  # High priority goes to review
    
    def test_update_config_remove_trigger(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test removing filter triggers."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        existing_config = AdaptiveFilterConfig(
            attention_triggers=[
                FilterTrigger(
                    trigger_id="t1",
                    name="To Remove",
                    pattern_type=TriggerType.CUSTOM,
                    pattern="test",
                    priority=FilterPriority.HIGH,
                    description="Will be removed"
                )
            ],
            version=1
        )
        
        mock_filter_service.get_config = MagicMock(return_value=existing_config)
        
        request_data = {
            "remove_trigger_ids": ["t1"]
        }
        
        response = client.put("/v1/filters/config", json=request_data, headers=auth_headers["admin"])
        assert response.status_code == 200
        
        mock_filter_service.remove_filter_trigger.assert_called_once_with("t1")
        
        data = response.json()["data"]
        assert len(data["attention_triggers"]) == 0
    
    def test_update_config_settings(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test updating filter settings."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        existing_config = AdaptiveFilterConfig()
        mock_filter_service.get_config = MagicMock(return_value=existing_config)
        
        request_data = {
            "auto_adjust": False,
            "adjustment_interval": 7200,
            "effectiveness_threshold": 0.2,
            "false_positive_threshold": 0.3
        }
        
        response = client.put("/v1/filters/config", json=request_data, headers=auth_headers["admin"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["auto_adjust"] is False
        assert data["adjustment_interval"] == 7200
        assert data["effectiveness_threshold"] == 0.2
        assert data["false_positive_threshold"] == 0.3
    
    def test_update_config_requires_admin(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test that config update requires admin role."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        request_data = {"auto_adjust": False}
        
        # Try with observer role
        response = client.put("/v1/filters/config", json=request_data, headers=auth_headers["observer"])
        assert response.status_code == 403


class TestFilterEffectiveness:
    """Test GET /v1/filters/effectiveness endpoint."""
    
    def test_get_effectiveness_success(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test successful effectiveness analysis."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        # Create triggers with varying effectiveness
        triggers = [
            FilterTrigger(
                trigger_id=f"t{i}",
                name=f"Trigger {i}",
                pattern_type=TriggerType.REGEX,
                pattern=f"pattern{i}",
                priority=FilterPriority.HIGH,
                description=f"Test trigger {i}",
                effectiveness=0.9 - (i * 0.1),
                false_positive_rate=i * 0.05,
                enabled=True
            )
            for i in range(6)
        ]
        
        config = AdaptiveFilterConfig(
            attention_triggers=triggers[:3],
            review_triggers=triggers[3:],
            false_positive_threshold=0.2
        )
        
        mock_filter_service.get_config = MagicMock(return_value=config)
        
        response = client.get("/v1/filters/effectiveness?top_n=3", headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert 0 <= data["overall_effectiveness"] <= 1
        assert 0 <= data["precision"] <= 1
        assert 0 <= data["recall"] <= 1
        
        # Check top performers (sorted by effectiveness * (1 - false_positive_rate))
        assert len(data["top_performers"]) == 3
        assert data["top_performers"][0]["trigger_id"] == "t0"  # Highest effectiveness, lowest FP
        
        # Check underperformers
        assert len(data["underperformers"]) == 3
        assert data["underperformers"][-1]["trigger_id"] == "t5"  # Lowest effectiveness, highest FP
        
        # Check recommendations
        assert len(data["recommendations"]) > 0
        assert any("high false positive" in r for r in data["recommendations"])
    
    def test_get_effectiveness_no_config(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test effectiveness when no config exists."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        # Mock filter service to raise exception when getting config
        mock_filter_service.get_config = MagicMock(side_effect=Exception("No config"))
        
        response = client.get("/v1/filters/effectiveness", headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["overall_effectiveness"] == 0.5
        assert data["precision"] == 0.0
        assert data["recall"] == 0.0
        assert len(data["top_performers"]) == 0
        assert "No filter configuration found" in data["recommendations"][0]


class TestFilterHealth:
    """Test GET /v1/filters/health endpoint."""
    
    def test_get_health_success(self, client, app, mock_filter_service, mock_auth_service, auth_headers):
        """Test health status retrieval."""
        setup_app_state(app, mock_filter_service, mock_auth_service)
        
        response = client.get("/v1/filters/health", headers=auth_headers["observer"])
        assert response.status_code == 200
        
        data = response.json()["data"]
        assert data["is_healthy"] is True
        assert data["warnings"] == []
        assert data["errors"] == []
        assert data["config_version"] == 1
        assert "stats" in data
    
    def test_service_unavailable(self, client, app, mock_auth_service, auth_headers):
        """Test when filter service is not available."""
        app.state.auth_service = mock_auth_service
        # Don't set filter service
        
        response = client.get("/v1/filters/health", headers=auth_headers["observer"])
        assert response.status_code == 503
        assert "Adaptive filter service not available" in response.json()["detail"]