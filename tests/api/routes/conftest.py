"""
Shared fixtures for API route tests.
"""
import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock

from ciris_engine.schemas.api.auth import UserRole, AuthContext, ROLE_PERMISSIONS
from ciris_engine.api.services.auth_service import APIAuthService, StoredAPIKey

@pytest.fixture
def mock_auth_service():
    """Create a mock auth service for testing."""
    service = Mock(spec=APIAuthService)

    # Mock methods
    service.validate_api_key = AsyncMock()
    service._get_key_id = Mock(return_value="test_key_id")

    # Setup default validation responses
    service.validate_api_key.side_effect = lambda key: {
        "observer_key": StoredAPIKey(
            key_hash="observer_hash",
            user_id="observer_user",
            role=UserRole.OBSERVER,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            expires_at=None,
            description="Observer Test Key",
            last_used=None,
            is_active=True
        ),
        "admin_key": StoredAPIKey(
            key_hash="admin_hash",
            user_id="admin_user",
            role=UserRole.ADMIN,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            expires_at=None,
            description="Admin Test Key",
            last_used=None,
            is_active=True
        ),
        "authority_key": StoredAPIKey(
            key_hash="authority_hash",
            user_id="authority_user",
            role=UserRole.AUTHORITY,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            expires_at=None,
            description="Authority Test Key",
            last_used=None,
            is_active=True
        ),
        "root_key": StoredAPIKey(
            key_hash="root_hash",
            user_id="root_user",
            role=UserRole.ROOT,
            created_at=datetime.now(timezone.utc),
            created_by="test",
            expires_at=None,
            description="Root Test Key",
            last_used=None,
            is_active=True
        )
    }.get(key)

    return service

@pytest.fixture
def observer_headers():
    """Headers for observer role."""
    return {"Authorization": "Bearer observer_key"}

@pytest.fixture
def admin_headers():
    """Headers for admin role."""
    return {"Authorization": "Bearer admin_key"}

@pytest.fixture
def authority_headers():
    """Headers for authority role."""
    return {"Authorization": "Bearer authority_key"}

@pytest.fixture
def root_headers():
    """Headers for root role."""
    return {"Authorization": "Bearer root_key"}
