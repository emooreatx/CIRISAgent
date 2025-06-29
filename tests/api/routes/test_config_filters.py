"""
Tests for filter configuration through config API.

Demonstrates how adaptive filter settings are managed as config keys.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.config import router
from ciris_engine.schemas.api.auth import AuthContext, UserRole


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
def mock_config_service():
    """Create mock config service."""
    service = AsyncMock()

    # Mock filter configuration as config keys
    filter_config = {
        # Filter settings
        "filter.enabled": True,
        "filter.auto_adjust": True,
        "filter.adjustment_interval": 3600,
        "filter.effectiveness_threshold": 0.1,
        "filter.false_positive_threshold": 0.2,

        # Filter rules (stored as JSON strings in config)
        "filter.rules.attention.dm_detection": {
            "trigger_id": "dm_detect",
            "name": "DM Detection",
            "pattern_type": "custom",
            "pattern": "is_dm",
            "priority": "critical",
            "description": "Direct messages",
            "enabled": True
        },
        "filter.rules.review.spam_pattern": {
            "trigger_id": "spam_001",
            "name": "Spam Pattern",
            "pattern_type": "regex",
            "pattern": "buy.*now",
            "priority": "high",
            "description": "Common spam pattern",
            "enabled": True
        },

        # Filter statistics (read-only)
        "filter.stats.total_messages": 1000,
        "filter.stats.total_filtered": 100,
        "filter.stats.false_positives": 5,
        "filter.stats.true_positives": 95,
    }

    async def get_all_configs():
        return filter_config

    async def get_config(key=None):
        if key is None:
            return filter_config
        return filter_config.get(key)

    async def set_config(key, value, updated_by="test"):
        filter_config[key] = value

    service.get_all_configs = get_all_configs
    service.get_config = get_config
    service.set_config = set_config

    return service


@pytest.fixture
def auth_headers():
    """Create auth headers for different roles."""
    return {
        "observer": {"Authorization": "Bearer test_observer_key"},
        "admin": {"Authorization": "Bearer test_admin_key"},
        "root": {"Authorization": "Bearer test_root_key"}
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
        elif key == "test_root_key":
            return MagicMock(user_id="root_user", role=UserRole.ROOT)
        return None

    service.validate_api_key = validate_key
    service._get_key_id = lambda key: f"key_{key[:10]}"
    return service


def setup_app_state(app, mock_config_service, mock_auth_service):
    """Set up app state with mock services."""
    app.state.config_service = mock_config_service
    app.state.auth_service = mock_auth_service


class TestFilterConfigRetrieval:
    """Test retrieving filter configuration through config API."""

    def test_list_filter_configs(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test listing all filter configurations."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        # Get all filter configs
        response = client.get("/v1/config?prefix=filter.", headers=auth_headers["observer"])
        assert response.status_code == 200

        data = response.json()["data"]
        configs = data["configs"]

        # Check filter settings are present
        filter_enabled = next(c for c in configs if c["key"] == "filter.enabled")
        assert filter_enabled["value"] is True

        # Check filter rules are present
        dm_rule = next(c for c in configs if c["key"] == "filter.rules.attention.dm_detection")
        assert dm_rule["value"]["trigger_id"] == "dm_detect"
        assert dm_rule["value"]["priority"] == "critical"

        # Check stats are present
        total_messages = next(c for c in configs if c["key"] == "filter.stats.total_messages")
        assert total_messages["value"] == 1000

    def test_get_specific_filter_rule(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test getting a specific filter rule."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        response = client.get(
            "/v1/config/filter.rules.review.spam_pattern",
            headers=auth_headers["observer"]
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["key"] == "filter.rules.review.spam_pattern"
        assert data["value"]["pattern"] == "buy.*now"
        assert data["value"]["priority"] == "high"


class TestFilterConfigUpdate:
    """Test updating filter configuration through config API."""

    def test_update_filter_settings(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test updating filter settings."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        # Update auto-adjust setting
        response = client.put(
            "/v1/config/filter.auto_adjust",
            json={"value": False, "reason": "Disabling auto-adjustment for manual tuning"},
            headers=auth_headers["admin"]
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["value"] is False
        assert data["updated_by"] == "admin_user"

    def test_add_filter_rule(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test adding a new filter rule."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        new_rule = {
            "trigger_id": "link_spam",
            "name": "Link Spam",
            "pattern_type": "regex",
            "pattern": "http.*bit\\.ly",
            "priority": "medium",
            "description": "Suspicious shortened URLs",
            "enabled": True
        }

        response = client.put(
            "/v1/config/filter.rules.review.link_spam",
            json={"value": new_rule, "reason": "Adding new spam detection rule"},
            headers=auth_headers["admin"]
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["value"]["trigger_id"] == "link_spam"

    def test_disable_filter_rule(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test disabling a filter rule by updating its enabled status."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        # First get the existing rule
        response = client.get(
            "/v1/config/filter.rules.attention.dm_detection",
            headers=auth_headers["admin"]
        )
        rule = response.json()["data"]["value"]

        # Update enabled status
        rule["enabled"] = False

        response = client.put(
            "/v1/config/filter.rules.attention.dm_detection",
            json={"value": rule, "reason": "Temporarily disabling DM detection"},
            headers=auth_headers["admin"]
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["value"]["enabled"] is False

    def test_remove_filter_rule(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test removing a filter rule."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        response = client.delete(
            "/v1/config/filter.rules.review.spam_pattern",
            headers=auth_headers["admin"]
        )
        assert response.status_code == 200

        data = response.json()["data"]
        assert data["status"] == "deleted"
        assert data["key"] == "filter.rules.review.spam_pattern"

    def test_update_filter_requires_admin(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test that filter updates require admin permissions."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        # Try with observer role
        response = client.put(
            "/v1/config/filter.enabled",
            json={"value": False},
            headers=auth_headers["observer"]
        )
        assert response.status_code == 403
        assert "Insufficient permissions" in response.json()["detail"]


class TestFilterStats:
    """Test reading filter statistics through config API."""

    def test_read_filter_stats(self, client, app, mock_config_service, mock_auth_service, auth_headers):
        """Test reading filter statistics as config values."""
        setup_app_state(app, mock_config_service, mock_auth_service)

        # Get all stats
        response = client.get("/v1/config?prefix=filter.stats.", headers=auth_headers["observer"])
        assert response.status_code == 200

        data = response.json()["data"]
        configs = data["configs"]

        # Check stats values
        stats_by_key = {c["key"]: c["value"] for c in configs}

        assert stats_by_key["filter.stats.total_messages"] == 1000
        assert stats_by_key["filter.stats.total_filtered"] == 100
        assert stats_by_key["filter.stats.false_positives"] == 5
        assert stats_by_key["filter.stats.true_positives"] == 95

        # Calculate effectiveness
        filter_rate = 100 / 1000 * 100  # 10%
        effectiveness = 95 / (95 + 5)  # 95%

        assert filter_rate == 10.0
        assert effectiveness == 0.95


# Example usage documentation
"""
Filter Configuration Key Structure:

1. Settings (prefix: filter.)
   - filter.enabled: bool - Master enable/disable
   - filter.auto_adjust: bool - Enable adaptive learning
   - filter.adjustment_interval: int - Seconds between adjustments
   - filter.effectiveness_threshold: float - Minimum effectiveness (0-1)
   - filter.false_positive_threshold: float - Maximum false positive rate (0-1)

2. Rules (prefix: filter.rules.)
   - filter.rules.attention.<name>: dict - Critical priority triggers
   - filter.rules.review.<name>: dict - High/medium priority triggers
   - filter.rules.llm.<name>: dict - LLM output filters

   Rule structure:
   {
       "trigger_id": "unique_id",
       "name": "Display Name",
       "pattern_type": "regex|custom|semantic|count|length|rate",
       "pattern": "pattern_string",
       "priority": "critical|high|medium|low",
       "description": "What this detects",
       "enabled": true/false,
       "effectiveness": 0.9,  # Optional, tracked by system
       "false_positive_rate": 0.1  # Optional, tracked by system
   }

3. Statistics (prefix: filter.stats.) - Read-only
   - filter.stats.total_messages: int
   - filter.stats.total_filtered: int
   - filter.stats.false_positives: int
   - filter.stats.true_positives: int
   - filter.stats.by_priority.<priority>: int
   - filter.stats.by_trigger.<trigger_id>: dict

Example API Usage:

# List all filter rules
GET /v1/config?prefix=filter.rules.

# Get specific rule
GET /v1/config/filter.rules.attention.dm_detection

# Add new rule
PUT /v1/config/filter.rules.review.new_spam
{
    "value": {
        "trigger_id": "new_spam",
        "name": "New Spam Pattern",
        "pattern_type": "regex",
        "pattern": "click.*here.*now",
        "priority": "high",
        "description": "Urgent spam pattern",
        "enabled": true
    },
    "reason": "Adding new spam detection"
}

# Update setting
PUT /v1/config/filter.auto_adjust
{
    "value": false,
    "reason": "Disabling for manual tuning"
}

# Delete rule
DELETE /v1/config/filter.rules.review.obsolete_rule
"""
