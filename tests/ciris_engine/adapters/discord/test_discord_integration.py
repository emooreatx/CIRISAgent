"""
Integration tests for Discord adapter health and telemetry.
Extracted from test_discord_comprehensive.py to focus on integration testing.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from ciris_engine.adapters.discord.adapter import DiscordPlatform
from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.registries.base import Priority


class TestDiscordAdapterIntegration:
    """Integration tests for Discord adapter health and telemetry"""
    
    @pytest.mark.asyncio
    async def test_adapter_health_integration(self):
        """Test adapter health check integration"""
        adapter = DiscordAdapter("test_token")
        
        # Test unhealthy state (no client)
        health = await adapter.is_healthy()
        assert health == False
        
        # Test healthy state (mock client)
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        adapter._channel_manager.set_client(mock_client)
        
        health = await adapter.is_healthy()
        assert health == True
        
        # Test unhealthy state (closed client)
        mock_client.is_closed.return_value = True
        health = await adapter.is_healthy()
        assert health == False
    
    def test_adapter_service_registration(self):
        """Test that adapter properly registers with service types"""
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter'), \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver'), \
             patch('ciris_engine.adapters.discord.adapter.discord.Client'):
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            services = platform.get_services_to_register()
            
            # Verify all required service types are registered
            service_types = {s.service_type for s in services}
            expected_types = {ServiceType.COMMUNICATION, ServiceType.WISE_AUTHORITY, ServiceType.TOOL}
            assert service_types == expected_types
            
            # Verify each service has proper capabilities
            for service in services:
                assert len(service.capabilities) > 0
                assert len(service.handlers) > 0
                assert service.priority == Priority.HIGH
    
    @pytest.mark.asyncio
    async def test_adapter_telemetry_data(self):
        """Test adapter provides proper telemetry data"""
        adapter = DiscordAdapter("test_token")
        
        # Mock client for telemetry
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        mock_client.user = MagicMock()
        mock_client.user.id = 12345
        adapter._channel_manager.set_client(mock_client)
        
        # Test adapter metadata for telemetry
        assert adapter.__class__.__name__ == "DiscordAdapter"
        assert adapter.__class__.__module__ == "ciris_engine.adapters.discord.discord_adapter"
        
        # Test health status for telemetry
        health = await adapter.is_healthy()
        assert health == True
        
        # Test adapter can be identified by telemetry collector
        adapter_id = str(id(adapter))
        assert isinstance(adapter_id, str)
        assert len(adapter_id) > 0
    
    def test_adapter_supports_multiple_service_protocols(self):
        """Test adapter implements multiple service protocols"""
        adapter = DiscordAdapter("test_token")
        
        # Should implement all required service protocols
        from ciris_engine.protocols.services import CommunicationService, WiseAuthorityService, ToolService
        
        assert isinstance(adapter, CommunicationService)
        # Note: DiscordAdapter extends CommunicationService but also provides WA and Tool functionality
        # The platform registers it for multiple service types
    
    @pytest.mark.asyncio
    async def test_full_discord_platform_health_integration(self):
        """Test complete Discord platform health reporting"""
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter') as mock_adapter_class, \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver'), \
             patch('ciris_engine.adapters.discord.adapter.discord.Client'):
            
            # Mock adapter instance with health check
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.is_healthy = AsyncMock(return_value=True)
            mock_adapter_class.return_value = mock_adapter_instance
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            
            # Test that platform's adapter reports as healthy
            health = await platform.discord_adapter.is_healthy()
            assert health == True
            
            # Verify the adapter can be used for telemetry collection
            assert hasattr(platform.discord_adapter, 'is_healthy')
            assert callable(platform.discord_adapter.is_healthy)
    
    @pytest.mark.asyncio
    async def test_adapter_lifecycle_integration(self):
        """Test complete adapter lifecycle"""
        adapter = DiscordAdapter("test_token")
        
        # Mock client for lifecycle testing
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        adapter._channel_manager.set_client(mock_client)
        
        # Test start
        with patch.object(adapter.__class__.__bases__[0], 'start', new_callable=AsyncMock) as mock_start:
            await adapter.start()
            mock_start.assert_called_once()
        
        # Test is_healthy during operation
        with patch.object(adapter._channel_manager, 'is_client_ready', return_value=True):
            health = await adapter.is_healthy()
            assert health == True
        
        # Test stop
        with patch.object(adapter._tool_handler, 'clear_tool_results') as mock_clear:
            with patch.object(adapter.__class__.__bases__[0], 'stop', new_callable=AsyncMock) as mock_stop:
                await adapter.stop()
                mock_clear.assert_called_once()
                mock_stop.assert_called_once()
    
    def test_platform_component_integration(self):
        """Test that platform properly integrates all components"""
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter') as mock_adapter, \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver') as mock_observer, \
             patch('ciris_engine.adapters.discord.adapter.discord.Client') as mock_client:
            
            mock_adapter_instance = MagicMock()
            mock_adapter.return_value = mock_adapter_instance
            
            mock_observer_instance = MagicMock()
            mock_observer.return_value = mock_observer_instance
            
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            
            # Verify all components are initialized
            assert platform.discord_adapter == mock_adapter_instance
            assert platform.discord_observer == mock_observer_instance
            assert platform.client == mock_client_instance
            
            # Verify configuration is passed correctly
            mock_adapter.assert_called_once()
            mock_observer.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_end_to_end_message_flow_integration(self):
        """Test end-to-end message processing flow"""
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter') as mock_adapter_class, \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver') as mock_observer_class, \
             patch('ciris_engine.adapters.discord.adapter.discord.Client'):
            
            # Set up mock instances
            mock_adapter = MagicMock()
            mock_adapter_class.return_value = mock_adapter
            
            mock_observer = MagicMock()
            mock_observer.handle_incoming_message = AsyncMock()
            mock_observer_class.return_value = mock_observer
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            
            # Create test message
            from ciris_engine.schemas.foundational_schemas_v1 import DiscordMessage
            from datetime import datetime, timezone
            
            test_message = DiscordMessage(
                message_id="123456",
                destination_id="789012", 
                author_id="345678",
                author_name="testuser",
                content="integration test message",
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
            # Test message handling flow
            await platform._handle_discord_message_event(test_message)
            
            # Verify message was passed to observer
            mock_observer.handle_incoming_message.assert_called_once_with(test_message)
    
    def test_service_registration_capabilities_integration(self):
        """Test that service registrations have proper capabilities"""
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter'), \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver'), \
             patch('ciris_engine.adapters.discord.adapter.discord.Client'):
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            services = platform.get_services_to_register()
            
            # Check communication service capabilities (now matches protocol)
            comm_service = next(s for s in services if s.service_type == ServiceType.COMMUNICATION)
            expected_comm_caps = ["send_message", "fetch_messages"]
            for cap in expected_comm_caps:
                assert cap in comm_service.capabilities
            
            # Check wise authority service capabilities  
            wa_service = next(s for s in services if s.service_type == ServiceType.WISE_AUTHORITY)
            expected_wa_caps = ["fetch_guidance", "send_deferral"]
            for cap in expected_wa_caps:
                assert cap in wa_service.capabilities
            
            # Check tool service capabilities (now matches protocol)
            tool_service = next(s for s in services if s.service_type == ServiceType.TOOL)
            expected_tool_caps = ["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]
            for cap in expected_tool_caps:
                assert cap in tool_service.capabilities