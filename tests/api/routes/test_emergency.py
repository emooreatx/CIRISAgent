"""
Unit tests for emergency shutdown endpoint.

Tests signature validation, timestamp validation, and rejection of invalid signatures.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import base64
import json
from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import AsyncClient

from ciris_engine.api.routes.emergency import router, verify_signature, verify_timestamp
from ciris_engine.schemas.services.shutdown import (
    WASignedCommand,
    EmergencyShutdownStatus,
    EmergencyCommandType
)

# Mock Ed25519 keys for testing
# In real tests, you would generate actual key pairs
MOCK_PRIVATE_KEY = "mock_private_key"
MOCK_PUBLIC_KEY = "MCowBQYDK2VwAyEAGb9ECWmEzf6FQbrBZ9w7lshQhqowtrbLDFw4rXAxZuE="
MOCK_SIGNATURE = "dGVzdF9zaWduYXR1cmU="  # base64 encoded "test_signature"

# Create test app
app = FastAPI()
app.include_router(router)


class TestEmergencyEndpoint:
    """Test suite for emergency shutdown endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)
    
    @pytest.fixture
    def valid_command(self):
        """Create a valid shutdown command."""
        return WASignedCommand(
            command_id="test_cmd_123",
            command_type=EmergencyCommandType.SHUTDOWN_NOW,
            wa_id="test_wa_001",
            wa_public_key=MOCK_PUBLIC_KEY,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            reason="Test emergency shutdown",
            target_agent_id=None,
            target_tree_path=None,
            signature=MOCK_SIGNATURE,
            parent_command_id=None,
            relay_chain=[]
        )
    
    def test_test_endpoint(self, client):
        """Test the test endpoint is accessible."""
        response = client.get("/emergency/test")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert "timestamp" in data
    
    def test_shutdown_invalid_command_type(self, client, valid_command):
        """Test rejection of non-SHUTDOWN_NOW commands."""
        valid_command.command_type = EmergencyCommandType.FREEZE
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 400
        assert "Invalid command type" in response.json()["detail"]
    
    def test_shutdown_expired_timestamp(self, client, valid_command):
        """Test rejection of expired commands."""
        # Set issued_at to 10 minutes ago
        valid_command.issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 403
        assert "timestamp outside acceptable window" in response.json()["detail"]
    
    def test_shutdown_future_timestamp(self, client, valid_command):
        """Test rejection of commands from the future."""
        # Set issued_at to 5 minutes in the future
        valid_command.issued_at = datetime.now(timezone.utc) + timedelta(minutes=5)
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 403
        assert "timestamp outside acceptable window" in response.json()["detail"]
    
    @patch('ciris_engine.api.routes.emergency.verify_signature')
    @patch('ciris_engine.api.routes.emergency.is_authorized_key')
    def test_shutdown_invalid_signature(self, mock_authorized, mock_verify, client, valid_command):
        """Test rejection of invalid signatures."""
        mock_verify.return_value = False  # Invalid signature
        mock_authorized.return_value = True
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 403
        assert "Invalid signature" in response.json()["detail"]
    
    @patch('ciris_engine.api.routes.emergency.verify_signature')
    @patch('ciris_engine.api.routes.emergency.is_authorized_key')
    def test_shutdown_unauthorized_key(self, mock_authorized, mock_verify, client, valid_command):
        """Test rejection of unauthorized keys."""
        mock_verify.return_value = True
        mock_authorized.return_value = False  # Unauthorized key
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 403
        assert "Unauthorized public key" in response.json()["detail"]
    
    @patch('ciris_engine.api.routes.emergency.verify_signature')
    @patch('ciris_engine.api.routes.emergency.is_authorized_key')
    @patch('ciris_engine.logic.services.registry.ServiceRegistry.get_service')
    async def test_shutdown_with_runtime_service(self, mock_registry, mock_authorized, mock_verify, client, valid_command):
        """Test successful shutdown with RuntimeControlService."""
        mock_verify.return_value = True
        mock_authorized.return_value = True
        
        # Mock runtime service
        mock_runtime = AsyncMock()
        mock_status = EmergencyShutdownStatus(
            command_received=datetime.now(timezone.utc),
            command_verified=True,
            shutdown_initiated=datetime.now(timezone.utc),
            services_stopped=["test_service"],
            data_persisted=True,
            final_message_sent=True,
            shutdown_completed=datetime.now(timezone.utc),
            exit_code=0
        )
        mock_runtime.handle_emergency_shutdown.return_value = mock_status
        mock_registry.return_value = mock_runtime
        
        response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["command_verified"] is True
        assert data["data"]["shutdown_completed"] is not None
    
    @patch('ciris_engine.api.routes.emergency.verify_signature')
    @patch('ciris_engine.api.routes.emergency.is_authorized_key')
    @patch('ciris_engine.logic.services.registry.ServiceRegistry.get_service')
    def test_shutdown_without_runtime_service(self, mock_registry, mock_authorized, mock_verify, client, valid_command):
        """Test shutdown fallback when RuntimeControlService is not available."""
        mock_verify.return_value = True
        mock_authorized.return_value = True
        mock_registry.side_effect = Exception("Service not found")
        
        # Mock the app state
        mock_shutdown_service = AsyncMock()
        mock_runtime = Mock()
        mock_runtime.shutdown_service = mock_shutdown_service
        
        with patch.object(client.app.state, 'runtime', mock_runtime):
            response = client.post("/emergency/shutdown", json=valid_command.model_dump(mode="json"))
            
            # Should still work but with direct shutdown
            assert response.status_code == 200
            data = response.json()
            assert data["data"]["command_verified"] is True
            mock_shutdown_service.request_shutdown.assert_called_once()


class TestVerificationFunctions:
    """Test the verification helper functions."""
    
    def test_verify_timestamp_valid(self):
        """Test timestamp verification with valid timestamp."""
        command = Mock()
        command.issued_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        command.expires_at = None
        
        assert verify_timestamp(command) is True
    
    def test_verify_timestamp_too_old(self):
        """Test timestamp verification with old timestamp."""
        command = Mock()
        command.issued_at = datetime.now(timezone.utc) - timedelta(minutes=10)
        command.expires_at = None
        
        assert verify_timestamp(command) is False
    
    def test_verify_timestamp_future(self):
        """Test timestamp verification with future timestamp."""
        command = Mock()
        command.issued_at = datetime.now(timezone.utc) + timedelta(minutes=10)
        command.expires_at = None
        
        assert verify_timestamp(command) is False
    
    def test_verify_timestamp_expired(self):
        """Test timestamp verification with expired command."""
        command = Mock()
        command.issued_at = datetime.now(timezone.utc) - timedelta(minutes=2)
        command.expires_at = datetime.now(timezone.utc) - timedelta(minutes=1)
        
        assert verify_timestamp(command) is False
    
    @patch('ciris_engine.api.routes.emergency.CRYPTO_AVAILABLE', False)
    def test_verify_signature_no_crypto(self):
        """Test signature verification when crypto is not available."""
        command = Mock()
        assert verify_signature(command) is False
    
    @patch('ciris_engine.api.routes.emergency.CRYPTO_AVAILABLE', True)
    @patch('ciris_engine.api.routes.emergency.Ed25519PublicKey')
    def test_verify_signature_valid(self, mock_key_class):
        """Test signature verification with valid signature."""
        # Mock the verification process
        mock_public_key = Mock()
        mock_public_key.verify.return_value = None  # No exception means valid
        mock_key_class.from_public_bytes.return_value = mock_public_key
        
        command = WASignedCommand(
            command_id="test_123",
            command_type=EmergencyCommandType.SHUTDOWN_NOW,
            wa_id="wa_001",
            wa_public_key=MOCK_PUBLIC_KEY,
            issued_at=datetime.now(timezone.utc),
            reason="Test",
            signature=MOCK_SIGNATURE,
            relay_chain=[]
        )
        
        assert verify_signature(command) is True
        mock_public_key.verify.assert_called_once()
    
    @patch('ciris_engine.api.routes.emergency.CRYPTO_AVAILABLE', True)
    @patch('ciris_engine.api.routes.emergency.Ed25519PublicKey')
    def test_verify_signature_invalid(self, mock_key_class):
        """Test signature verification with invalid signature."""
        # Mock the verification to raise InvalidSignature
        mock_public_key = Mock()
        from cryptography.exceptions import InvalidSignature
        mock_public_key.verify.side_effect = InvalidSignature("Bad signature")
        mock_key_class.from_public_bytes.return_value = mock_public_key
        
        command = WASignedCommand(
            command_id="test_123",
            command_type=EmergencyCommandType.SHUTDOWN_NOW,
            wa_id="wa_001",
            wa_public_key=MOCK_PUBLIC_KEY,
            issued_at=datetime.now(timezone.utc),
            reason="Test",
            signature=MOCK_SIGNATURE,
            relay_chain=[]
        )
        
        assert verify_signature(command) is False


@pytest.mark.asyncio
class TestAsyncEmergencyEndpoint:
    """Async tests for emergency endpoint."""
    
    @pytest.fixture
    async def async_client(self):
        """Create async test client."""
        async with AsyncClient(app=app, base_url="http://test") as client:
            yield client
    
    @pytest.fixture
    def valid_command(self):
        """Create a valid shutdown command."""
        return WASignedCommand(
            command_id="test_cmd_123",
            command_type=EmergencyCommandType.SHUTDOWN_NOW,
            wa_id="test_wa_001",
            wa_public_key=MOCK_PUBLIC_KEY,
            issued_at=datetime.now(timezone.utc),
            expires_at=datetime.now(timezone.utc) + timedelta(minutes=5),
            reason="Test emergency shutdown",
            target_agent_id=None,
            target_tree_path=None,
            signature=MOCK_SIGNATURE,
            parent_command_id=None,
            relay_chain=[]
        )
    
    @patch('ciris_engine.api.routes.emergency.verify_signature')
    @patch('ciris_engine.api.routes.emergency.is_authorized_key')
    @patch('ciris_engine.logic.services.registry.ServiceRegistry.get_service')
    async def test_async_shutdown_success(self, mock_registry, mock_authorized, mock_verify, async_client, valid_command):
        """Test async emergency shutdown with all validations passing."""
        mock_verify.return_value = True
        mock_authorized.return_value = True
        
        # Mock runtime service
        mock_runtime = AsyncMock()
        mock_status = EmergencyShutdownStatus(
            command_received=datetime.now(timezone.utc),
            command_verified=True,
            shutdown_initiated=datetime.now(timezone.utc),
            services_stopped=["service1", "service2"],
            data_persisted=True,
            final_message_sent=True,
            shutdown_completed=datetime.now(timezone.utc),
            exit_code=0
        )
        mock_runtime.handle_emergency_shutdown.return_value = mock_status
        mock_registry.return_value = mock_runtime
        
        response = await async_client.post(
            "/emergency/shutdown",
            json=valid_command.model_dump(mode="json")
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["data"]["command_verified"] is True
        assert len(data["data"]["services_stopped"]) == 2
        assert data["data"]["exit_code"] == 0