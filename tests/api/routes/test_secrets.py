"""
Tests for Secrets Service API endpoints.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.secrets import router
from ciris_engine.schemas.services.core.secrets import (
    SecretsServiceStats,
    SecretFilterStatus,
    SecretAccessLog,
    SecretContext,
)
from ciris_engine.schemas.secrets.service import (
    FilterUpdateRequest,
    FilterUpdateResult,
    PatternConfig,
    FilterStats,
)
from ciris_engine.schemas.secrets.core import SecretReference
from ciris_engine.schemas.runtime.enums import SensitivityLevel
from ciris_engine.schemas.api.auth import UserRole


@pytest.fixture
def mock_secrets_service():
    """Create mock secrets service."""
    service = Mock()
    
    # Setup async methods
    service.get_service_stats = AsyncMock()
    service.is_healthy = AsyncMock()
    service.get_filter_config = AsyncMock()
    service.update_filter_config = AsyncMock()
    service.process_incoming_text = AsyncMock()
    
    # Mock get_service_stats
    service.get_service_stats.return_value = SecretsServiceStats(
            total_secrets=42,
            active_filters=5,
            filter_matches_today=123,
            last_filter_update=datetime.now(timezone.utc),
        encryption_enabled=True
    )
    
    # Mock is_healthy
    service.is_healthy.return_value = True
    
    # Mock get_filter_config
    service.get_filter_config.return_value = {
            'patterns': [
                {
                    'name': 'api_key',
                    'pattern': r'api[_-]?key.*',
                    'enabled': True,
                    'sensitivity': 'HIGH'
                },
                {
                    'name': 'bearer_token',
                    'pattern': r'bearer\s+.*',
                    'enabled': True,
                    'sensitivity': 'HIGH'
                }
            ],
            'sensitivity_config': {
                'HIGH': {
                    'enabled': True,
                    'redaction_enabled': True,
                    'audit_enabled': True
                }
            }
        }
    
    # Mock update_filter_config
    service.update_filter_config.return_value = FilterUpdateResult(
            success=True,
            error=None,
            results=[],
            accessor='test_user',
        stats=FilterStats(patterns_updated=1, sensitivity_levels_updated=0)
    )
    
    # Mock process_incoming_text
    service.process_incoming_text.return_value = (
        "This contains [SECRET_REF:12345]",
        [
            SecretReference(
                uuid="12345",
                description="API Key detected",
                context_hint="api_key=***",
                sensitivity="HIGH",
                detected_pattern="api_key",
                auto_decapsulate_actions=[],
                created_at=datetime.now(timezone.utc),
                last_accessed=None
            )
        ]
    )
    
    return service


@pytest.fixture
def test_app(mock_secrets_service, mock_auth_service):
    """Create a test FastAPI app with secrets routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add mock services to app state
    app.state.secrets_service = mock_secrets_service
    app.state.auth_service = mock_auth_service
    
    return app


@pytest.fixture
def client(test_app):
    """Create a test client."""
    return TestClient(test_app)


class TestSecretsStats:
    """Test /v1/secrets/stats endpoint."""
    
    def test_get_stats_success(self, client, mock_secrets_service, observer_headers):
        """Test getting secrets service statistics."""
        response = client.get(
            "/v1/secrets/stats",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['total_secrets'] == 42
        assert data['data']['active_filters'] == 5
        assert data['data']['filter_matches_today'] == 123
        assert data['data']['encryption_enabled'] is True
        assert data['data']['storage_health'] is True
    
    def test_get_stats_no_auth(self, client):
        """Test getting stats without authentication."""
        response = client.get("/v1/secrets/stats")
        assert response.status_code == 401
    
    def test_get_stats_no_service(self, client, observer_headers):
        """Test getting stats when service unavailable."""
        client.app.state.secrets_service = None
        
        response = client.get(
            "/v1/secrets/stats",
            headers=observer_headers
        )
        
        assert response.status_code == 503
        assert "Secrets service not available" in response.text


class TestSecretsFilters:
    """Test /v1/secrets/filters endpoints."""
    
    def test_get_filters_success(self, client, observer_headers):
        """Test getting filter configuration."""
        response = client.get(
            "/v1/secrets/filters",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['total'] == 3  # 2 patterns + 1 sensitivity config
        
        # Check pattern filter
        pattern_filter = next(f for f in data['data']['filters'] if f['filter_name'] == 'api_key')
        assert pattern_filter['filter_type'] == 'pattern'
        assert pattern_filter['enabled'] is True
        assert pattern_filter['metadata']['pattern'] == r'api[_-]?key.*'
        
        # Check sensitivity filter
        sensitivity_filter = next(f for f in data['data']['filters'] if f['filter_name'] == 'sensitivity_HIGH')
        assert sensitivity_filter['filter_type'] == 'sensitivity'
        assert sensitivity_filter['metadata']['redaction_enabled'] == 'True'
    
    def test_update_filters_success(self, client, admin_headers):
        """Test updating filter configuration."""
        update_request = {
            "patterns": [
                {
                    "name": "new_pattern",
                    "pattern": r"secret_.*",
                    "sensitivity": "HIGH",
                    "enabled": True
                }
            ]
        }
        
        response = client.put(
            "/v1/secrets/filters",
            headers=admin_headers,
            json=update_request
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['success'] is True
        assert data['data']['updated_filters'] == 1
        assert data['data']['message'] == "Filters updated successfully"
    
    def test_update_filters_observer_forbidden(self, client, observer_headers):
        """Test that observers cannot update filters."""
        update_request = {
            "patterns": [
                {
                    "name": "new_pattern",
                    "pattern": r"secret_.*",
                    "sensitivity": "HIGH",
                    "enabled": True
                }
            ]
        }
        
        response = client.put(
            "/v1/secrets/filters",
            headers=observer_headers,
            json=update_request
        )
        
        assert response.status_code == 403
        assert "Requires ADMIN role or higher" in response.json()['detail']


class TestSecretsTest:
    """Test /v1/secrets/test endpoint."""
    
    def test_secret_detection_positive(self, client, observer_headers):
        """Test secret detection with secrets present."""
        test_request = {
            "content": "My API key is api_key=sk-1234567890abcdef"
        }
        
        response = client.post(
            "/v1/secrets/test",
            headers=observer_headers,
            json=test_request
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['contains_secrets'] is True
        assert data['data']['detected_count'] == 1
        assert 'api_key' in data['data']['patterns_matched']
    
    def test_secret_detection_negative(self, client, observer_headers, mock_secrets_service):
        """Test secret detection with no secrets."""
        # Mock no secrets detected
        mock_secrets_service.process_incoming_text.return_value = (
            "This text has no secrets",
            []
        )
        
        test_request = {
            "content": "This text has no secrets"
        }
        
        response = client.post(
            "/v1/secrets/test",
            headers=observer_headers,
            json=test_request
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['contains_secrets'] is False
        assert data['data']['detected_count'] == 0
        assert len(data['data']['patterns_matched']) == 0
    
    def test_secret_detection_large_content(self, client, observer_headers):
        """Test secret detection with large content."""
        # Test content at max length
        test_request = {
            "content": "x" * 10000
        }
        
        response = client.post(
            "/v1/secrets/test",
            headers=observer_headers,
            json=test_request
        )
        
        assert response.status_code == 200
    
    def test_secret_detection_too_large(self, client, observer_headers):
        """Test secret detection with content exceeding limit."""
        # Test content exceeding max length
        test_request = {
            "content": "x" * 10001
        }
        
        response = client.post(
            "/v1/secrets/test",
            headers=observer_headers,
            json=test_request
        )
        
        assert response.status_code == 422  # Validation error


class TestSecretsAudit:
    """Test /v1/secrets/audit endpoint."""
    
    def test_get_audit_empty(self, client, observer_headers):
        """Test getting audit log when empty."""
        response = client.get(
            "/v1/secrets/audit",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['total'] == 0
        assert data['data']['filtered_count'] == 0
        assert len(data['data']['logs']) == 0
    
    def test_get_audit_with_params(self, client, observer_headers):
        """Test getting audit log with filter parameters."""
        response = client.get(
            "/v1/secrets/audit?limit=50&offset=10&operation=VIEW",
            headers=observer_headers
        )
        
        assert response.status_code == 200
        data = response.json()
        assert 'logs' in data['data']


class TestSecretsFilterUpdate:
    """Test filter update functionality."""
    
    def test_filter_update_with_sensitivity(self, client, admin_headers):
        """Test updating both patterns and sensitivity config."""
        update_request = {
            "patterns": [
                {
                    "name": "custom_secret",
                    "pattern": r"custom_secret_\w+",
                    "sensitivity": "CRITICAL",
                    "enabled": True
                }
            ],
            "sensitivity_config": {
                "CRITICAL": {
                    "level": "CRITICAL",
                    "redaction_enabled": True,
                    "audit_enabled": True
                }
            }
        }
        
        response = client.put(
            "/v1/secrets/filters",
            headers=admin_headers,
            json=update_request
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data['data']['success'] is True
        assert data['data']['updated_filters'] == 2  # 1 pattern + 1 sensitivity
    
    def test_service_error_handling(self, client, observer_headers, mock_secrets_service):
        """Test error handling when service raises exception."""
        mock_secrets_service.get_service_stats.side_effect = Exception("Service error")
        
        response = client.get(
            "/v1/secrets/stats",
            headers=observer_headers
        )
        
        assert response.status_code == 500
        assert "Service error" in response.json()['detail']


class TestSecretsAuth:
    """Test authentication requirements for all endpoints."""
    
    @pytest.mark.parametrize("endpoint,method", [
        ("/v1/secrets/stats", "GET"),
        ("/v1/secrets/filters", "GET"),
        ("/v1/secrets/test", "POST"),
        ("/v1/secrets/audit", "GET"),
    ])
    def test_all_endpoints_require_auth(self, client, endpoint, method):
        """Test that all endpoints require authentication."""
        if method == "GET":
            response = client.get(endpoint)
        elif method == "POST":
            response = client.post(endpoint, json={})
        elif method == "PUT":
            response = client.put(endpoint, json={})
        
        assert response.status_code == 401
        assert "Missing authorization header" in response.json()['detail']