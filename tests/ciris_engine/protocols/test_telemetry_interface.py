"""
Tests for Telemetry Interface Protocol

Tests the telemetry interface protocol definitions, data models, and validation
to ensure proper structure and compliance across the telemetry system.
"""

import pytest
from datetime import datetime, timezone
from typing import Dict, Any, List
from pydantic import ValidationError

from ciris_engine.protocols.telemetry_interface import (
    TelemetryInterface,
    ProcessorControlInterface, 
    TelemetrySnapshot,
    AdapterInfo,
    ServiceInfo,
    ProcessorState,
    ConfigurationSnapshot
)
from ciris_engine.schemas.telemetry_schemas_v1 import CompactTelemetry


class TestTelemetryDataModels:
    """Test suite for telemetry data models and validation"""
    
    def test_adapter_info_creation(self):
        """Test AdapterInfo model creation and validation"""
        adapter = AdapterInfo(
            name="TestAdapter",
            type="test",
            status="active",
            capabilities=["test_capability", "another_capability"],
            metadata={"key": "value", "number": 42}
        )
        
        assert adapter.name == "TestAdapter"
        assert adapter.type == "test"
        assert adapter.status == "active"
        assert len(adapter.capabilities) == 2
        assert adapter.metadata["key"] == "value"
        assert adapter.metadata["number"] == 42
    
    def test_adapter_info_defaults(self):
        """Test AdapterInfo with default values"""
        adapter = AdapterInfo(
            name="MinimalAdapter",
            type="minimal", 
            status="inactive"
        )
        
        assert adapter.capabilities == []
        assert adapter.metadata == {}
    
    def test_adapter_info_validation_error(self):
        """Test AdapterInfo validation with invalid data"""
        with pytest.raises(ValidationError):
            AdapterInfo(
                # Missing required fields
                name="Test"
                # Missing type and status
            )
    
    def test_service_info_creation(self):
        """Test ServiceInfo model creation and validation"""
        service = ServiceInfo(
            name="LLMService",
            service_type="llm_service",
            handler="speak_handler",
            priority="HIGH",
            capabilities=["text_generation", "code_completion"],
            status="healthy",
            circuit_breaker_state="closed",
            metadata={"model": "gpt-4", "version": "1.0"},
            instance_id="service_123"
        )
        
        assert service.name == "LLMService"
        assert service.service_type == "llm_service"
        assert service.handler == "speak_handler"
        assert service.priority == "HIGH"
        assert service.status == "healthy"
        assert service.circuit_breaker_state == "closed"
        assert service.metadata["model"] == "gpt-4"
        assert service.instance_id == "service_123"
    
    def test_service_info_global_service(self):
        """Test ServiceInfo for global service (no handler)"""
        service = ServiceInfo(
            name="GlobalService",
            service_type="audit_service",
            handler=None,  # Global service
            priority="MEDIUM",
            capabilities=["audit_logging"],
            status="healthy",
            circuit_breaker_state="closed",
            instance_id="global_service_123"
        )
        
        assert service.handler is None
        assert service.service_type == "audit_service"
    
    def test_processor_state_creation(self):
        """Test ProcessorState model creation"""
        now = datetime.now(timezone.utc)
        
        state = ProcessorState(
            is_running=True,
            current_round=42,
            thoughts_pending=5,
            thoughts_processing=2,
            processor_mode="work",
            last_activity=now
        )
        
        assert state.is_running == True
        assert state.current_round == 42
        assert state.thoughts_pending == 5
        assert state.thoughts_processing == 2
        assert state.processor_mode == "work"
        assert state.last_activity == now
    
    def test_processor_state_defaults(self):
        """Test ProcessorState with default values"""
        state = ProcessorState()
        
        assert state.is_running == False
        assert state.current_round == 0
        assert state.thoughts_pending == 0
        assert state.thoughts_processing == 0
        assert state.processor_mode == "unknown"
        assert state.last_activity is None
    
    def test_configuration_snapshot_creation(self):
        """Test ConfigurationSnapshot model creation"""
        config = ConfigurationSnapshot(
            profile_name="production_profile",
            startup_channel_id="channel_456",
            llm_model="gpt-4",
            llm_base_url="https://api.openai.com/v1",
            adapter_modes=["discord", "cli"],
            debug_mode=False
        )
        
        assert config.profile_name == "production_profile"
        assert config.startup_channel_id == "channel_456"
        assert config.llm_model == "gpt-4"
        assert config.llm_base_url == "https://api.openai.com/v1"
        assert "discord" in config.adapter_modes
        assert config.debug_mode == False
    
    def test_configuration_snapshot_minimal(self):
        """Test ConfigurationSnapshot with minimal required data"""
        config = ConfigurationSnapshot(profile_name="test")
        
        assert config.profile_name == "test"
        assert config.startup_channel_id is None
        assert config.llm_model is None
        assert config.adapter_modes == []
        assert config.debug_mode == False
    
    def test_telemetry_snapshot_creation(self):
        """Test TelemetrySnapshot comprehensive model creation"""
        basic_telemetry = CompactTelemetry(
            thoughts_24h=150,
            uptime_hours=24.5,
            messages_processed_24h=300
        )
        
        adapters = [
            AdapterInfo(name="Discord", type="discord", status="active"),
            AdapterInfo(name="CLI", type="cli", status="inactive")
        ]
        
        services = [
            ServiceInfo(
                name="LLM", 
                service_type="llm_service",
                handler="speak_handler",
                priority="HIGH",
                capabilities=["generation"],
                status="healthy",
                circuit_breaker_state="closed",
                instance_id="llm_service_123"
            )
        ]
        
        processor_state = ProcessorState(
            is_running=True,
            current_round=10,
            thoughts_pending=3
        )
        
        configuration = ConfigurationSnapshot(profile_name="test_profile")
        
        snapshot = TelemetrySnapshot(
            basic_telemetry=basic_telemetry,
            adapters=adapters,
            services=services,
            processor_state=processor_state,
            configuration=configuration,
            runtime_uptime_seconds=88200.0,
            memory_usage_mb=512.0,
            cpu_usage_percent=25.5,
            overall_health="healthy",
            health_details={"adapters": "all_active"}
        )
        
        assert snapshot.basic_telemetry.thoughts_24h == 150
        assert len(snapshot.adapters) == 2
        assert len(snapshot.services) == 1
        assert snapshot.processor_state.is_running == True
        assert snapshot.configuration.profile_name == "test_profile"
        assert snapshot.runtime_uptime_seconds == 88200.0
        assert snapshot.memory_usage_mb == 512.0
        assert snapshot.cpu_usage_percent == 25.5
        assert snapshot.overall_health == "healthy"
        assert snapshot.health_details["adapters"] == "all_active"
    
    def test_telemetry_snapshot_defaults(self):
        """Test TelemetrySnapshot with default values"""
        basic_telemetry = CompactTelemetry()
        processor_state = ProcessorState()
        configuration = ConfigurationSnapshot(profile_name="default")
        
        snapshot = TelemetrySnapshot(
            basic_telemetry=basic_telemetry,
            processor_state=processor_state,
            configuration=configuration,
            overall_health="unknown"
        )
        
        assert snapshot.adapters == []
        assert snapshot.services == []
        assert snapshot.runtime_uptime_seconds == 0.0
        assert snapshot.memory_usage_mb == 0.0
        assert snapshot.cpu_usage_percent == 0.0
        assert snapshot.health_details == {}
    
    def test_telemetry_snapshot_json_serialization(self):
        """Test that TelemetrySnapshot can be serialized to JSON"""
        basic_telemetry = CompactTelemetry(thoughts_24h=100)
        processor_state = ProcessorState(is_running=True)
        configuration = ConfigurationSnapshot(profile_name="json_test")
        
        snapshot = TelemetrySnapshot(
            basic_telemetry=basic_telemetry,
            processor_state=processor_state,
            configuration=configuration,
            overall_health="healthy"
        )
        
        # Test JSON serialization
        json_data = snapshot.model_dump()
        
        assert isinstance(json_data, dict)
        assert json_data["basic_telemetry"]["thoughts_24h"] == 100
        assert json_data["processor_state"]["is_running"] == True
        assert json_data["configuration"]["profile_name"] == "json_test"
        assert json_data["overall_health"] == "healthy"
    
    def test_telemetry_snapshot_datetime_handling(self):
        """Test datetime handling in telemetry models"""
        now = datetime.now(timezone.utc)
        
        processor_state = ProcessorState(
            is_running=True,
            last_activity=now
        )
        
        basic_telemetry = CompactTelemetry()
        configuration = ConfigurationSnapshot(profile_name="datetime_test")
        
        snapshot = TelemetrySnapshot(
            basic_telemetry=basic_telemetry,
            processor_state=processor_state,
            configuration=configuration,
            overall_health="healthy"
        )
        
        # Verify datetime is preserved
        assert snapshot.processor_state.last_activity == now
        
        # Test JSON serialization with datetime
        json_data = snapshot.model_dump()
        assert "last_activity" in json_data["processor_state"]
    
    def test_complex_metadata_handling(self):
        """Test handling of complex metadata structures"""
        complex_metadata = {
            "nested": {
                "level1": {
                    "level2": "deep_value"
                }
            },
            "list": ["item1", "item2", "item3"],
            "mixed": {
                "string": "value",
                "number": 42,
                "boolean": True,
                "null": None
            }
        }
        
        adapter = AdapterInfo(
            name="ComplexAdapter",
            type="complex",
            status="active",
            metadata=complex_metadata
        )
        
        # Verify complex metadata is preserved
        assert adapter.metadata["nested"]["level1"]["level2"] == "deep_value"
        assert adapter.metadata["list"] == ["item1", "item2", "item3"]
        assert adapter.metadata["mixed"]["number"] == 42
        assert adapter.metadata["mixed"]["boolean"] == True
        assert adapter.metadata["mixed"]["null"] is None
    
    def test_large_capabilities_list(self):
        """Test handling of large capabilities lists"""
        large_capabilities = [f"capability_{i}" for i in range(100)]
        
        service = ServiceInfo(
            name="CapabilityRichService",
            service_type="multi_service",
            handler="test_handler",
            priority="MEDIUM",
            capabilities=large_capabilities,
            status="healthy",
            circuit_breaker_state="closed",
            instance_id="capability_service_123"
        )
        
        assert len(service.capabilities) == 100
        assert "capability_50" in service.capabilities
        assert service.capabilities[0] == "capability_0"
        assert service.capabilities[-1] == "capability_99"
    
    def test_health_status_values(self):
        """Test various health status values"""
        health_statuses = ["healthy", "degraded", "critical", "unknown", "error"]
        
        for status in health_statuses:
            snapshot = TelemetrySnapshot(
                basic_telemetry=CompactTelemetry(),
                processor_state=ProcessorState(),
                configuration=ConfigurationSnapshot(profile_name="test"),
                overall_health=status
            )
            assert snapshot.overall_health == status
    
    def test_edge_case_values(self):
        """Test edge case values in telemetry models"""
        # Test very large numbers
        snapshot = TelemetrySnapshot(
            basic_telemetry=CompactTelemetry(),
            processor_state=ProcessorState(),
            configuration=ConfigurationSnapshot(profile_name="edge_test"),
            runtime_uptime_seconds=999999999.99,
            memory_usage_mb=999999.99,
            cpu_usage_percent=100.0,
            overall_health="healthy"
        )
        
        assert snapshot.runtime_uptime_seconds == 999999999.99
        assert snapshot.memory_usage_mb == 999999.99
        assert snapshot.cpu_usage_percent == 100.0
        
        # Test zero values
        zero_snapshot = TelemetrySnapshot(
            basic_telemetry=CompactTelemetry(),
            processor_state=ProcessorState(),
            configuration=ConfigurationSnapshot(profile_name="zero_test"),
            runtime_uptime_seconds=0.0,
            memory_usage_mb=0.0,
            cpu_usage_percent=0.0,
            overall_health="healthy"
        )
        
        assert zero_snapshot.runtime_uptime_seconds == 0.0
        assert zero_snapshot.memory_usage_mb == 0.0
        assert zero_snapshot.cpu_usage_percent == 0.0


class MockTelemetryInterface(TelemetryInterface):
    """Mock implementation of TelemetryInterface for testing"""
    
    async def get_telemetry_snapshot(self) -> TelemetrySnapshot:
        return TelemetrySnapshot(
            basic_telemetry=CompactTelemetry(),
            processor_state=ProcessorState(),
            configuration=ConfigurationSnapshot(profile_name="mock"),
            overall_health="healthy"
        )
    
    async def get_adapters_info(self) -> List[AdapterInfo]:
        return []
    
    async def get_services_info(self) -> List[ServiceInfo]:
        return []
    
    async def get_processor_state(self) -> ProcessorState:
        return ProcessorState()
    
    async def get_configuration_snapshot(self) -> ConfigurationSnapshot:
        return ConfigurationSnapshot(profile_name="mock")
    
    async def get_health_status(self) -> Dict[str, Any]:
        return {"overall": "healthy"}
    
    async def record_metric(self, metric_name: str, value: float, tags: Dict[str, str] = None) -> None:
        pass
    
    async def get_metrics_history(self, metric_name: str, hours: int = 24) -> List[Dict[str, Any]]:
        return []


class MockProcessorControlInterface(ProcessorControlInterface):
    """Mock implementation of ProcessorControlInterface for testing"""
    
    async def single_step(self) -> Dict[str, Any]:
        return {"status": "completed"}
    
    async def pause_processing(self) -> bool:
        return True
    
    async def resume_processing(self) -> bool:
        return True
    
    async def get_processing_queue_status(self) -> Dict[str, Any]:
        return {"size": 0}


class TestTelemetryInterfaces:
    """Test suite for telemetry interface compliance"""
    
    @pytest.mark.asyncio
    async def test_telemetry_interface_implementation(self):
        """Test that TelemetryInterface can be implemented"""
        impl = MockTelemetryInterface()
        
        # Test all interface methods
        snapshot = await impl.get_telemetry_snapshot()
        assert isinstance(snapshot, TelemetrySnapshot)
        
        adapters = await impl.get_adapters_info()
        assert isinstance(adapters, list)
        
        services = await impl.get_services_info()
        assert isinstance(services, list)
        
        state = await impl.get_processor_state()
        assert isinstance(state, ProcessorState)
        
        config = await impl.get_configuration_snapshot()
        assert isinstance(config, ConfigurationSnapshot)
        
        health = await impl.get_health_status()
        assert isinstance(health, dict)
        
        # Test metric operations
        await impl.record_metric("test", 1.0, {"tag": "value"})
        
        history = await impl.get_metrics_history("test", 24)
        assert isinstance(history, list)
    
    @pytest.mark.asyncio
    async def test_processor_control_interface_implementation(self):
        """Test that ProcessorControlInterface can be implemented"""
        impl = MockProcessorControlInterface()
        
        # Test processor control methods
        result = await impl.single_step()
        assert isinstance(result, dict)
        assert "status" in result
        
        assert await impl.pause_processing() == True
        assert await impl.resume_processing() == True
        
        queue_status = await impl.get_processing_queue_status()
        assert isinstance(queue_status, dict)
    
    def test_interface_method_signatures(self):
        """Test that interface methods have correct signatures"""
        # This test ensures that the abstract methods are properly defined
        # and would catch signature changes that break implementations
        
        import inspect
        from ciris_engine.protocols.telemetry_interface import TelemetryInterface, ProcessorControlInterface
        
        # Test TelemetryInterface methods
        telemetry_methods = [
            'get_telemetry_snapshot',
            'get_adapters_info', 
            'get_services_info',
            'get_processor_state',
            'get_configuration_snapshot',
            'get_health_status',
            'record_metric',
            'get_metrics_history'
        ]
        
        for method_name in telemetry_methods:
            assert hasattr(TelemetryInterface, method_name)
            method = getattr(TelemetryInterface, method_name)
            assert inspect.iscoroutinefunction(method)
        
        # Test ProcessorControlInterface methods
        processor_methods = [
            'single_step',
            'pause_processing',
            'resume_processing', 
            'get_processing_queue_status'
        ]
        
        for method_name in processor_methods:
            assert hasattr(ProcessorControlInterface, method_name)
            method = getattr(ProcessorControlInterface, method_name)
            assert inspect.iscoroutinefunction(method)