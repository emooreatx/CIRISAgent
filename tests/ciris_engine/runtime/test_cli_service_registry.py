import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ciris_engine.runtime.ciris_runtime import CIRISRuntime


@pytest.mark.asyncio
async def test_cli_service_registry():
    """Ensure CLI mode of CIRISRuntime registers expected services."""
    # Create a minimal runtime with CLI adapter
    with patch('ciris_engine.runtime.ciris_runtime.load_adapter') as mock_load_adapter:
        # Create a mock CLI adapter that provides services
        class MockCLIAdapter:
            def __init__(self, runtime, **kwargs):
                self.runtime = runtime
                self.started = False
                self.stopped = False
                
            async def start(self):
                self.started = True
                
            async def stop(self):
                self.stopped = True
                
            async def run_lifecycle(self, agent_task):
                try:
                    await agent_task
                except asyncio.CancelledError:
                    pass
                    
            def get_services_to_register(self):
                """Return services that CLI adapter provides."""
                from ciris_engine.protocols.adapter_interface import ServiceRegistration, ServiceType
                from ciris_engine.registries.base import Priority
                
                # Create mock services that inherit from Service
                from ciris_engine.adapters.base import Service
                
                class MockCLIService(Service):
                    def __init__(self):
                        self.started = False
                        self.stopped = False
                        
                    async def start(self):
                        self.started = True
                        
                    async def stop(self):
                        self.stopped = True
                
                class MockCLIToolService(Service):
                    def __init__(self):
                        self.started = False
                        self.stopped = False
                        
                    async def start(self):
                        self.started = True
                        
                    async def stop(self):
                        self.stopped = True
                        
                class MockCLIWAService(Service):
                    def __init__(self):
                        self.started = False
                        self.stopped = False
                        
                    async def start(self):
                        self.started = True
                        
                    async def stop(self):
                        self.stopped = True
                
                mock_cli_service = MockCLIService()
                mock_tool_service = MockCLIToolService()
                mock_wa_service = MockCLIWAService()
                
                return [
                    ServiceRegistration(
                        service_type=ServiceType.COMMUNICATION,
                        provider=mock_cli_service,
                        priority=Priority.HIGH,
                        handlers=["SpeakHandler", "ObserveHandler"]
                    ),
                    ServiceRegistration(
                        service_type=ServiceType.TOOL,
                        provider=mock_tool_service,
                        priority=Priority.NORMAL,
                        handlers=["ToolHandler"]
                    ),
                    ServiceRegistration(
                        service_type=ServiceType.WISE_AUTHORITY,
                        provider=mock_wa_service,
                        priority=Priority.NORMAL,
                        handlers=["DeferHandler"]
                    )
                ]
        
        mock_load_adapter.return_value = MockCLIAdapter
        
        # Create runtime
        runtime = CIRISRuntime(adapter_types=["cli"], profile_name="default")
        
        # Set up service registry manually
        from ciris_engine.registries.base import ServiceRegistry
        from ciris_engine.runtime.service_initializer import ServiceInitializer
        
        runtime.service_initializer = ServiceInitializer()
        runtime.service_initializer.service_registry = ServiceRegistry()
        
        # Mock WA auth system for adapter registration
        runtime.service_initializer.wa_auth_system = AsyncMock()
        runtime.service_initializer.wa_auth_system.create_channel_token_for_adapter = AsyncMock(return_value="test_token")
        
        # Register adapter services
        await runtime._register_adapter_services()
        
        # Verify service registry has expected services
        info = runtime.service_registry.get_provider_info()
        handlers = info.get("handlers", {})
        
        # Check communication service registration
        speak_comm = handlers.get("SpeakHandler", {}).get("communication", [])
        assert len(speak_comm) > 0
        assert any("MockCLIService" in str(p) for p in speak_comm)
        
        # Observer service (now registered as communication)
        observe_comm = handlers.get("ObserveHandler", {}).get("communication", [])
        assert len(observe_comm) > 0
        assert any("MockCLIService" in str(p) for p in observe_comm)
        
        # Tool service
        tool_services = handlers.get("ToolHandler", {}).get("tool", [])
        assert len(tool_services) > 0
        assert any("MockCLIToolService" in str(p) for p in tool_services)
        
        # Wise authority service
        wa_services = handlers.get("DeferHandler", {}).get("wise_authority", [])
        assert len(wa_services) > 0
        assert any("MockCLIWAService" in str(p) for p in wa_services)
