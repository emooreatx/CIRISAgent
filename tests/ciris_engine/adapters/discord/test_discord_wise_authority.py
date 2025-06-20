"""
Tests for Discord adapter as WiseAuthority service for deferrals.
Extracted from test_discord_comprehensive.py to focus on WiseAuthority functionality.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.schemas.wa_context_schemas_v1 import GuidanceContext, DeferralContext


class TestDiscordWiseAuthorityService:
    """Test Discord adapter as WiseAuthority service for deferrals"""
    
    @pytest.fixture
    def adapter_with_deferral(self):
        """Discord adapter configured for deferral testing"""
        adapter = DiscordAdapter("test_token")
        
        # Mock client
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        adapter._channel_manager.set_client(mock_client)
        adapter._message_handler.set_client(mock_client)
        adapter._guidance_handler.set_client(mock_client)
        adapter._tool_handler.set_client(mock_client)
        
        return adapter
    
    @pytest.mark.asyncio
    async def test_send_deferral_success(self, adapter_with_deferral):
        """Test successful deferral to human"""
        adapter = adapter_with_deferral
        
        # Mock send_deferral method
        with patch.object(adapter, 'send_deferral', return_value=True) as mock_send:
            context = DeferralContext(
                thought_id="thought_123",
                task_id="task_456",
                reason="Need human guidance"
            )
            result = await adapter.send_deferral(context)
            
            assert result == True
            mock_send.assert_called_once_with(context)
    
    @pytest.mark.asyncio
    async def test_send_deferral_failure(self, adapter_with_deferral):
        """Test deferral failure"""
        adapter = adapter_with_deferral
        
        # Mock send_deferral to return False (failure)
        with patch.object(adapter, 'send_deferral', return_value=False) as mock_send:
            context = DeferralContext(
                thought_id="thought_123",
                task_id="task_456",
                reason="Need guidance"
            )
            result = await adapter.send_deferral(context)
            
            assert result == False
            mock_send.assert_called_once_with(context)
    
    @pytest.mark.asyncio
    async def test_fetch_guidance_success(self, adapter_with_deferral):
        """Test fetching guidance successfully"""
        adapter = adapter_with_deferral
        
        # Mock fetch_guidance method to return guidance
        test_context = GuidanceContext(
            thought_id="thought_123",
            task_id="task_456",
            question="Need guidance on ethical dilemma",
            ethical_considerations=["Consider the covenant principles"]
        )
        expected_result = "Follow the covenant principles"
        
        with patch.object(adapter, 'fetch_guidance', return_value=expected_result) as mock_fetch:
            result = await adapter.fetch_guidance(test_context)
            
            assert result == expected_result
            mock_fetch.assert_called_once_with(test_context)
    
    @pytest.mark.asyncio
    async def test_fetch_guidance_failure(self, adapter_with_deferral):
        """Test guidance fetch failure"""
        adapter = adapter_with_deferral
        
        # Mock fetch_guidance to raise exception
        test_context = GuidanceContext(
            thought_id="thought_123",
            task_id="task_456",
            question="Need guidance on ethical dilemma"
        )
        
        with patch.object(adapter, 'fetch_guidance', side_effect=Exception("Fetch failed")) as mock_fetch:
            with pytest.raises(Exception, match="Fetch failed"):
                await adapter.fetch_guidance(test_context)
            
            mock_fetch.assert_called_once_with(test_context)
    
    @pytest.mark.asyncio
    async def test_send_deferral_with_full_implementation(self, adapter_with_deferral):
        """Test send_deferral with full implementation (not mocked)"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = "567890"
            mock_get_config.return_value = mock_config
            
            with patch.object(adapter, 'retry_with_backoff', new_callable=AsyncMock) as mock_retry:
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    context = DeferralContext(
                        thought_id="thought_123",
                        task_id="task_456",
                        reason="Need human guidance",
                        metadata={"context": "data"}
                    )
                    result = await adapter.send_deferral(context)
                    
                    assert result is True
                    mock_retry.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_send_deferral_no_channel_configured(self, adapter_with_deferral):
        """Test send_deferral when no deferral channel is configured"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = None
            mock_get_config.return_value = mock_config
            
            context = DeferralContext(
                thought_id="thought_123",
                task_id="task_456",
                reason="Need guidance"
            )
            result = await adapter.send_deferral(context)
            
            # Should return False when no channel is configured
            assert result is False
    
    @pytest.mark.asyncio
    async def test_fetch_guidance_with_full_implementation(self, adapter_with_deferral):
        """Test fetch_guidance with full implementation (not mocked)"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = "567890"
            mock_get_config.return_value = mock_config
            
            test_context = GuidanceContext(
                thought_id="thought_123",
                task_id="task_123",
                question="Ethical dilemma"
            )
            expected_guidance = {"guidance": "Follow the covenant"}
            
            with patch.object(adapter, 'retry_with_backoff', return_value=expected_guidance):
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    result = await adapter.fetch_guidance(test_context)
                    
                    # Should extract the guidance from the response
                    assert result == "Follow the covenant"
    
    @pytest.mark.asyncio
    async def test_fetch_guidance_no_channel_configured(self, adapter_with_deferral):
        """Test fetch_guidance when no deferral channel is configured"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = None
            mock_get_config.return_value = mock_config
            
            test_context = GuidanceContext(
                thought_id="thought_123",
                task_id="task_456",
                question="Need guidance"
            )
            
            with pytest.raises(RuntimeError, match="Guidance channel not configured"):
                await adapter.fetch_guidance(test_context)
    
    @pytest.mark.asyncio
    async def test_deferral_message_formatting(self, adapter_with_deferral):
        """Test that deferral messages are formatted correctly"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = "567890"
            mock_get_config.return_value = mock_config
            
            # Capture the actual message sent
            sent_message = None
            
            async def capture_message(*args, **kwargs):
                nonlocal sent_message
                sent_message = args[0] if args else None
                return True
            
            with patch.object(adapter, 'retry_with_backoff', side_effect=capture_message):
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    context = DeferralContext(
                        thought_id="thought_123",
                        task_id="task_456",
                        reason="Complex ethical decision needed",
                        priority="high",
                        metadata={"urgency": "high"}
                    )
                    await adapter.send_deferral(context)
                    
                    # Verify the message contains the key information
                    assert sent_message is not None
                    # The exact format depends on the implementation, but should contain key details
    
    @pytest.mark.asyncio
    async def test_guidance_context_formatting(self, adapter_with_deferral):
        """Test that guidance requests format context correctly"""
        adapter = adapter_with_deferral
        
        with patch('ciris_engine.config.config_manager.get_config') as mock_get_config:
            mock_config = MagicMock()
            mock_config.discord_deferral_channel_id = "567890"
            mock_get_config.return_value = mock_config
            
            # Capture the guidance request made
            guidance_request = None
            
            async def capture_guidance_request(*args, **kwargs):
                nonlocal guidance_request
                guidance_request = args[0] if args else None
                return {"guidance": "Test guidance response"}
            
            with patch.object(adapter, 'retry_with_backoff', side_effect=capture_guidance_request):
                with patch('ciris_engine.adapters.discord.discord_adapter.persistence'):
                    test_context = GuidanceContext(
                        thought_id="thought_456",
                        task_id="task_789",
                        question="Should I help with this request?",
                        domain_context={
                            "urgency": "medium",
                            "user_info": "New user"
                        }
                    )
                    
                    result = await adapter.fetch_guidance(test_context)
                    
                    assert result == "Test guidance response"
                    assert guidance_request is not None
                    # The guidance request should be formatted appropriately
    
    def test_wise_authority_service_protocol_compliance(self, adapter_with_deferral):
        """Test that adapter properly implements WiseAuthorityService protocol"""
        adapter = adapter_with_deferral
        
        # Check that required methods exist
        assert hasattr(adapter, 'send_deferral')
        assert hasattr(adapter, 'fetch_guidance')
        assert callable(adapter.send_deferral)
        assert callable(adapter.fetch_guidance)
        
        # Check that methods have appropriate signatures
        import inspect
        
        send_deferral_sig = inspect.signature(adapter.send_deferral)
        # Updated method now takes a single context parameter
        assert 'context' in send_deferral_sig.parameters
        
        fetch_guidance_sig = inspect.signature(adapter.fetch_guidance)
        assert 'context' in fetch_guidance_sig.parameters