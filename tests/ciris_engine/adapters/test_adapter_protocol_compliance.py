"""
Comprehensive unit tests to verify all adapters are protocol and schema compliant.
Tests that adapters correctly implement service protocols and expose correct capabilities.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from typing import List

from ciris_engine.protocols.services import (
    CommunicationService, 
    WiseAuthorityService, 
    ToolService, 
    LLMService,
    MemoryService,
    AuditService
)
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
from ciris_engine.registries.base import Priority


class TestDiscordAdapterProtocolCompliance:
    """Test Discord adapter protocol compliance."""
    
    @pytest.fixture
    def discord_adapter(self):
        """Create Discord adapter for testing."""
        from ciris_engine.adapters.discord.discord_adapter import DiscordAdapter
        adapter = DiscordAdapter("test_token")
        
        # Mock the client to avoid Discord connection
        mock_client = MagicMock()
        mock_client.is_closed.return_value = False
        adapter._channel_manager.set_client(mock_client)
        adapter._message_handler.set_client(mock_client)
        adapter._guidance_handler.set_client(mock_client)
        adapter._tool_handler.set_client(mock_client)
        
        return adapter
    
    def test_discord_implements_communication_service(self, discord_adapter):
        """Test Discord adapter implements CommunicationService protocol."""
        assert isinstance(discord_adapter, CommunicationService)
        
        # Check required methods exist
        assert hasattr(discord_adapter, 'send_message')
        assert hasattr(discord_adapter, 'fetch_messages')
        assert hasattr(discord_adapter, 'is_healthy')
        assert hasattr(discord_adapter, 'get_capabilities')
        
        # Check methods are callable
        assert callable(discord_adapter.send_message)
        assert callable(discord_adapter.fetch_messages)
        assert callable(discord_adapter.is_healthy)
        assert callable(discord_adapter.get_capabilities)
    
    def test_discord_implements_wise_authority_service(self, discord_adapter):
        """Test Discord adapter implements WiseAuthorityService protocol."""
        assert isinstance(discord_adapter, WiseAuthorityService)
        
        # Check required methods exist
        assert hasattr(discord_adapter, 'fetch_guidance')
        assert hasattr(discord_adapter, 'send_deferral')
        
        # Check methods are callable
        assert callable(discord_adapter.fetch_guidance)
        assert callable(discord_adapter.send_deferral)
    
    def test_discord_implements_tool_service(self, discord_adapter):
        """Test Discord adapter implements ToolService protocol."""
        assert isinstance(discord_adapter, ToolService)
        
        # Check required methods exist
        assert hasattr(discord_adapter, 'execute_tool')
        assert hasattr(discord_adapter, 'get_available_tools')
        assert hasattr(discord_adapter, 'get_tool_result')
        assert hasattr(discord_adapter, 'validate_parameters')
        
        # Check methods are callable
        assert callable(discord_adapter.execute_tool)
        assert callable(discord_adapter.get_available_tools)
        assert callable(discord_adapter.get_tool_result)
        assert callable(discord_adapter.validate_parameters)
    
    @pytest.mark.asyncio
    async def test_discord_capabilities_match_protocols(self, discord_adapter):
        """Test Discord adapter reports correct protocol capabilities."""
        capabilities = await discord_adapter.get_capabilities()
        
        # Should include all capabilities from all three protocols
        expected_capabilities = [
            # CommunicationService
            "send_message", "fetch_messages",
            # WiseAuthorityService
            "fetch_guidance", "send_deferral",
            # ToolService
            "execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"
        ]
        
        for cap in expected_capabilities:
            assert cap in capabilities, f"Missing capability: {cap}"
    
    def test_discord_platform_service_registrations(self):
        """Test Discord platform registers correct services with correct capabilities."""
        from ciris_engine.adapters.discord.adapter import DiscordPlatform
        
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.discord.adapter.DiscordAdapter'), \
             patch('ciris_engine.adapters.discord.adapter.DiscordObserver'), \
             patch('ciris_engine.adapters.discord.adapter.discord.Client'):
            
            platform = DiscordPlatform(mock_runtime, discord_bot_token="test_token")
            services = platform.get_services_to_register()
            
            # Should register exactly 3 services
            assert len(services) == 3
            
            # Check service types
            service_types = {s.service_type for s in services}
            expected_types = {ServiceType.COMMUNICATION, ServiceType.WISE_AUTHORITY, ServiceType.TOOL}
            assert service_types == expected_types
            
            # Check capabilities match protocol definitions
            for service in services:
                if service.service_type == ServiceType.COMMUNICATION:
                    assert service.capabilities == ["send_message", "fetch_messages"]
                elif service.service_type == ServiceType.WISE_AUTHORITY:
                    assert service.capabilities == ["fetch_guidance", "send_deferral"]
                elif service.service_type == ServiceType.TOOL:
                    assert service.capabilities == ["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]


class TestCLIAdapterProtocolCompliance:
    """Test CLI adapter protocol compliance."""
    
    @pytest.fixture
    def cli_adapter(self):
        """Create CLI adapter for testing."""
        from ciris_engine.adapters.cli.cli_adapter import CLIAdapter
        return CLIAdapter(interactive=False)
    
    def test_cli_implements_communication_service(self, cli_adapter):
        """Test CLI adapter implements CommunicationService protocol."""
        assert isinstance(cli_adapter, CommunicationService)
        
        # Check required methods exist and are callable
        assert hasattr(cli_adapter, 'send_message') and callable(cli_adapter.send_message)
        assert hasattr(cli_adapter, 'fetch_messages') and callable(cli_adapter.fetch_messages)
        assert hasattr(cli_adapter, 'is_healthy') and callable(cli_adapter.is_healthy)
        assert hasattr(cli_adapter, 'get_capabilities') and callable(cli_adapter.get_capabilities)
    
    def test_cli_implements_wise_authority_service(self, cli_adapter):
        """Test CLI adapter implements WiseAuthorityService protocol."""
        assert isinstance(cli_adapter, WiseAuthorityService)
        
        # Check required methods exist and are callable
        assert hasattr(cli_adapter, 'fetch_guidance') and callable(cli_adapter.fetch_guidance)
        assert hasattr(cli_adapter, 'send_deferral') and callable(cli_adapter.send_deferral)
    
    def test_cli_implements_tool_service(self, cli_adapter):
        """Test CLI adapter implements ToolService protocol."""
        assert isinstance(cli_adapter, ToolService)
        
        # Check required methods exist and are callable
        assert hasattr(cli_adapter, 'execute_tool') and callable(cli_adapter.execute_tool)
        assert hasattr(cli_adapter, 'get_available_tools') and callable(cli_adapter.get_available_tools)
        assert hasattr(cli_adapter, 'get_tool_result') and callable(cli_adapter.get_tool_result)
        assert hasattr(cli_adapter, 'validate_parameters') and callable(cli_adapter.validate_parameters)
    
    @pytest.mark.asyncio
    async def test_cli_capabilities_match_protocols(self, cli_adapter):
        """Test CLI adapter reports correct protocol capabilities."""
        capabilities = await cli_adapter.get_capabilities()
        
        # Should include all capabilities from all three protocols
        expected_capabilities = [
            # CommunicationService
            "send_message", "fetch_messages",
            # WiseAuthorityService
            "fetch_guidance", "send_deferral", 
            # ToolService
            "execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"
        ]
        
        for cap in expected_capabilities:
            assert cap in capabilities, f"Missing capability: {cap}"
    
    @pytest.mark.asyncio
    async def test_cli_tool_validation_works(self, cli_adapter):
        """Test CLI adapter's validate_parameters method works correctly."""
        # Test with valid tool and parameters
        assert await cli_adapter.validate_parameters("read_file", {"path": "test.txt"}) == True
        assert await cli_adapter.validate_parameters("write_file", {"path": "test.txt", "content": "data"}) == True
        assert await cli_adapter.validate_parameters("list_files", {}) == True
        assert await cli_adapter.validate_parameters("system_info", {}) == True
        
        # Test with invalid tool
        assert await cli_adapter.validate_parameters("nonexistent_tool", {}) == False
        
        # Test with missing required parameters
        assert await cli_adapter.validate_parameters("read_file", {}) == False
        assert await cli_adapter.validate_parameters("write_file", {}) == False
    
    def test_cli_platform_service_registrations(self):
        """Test CLI platform registers correct services with correct capabilities."""
        from ciris_engine.adapters.cli.adapter import CliPlatform
        
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.cli.adapter.CLIAdapter'):
            platform = CliPlatform(mock_runtime)
            services = platform.get_services_to_register()
            
            # Should register exactly 3 services
            assert len(services) == 3
            
            # Check service types
            service_types = {s.service_type for s in services}
            expected_types = {ServiceType.COMMUNICATION, ServiceType.WISE_AUTHORITY, ServiceType.TOOL}
            assert service_types == expected_types
            
            # Check capabilities match protocol definitions
            for service in services:
                if service.service_type == ServiceType.COMMUNICATION:
                    assert service.capabilities == ["send_message", "fetch_messages"]
                elif service.service_type == ServiceType.WISE_AUTHORITY:
                    assert service.capabilities == ["fetch_guidance", "send_deferral"]
                elif service.service_type == ServiceType.TOOL:
                    assert service.capabilities == ["execute_tool", "get_available_tools", "get_tool_result", "validate_parameters"]


class TestAPIAdapterProtocolCompliance:
    """Test API adapter protocol compliance."""
    
    @pytest.fixture
    def api_adapter(self):
        """Create API adapter for testing."""
        from ciris_engine.adapters.api.api_adapter import APIAdapter
        return APIAdapter(host="localhost", port=8000)
    
    def test_api_implements_communication_service(self, api_adapter):
        """Test API adapter implements CommunicationService protocol."""
        assert isinstance(api_adapter, CommunicationService)
        
        # Check required methods exist and are callable
        assert hasattr(api_adapter, 'send_message') and callable(api_adapter.send_message)
        assert hasattr(api_adapter, 'fetch_messages') and callable(api_adapter.fetch_messages)
        assert hasattr(api_adapter, 'is_healthy') and callable(api_adapter.is_healthy)
        assert hasattr(api_adapter, 'get_capabilities') and callable(api_adapter.get_capabilities)
    
    def test_api_does_not_implement_other_services(self, api_adapter):
        """Test API adapter only implements CommunicationService."""
        # Should NOT implement other service protocols
        assert not isinstance(api_adapter, WiseAuthorityService)
        assert not isinstance(api_adapter, ToolService)
        assert not isinstance(api_adapter, LLMService)
    
    @pytest.mark.asyncio
    async def test_api_capabilities_include_communication(self, api_adapter):
        """Test API adapter includes required communication capabilities."""
        capabilities = await api_adapter.get_capabilities()
        
        # Should include required communication capabilities
        assert "send_message" in capabilities
        assert "fetch_messages" in capabilities
        
        # May include additional API-specific capabilities
        assert "health_check" in capabilities
        assert "list_services" in capabilities
    
    def test_api_platform_service_registrations(self):
        """Test API platform registers correct service with correct capabilities."""
        from ciris_engine.adapters.api.adapter import ApiPlatform
        
        mock_runtime = MagicMock()
        
        with patch('ciris_engine.adapters.api.adapter.APIAdapter') as mock_adapter_class:
            mock_adapter_instance = MagicMock()
            mock_adapter_instance.get_capabilities.return_value = ["send_message", "fetch_messages", "health_check"]
            mock_adapter_class.return_value = mock_adapter_instance
            
            platform = ApiPlatform(mock_runtime)
            services = platform.get_services_to_register()
            
            # Should register exactly 1 service
            assert len(services) == 1
            
            # Check service type
            service = services[0]
            assert service.service_type == ServiceType.COMMUNICATION
            assert service.priority == Priority.NORMAL


class TestLLMServiceProtocolCompliance:
    """Test LLM service protocol compliance."""
    
    @pytest.fixture
    def llm_service(self):
        """Create LLM service for testing."""
        from ciris_engine.services.llm_service import OpenAICompatibleClient
        return OpenAICompatibleClient()
    
    def test_llm_implements_llm_service(self, llm_service):
        """Test LLM service implements LLMService protocol."""
        assert isinstance(llm_service, LLMService)
        
        # Check required methods exist and are callable
        assert hasattr(llm_service, 'call_llm_structured') and callable(llm_service.call_llm_structured)
        assert hasattr(llm_service, 'is_healthy') and callable(llm_service.is_healthy)
        assert hasattr(llm_service, 'get_capabilities') and callable(llm_service.get_capabilities)
        
        # Check that internal methods are NOT exposed publicly
        assert not hasattr(llm_service, 'get_client'), "get_client should be private (_get_client)"
    
    @pytest.mark.asyncio
    async def test_llm_capabilities_match_protocol(self, llm_service):
        """Test LLM service reports correct protocol capabilities."""
        capabilities = await llm_service.get_capabilities()
        
        # Should include required LLM capabilities
        expected_capabilities = ["call_llm_structured"]
        
        for cap in expected_capabilities:
            assert cap in capabilities, f"Missing capability: {cap}"


class TestProtocolDefinitionsIntegrity:
    """Test that protocol definitions themselves are consistent."""
    
    def test_communication_service_capabilities(self):
        """Test CommunicationService defines correct capabilities."""
        from ciris_engine.protocols.services import CommunicationService
        
        # Create instance to test default capabilities
        class TestCommService(CommunicationService):
            async def send_message(self, channel_id: str, content: str) -> bool:
                return True
            async def fetch_messages(self, channel_id: str, limit: int = 100):
                return []
            async def start(self):
                pass
            async def stop(self):
                pass
        
        service = TestCommService()
        
        # Test get_capabilities method exists and returns correct values
        assert hasattr(service, 'get_capabilities')
        assert callable(service.get_capabilities)
    
    def test_wise_authority_service_capabilities(self):
        """Test WiseAuthorityService defines correct capabilities."""
        from ciris_engine.protocols.services import WiseAuthorityService
        
        class TestWAService(WiseAuthorityService):
            async def fetch_guidance(self, context):
                return None
            async def send_deferral(self, thought_id: str, reason: str, context=None) -> bool:
                return True
            async def start(self):
                pass
            async def stop(self):
                pass
        
        service = TestWAService()
        assert hasattr(service, 'get_capabilities')
        assert callable(service.get_capabilities)
    
    def test_tool_service_capabilities(self):
        """Test ToolService defines correct capabilities."""
        from ciris_engine.protocols.services import ToolService
        
        class TestToolService(ToolService):
            async def execute_tool(self, tool_name: str, parameters):
                from ciris_engine.schemas.protocol_schemas_v1 import ToolExecutionResult
                return ToolExecutionResult(success=True, result={}, error=None, execution_time=0.0)
            async def get_available_tools(self):
                return []
            async def get_tool_result(self, correlation_id: str, timeout: float = 30.0):
                return None
            def get_tool_info(self, tool_name: str):
                return None
            def get_all_tool_info(self):
                return {}
            async def start(self):
                pass
            async def stop(self):
                pass
        
        service = TestToolService()
        assert hasattr(service, 'get_capabilities')
        assert callable(service.get_capabilities)
    
    def test_llm_service_capabilities(self):
        """Test LLMService defines correct capabilities."""
        from ciris_engine.protocols.services import LLMService
        
        class TestLLMService(LLMService):
            async def call_llm_structured(self, messages, response_model, max_tokens=1024, temperature=0.0, **kwargs):
                from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
                # Create a mock instance of the response model
                mock_response = response_model()
                usage = ResourceUsage(tokens=100)
                return mock_response, usage
            async def start(self):
                pass
            async def stop(self):
                pass
        
        service = TestLLMService()
        assert hasattr(service, 'get_capabilities')
        assert callable(service.get_capabilities)