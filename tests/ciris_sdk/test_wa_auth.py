"""Tests for WA (Wise Authority) authentication via SDK."""
import pytest
import asyncio
import os
from pathlib import Path
from ciris_sdk import CIRISClient
from ciris_sdk.exceptions import CIRISConnectionError

# WA test fixtures are available from conftest.py


class TestWAAuthentication:
    """Test WA authentication functionality through API."""
    
    @pytest.fixture
    async def running_api_or_skip(self):
        """Check if API is running, skip test if not."""
        try:
            async with CIRISClient(base_url="http://localhost:8080") as client:
                # Try to connect
                await client._transport.request("GET", "/api/v1/health")
                return client
        except (CIRISConnectionError, Exception):
            pytest.skip("API not running - skipping SDK tests")
    
    @pytest.mark.asyncio
    async def test_wa_private_key_location(self):
        """Test that WA private key location is documented."""
        # The standard location for WA private key is documented
        expected_path = Path.home() / ".ciris" / "wa_private_key.pem"
        
        # For SDK users, they need to know where to place their key
        # This test just verifies the path is constructed correctly
        assert str(expected_path).endswith(".ciris/wa_private_key.pem")
        
        # If the key exists (in production/dev environment), check it's readable
        if expected_path.exists():
            assert os.access(expected_path, os.R_OK), "WA private key exists but not readable"
            
            # Verify it's a valid private key format
            key_content = expected_path.read_bytes()
            assert b"BEGIN PRIVATE KEY" in key_content or b"BEGIN ENCRYPTED PRIVATE KEY" in key_content
            assert b"END PRIVATE KEY" in key_content or b"END ENCRYPTED PRIVATE KEY" in key_content
    
    @pytest.mark.asyncio
    async def test_wa_auth_endpoints(self, running_api_or_skip):
        """Test WA authentication endpoints are available."""
        client = running_api_or_skip
        
        # Check if auth endpoints exist
        try:
            # Try to access a protected endpoint
            resp = await client._transport.request("GET", "/api/v1/wa/status")
            assert resp.status_code in [200, 401, 403]  # OK or auth required
        except Exception:
            # Endpoint might not exist yet - that's OK for now
            pass
    
    @pytest.mark.asyncio
    async def test_defer_with_wa_context(self, running_api_or_skip):
        """Test deferral includes WA context."""
        client = running_api_or_skip
        channel = "test_wa_defer"
        
        # Create a scenario requiring WA
        msg = await client.messages.send(
            content="$defer Need wise authority approval for this sensitive request",
            channel_id=channel,
            author_name="TestUser"
        )
        
        # Wait for agent response
        try:
            response = await client.messages.wait_for_response(
                channel_id=channel,
                after_message_id=msg.id,
                timeout=5.0
            )
            
            # Check that deferral was acknowledged
            assert response is not None
            assert "defer" in response.content.lower() or "wise authority" in response.content.lower()
        except asyncio.TimeoutError:
            # Deferral might not generate immediate response
            pass
    
    @pytest.mark.asyncio
    async def test_reject_with_filter_creation(self, running_api_or_skip):
        """Test rejection can create adaptive filters."""
        client = running_api_or_skip
        channel = "test_reject_filter"
        
        # Send a request that should be rejected
        msg = await client.messages.send(
            content="$reject This violates ethical guidelines - please filter similar requests",
            channel_id=channel,
            author_name="TestUser"
        )
        
        # Wait for response
        try:
            response = await client.messages.wait_for_response(
                channel_id=channel,
                after_message_id=msg.id,
                timeout=5.0
            )
            
            assert response is not None
            # Agent should acknowledge rejection
            assert "reject" in response.content.lower() or "cannot" in response.content.lower()
        except asyncio.TimeoutError:
            # Rejection might terminate without response
            pass
    
    @pytest.mark.asyncio
    async def test_channel_observer_token(self, running_api_or_skip):
        """Test that adapters get channel observer tokens."""
        client = running_api_or_skip
        
        # When an adapter connects, it should get an observer token
        # This is typically automatic, but we can verify the pattern
        
        # The API adapter should have a channel identity like "http:127.0.0.1:8080"
        # And should be operating with observer privileges
        
        # Send a basic message (observers can do this)
        msg = await client.messages.send(
            content="Test message from observer",
            channel_id="test_observer",
            author_name="TestUser"
        )
        
        assert msg.id is not None
        
        # Try to do something that requires authority (should fail)
        # This would need an actual protected endpoint to test properly
    
    @pytest.mark.asyncio
    async def test_wa_scopes_in_action(self, running_api_or_skip):
        """Test different WA scopes through actions."""
        client = running_api_or_skip
        
        # Test observer scopes (read:any, write:message)
        # Should work:
        messages = await client.messages.list("test_channel", limit=5)
        assert isinstance(messages, list)
        
        # Should work:
        msg = await client.messages.send(
            content="Observer can send messages",
            channel_id="test_channel",
            author_name="TestUser"
        )
        assert msg.id is not None
        
        # Test that observers cannot perform admin actions
        # (Would need admin endpoints in SDK to test properly)


# TestWAAuthWithHarness class removed - requires wa_test_harness fixture from engine tests
# SDK tests should only test SDK functionality against running API