"""Unit tests for ServiceInitializer."""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, AsyncMock, patch, MagicMock, call
from datetime import datetime, timezone
from pathlib import Path

from ciris_engine.logic.runtime.service_initializer import ServiceInitializer
from ciris_engine.schemas.config.essential import EssentialConfig


class TestServiceInitializer:
    """Test cases for ServiceInitializer."""
    
    @pytest.fixture
    def temp_data_dir(self):
        """Create temporary data directory."""
        with tempfile.TemporaryDirectory() as temp_dir:
            yield temp_dir
    
    @pytest.fixture
    def mock_essential_config(self, temp_data_dir):
        """Create mock essential config."""
        config = Mock(spec=EssentialConfig)
        config.data_dir = temp_data_dir
        config.db_path = os.path.join(temp_data_dir, "test.db")
        config.log_level = "INFO"
        config.openai_api_key = "test-key"
        config.anthropic_api_key = None
        return config
    
    @pytest.fixture
    def service_initializer(self, mock_essential_config):
        """Create ServiceInitializer instance."""
        initializer = ServiceInitializer(
            essential_config=mock_essential_config,
            db_path=mock_essential_config.db_path,
            mock_llm=True
        )
        return initializer
    
    @pytest.mark.asyncio
    async def test_initialize_all(self, service_initializer):
        """Test initializing all services."""
        with patch.object(service_initializer, '_initialize_infrastructure') as mock_infra:
            with patch.object(service_initializer, '_initialize_database') as mock_db:
                with patch.object(service_initializer, '_initialize_memory') as mock_memory:
                    with patch.object(service_initializer, '_initialize_identity') as mock_identity:
                        with patch.object(service_initializer, '_initialize_security') as mock_security:
                            with patch.object(service_initializer, '_initialize_services') as mock_services:
                                with patch.object(service_initializer, '_verify_initialization') as mock_verify:
                                    
                                    await service_initializer.initialize_all()
                                    
                                    # Verify initialization sequence
                                    mock_infra.assert_called_once()
                                    mock_db.assert_called_once()
                                    mock_memory.assert_called_once()
                                    mock_identity.assert_called_once()
                                    mock_security.assert_called_once()
                                    mock_services.assert_called_once()
                                    mock_verify.assert_called_once()
    
    def test_initialize_infrastructure(self, service_initializer):
        """Test infrastructure services initialization."""
        service_initializer._initialize_infrastructure()
        
        # Should create time service
        assert service_initializer.time_service is not None
        assert hasattr(service_initializer.time_service, 'now')
        
        # Should create other infrastructure services
        assert service_initializer.shutdown_service is not None
        assert service_initializer.initialization_service is not None
        assert service_initializer.resource_monitor is not None
    
    def test_initialize_database(self, service_initializer):
        """Test database initialization."""
        # Create time service first
        service_initializer._initialize_infrastructure()
        
        # Initialize database
        service_initializer._initialize_database()
        
        # Database file should exist
        assert os.path.exists(service_initializer._db_path)
    
    @pytest.mark.asyncio
    async def test_initialize_memory(self, service_initializer):
        """Test memory services initialization."""
        # Initialize prerequisites
        service_initializer._initialize_infrastructure()
        service_initializer._initialize_database()
        
        # Initialize memory
        await service_initializer._initialize_memory()
        
        # Should create secrets and memory services
        assert service_initializer.secrets_service is not None
        assert service_initializer.memory_service is not None
        assert service_initializer.config_service is not None
        
        # Should create config accessor
        assert service_initializer.config_accessor is not None
    
    @pytest.mark.asyncio
    async def test_initialize_identity(self, service_initializer):
        """Test identity initialization."""
        # Initialize prerequisites
        service_initializer._initialize_infrastructure()
        service_initializer._initialize_database()
        await service_initializer._initialize_memory()
        
        # Mock memory service
        service_initializer.memory_service = Mock()
        service_initializer.memory_service.recall = AsyncMock(return_value=[])
        service_initializer.memory_service.memorize = AsyncMock()
        
        # Initialize identity
        await service_initializer._initialize_identity()
        
        # Should attempt to load/create identity
        service_initializer.memory_service.recall.assert_called()
    
    def test_initialize_security(self, service_initializer):
        """Test security services initialization."""
        # Initialize prerequisites
        service_initializer._initialize_infrastructure()
        
        # Mock registry
        with patch('ciris_engine.logic.runtime.service_initializer.ServiceRegistry') as mock_registry:
            service_initializer.registry = mock_registry.return_value
            
            # Initialize security
            service_initializer._initialize_security()
            
            # Should create wise authority service
            assert service_initializer.wise_authority_service is not None
            
            # Should register in registry
            service_initializer.registry.register_service.assert_called()
    
    def test_initialize_services(self, service_initializer):
        """Test remaining services initialization."""
        # Initialize prerequisites
        service_initializer._initialize_infrastructure()
        service_initializer.memory_service = Mock()
        service_initializer.registry = Mock()
        
        # Initialize services
        service_initializer._initialize_services()
        
        # Should create all graph services
        assert service_initializer.audit_service is not None
        assert service_initializer.telemetry_service is not None
        assert service_initializer.incident_service is not None
        assert service_initializer.tsdb_service is not None
        
        # Should create governance services
        assert service_initializer.visibility_service is not None
        
        # Should create special services
        assert service_initializer.self_configuration is not None
        assert service_initializer.adaptive_filter is not None
        assert service_initializer.task_scheduler is not None
    
    def test_initialize_llm_service_mock(self, service_initializer):
        """Test LLM service initialization with mock."""
        service_initializer.registry = Mock()
        
        # Initialize LLM (should use mock)
        service_initializer._initialize_llm_service()
        
        assert service_initializer.llm_service is not None
        # Should register in registry
        service_initializer.registry.register_service.assert_called_with(
            service_initializer.llm_service,
            "llm"
        )
    
    def test_initialize_llm_service_real(self, service_initializer):
        """Test LLM service initialization with real provider."""
        service_initializer._mock_llm = False
        service_initializer.registry = Mock()
        service_initializer._essential_config.openai_api_key = "test-key"
        
        with patch('ciris_engine.logic.runtime.service_initializer.LLMService') as mock_llm_class:
            mock_llm = Mock()
            mock_llm_class.return_value = mock_llm
            
            # Initialize LLM
            service_initializer._initialize_llm_service()
            
            assert service_initializer.llm_service is not None
            mock_llm_class.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_all(self, service_initializer):
        """Test shutting down all services."""
        # Create mock services
        mock_service1 = Mock()
        mock_service1.stop = AsyncMock()
        mock_service2 = Mock()
        mock_service2.stop = AsyncMock()
        
        service_initializer._all_services = {
            "service1": mock_service1,
            "service2": mock_service2
        }
        
        # Shutdown
        await service_initializer.shutdown_all()
        
        # All services should be stopped
        mock_service1.stop.assert_called_once()
        mock_service2.stop.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_shutdown_with_error(self, service_initializer):
        """Test shutdown handling service errors."""
        # Create service that errors on stop
        mock_service = Mock()
        mock_service.stop = AsyncMock(side_effect=Exception("Stop error"))
        
        service_initializer._all_services = {"service": mock_service}
        
        # Should not raise
        await service_initializer.shutdown_all()
        
        # Service stop should have been attempted
        mock_service.stop.assert_called_once()
    
    def test_get_all_services(self, service_initializer):
        """Test getting all services."""
        # Add some services
        service_initializer.time_service = Mock()
        service_initializer.memory_service = Mock()
        
        services = service_initializer.get_all_services()
        
        assert "time_service" in services
        assert "memory_service" in services
        assert services["time_service"] == service_initializer.time_service
        assert services["memory_service"] == service_initializer.memory_service
    
    def test_verify_initialization(self, service_initializer):
        """Test initialization verification."""
        # Set up required services
        service_initializer.time_service = Mock()
        service_initializer.memory_service = Mock()
        service_initializer.secrets_service = Mock()
        service_initializer.wise_authority_service = Mock()
        service_initializer.config_accessor = Mock()
        
        # Should not raise
        service_initializer._verify_initialization()
    
    def test_verify_initialization_missing_service(self, service_initializer):
        """Test verification with missing service."""
        # Missing time_service
        service_initializer.memory_service = Mock()
        
        with pytest.raises(RuntimeError) as exc_info:
            service_initializer._verify_initialization()
        
        assert "time_service" in str(exc_info.value)
    
    def test_service_count(self, service_initializer):
        """Test that exactly 19 services are created."""
        # Initialize all services
        service_initializer._initialize_infrastructure()
        service_initializer.secrets_service = Mock()  # Mock to avoid file operations
        service_initializer.memory_service = Mock()
        service_initializer.registry = Mock()
        
        service_initializer._initialize_security()
        service_initializer._initialize_services()
        service_initializer._initialize_llm_service()
        
        # Count services (excluding config_accessor and registry)
        services = service_initializer.get_all_services()
        service_count = sum(
            1 for name, svc in services.items() 
            if svc is not None and name not in ['config_accessor', 'registry']
        )
        
        assert service_count == 19
    
    @pytest.mark.asyncio
    async def test_initialization_order_dependencies(self, service_initializer):
        """Test that services are initialized in correct dependency order."""
        calls = []
        
        # Mock each initialization phase to track order
        async def track_call(phase):
            calls.append(phase)
        
        with patch.object(service_initializer, '_initialize_infrastructure', 
                         side_effect=lambda: track_call('infrastructure')):
            with patch.object(service_initializer, '_initialize_database',
                             side_effect=lambda: track_call('database')):
                with patch.object(service_initializer, '_initialize_memory',
                                 side_effect=lambda: asyncio.create_task(track_call('memory'))):
                    with patch.object(service_initializer, '_initialize_identity',
                                     side_effect=lambda: asyncio.create_task(track_call('identity'))):
                        with patch.object(service_initializer, '_initialize_security',
                                         side_effect=lambda: track_call('security')):
                            with patch.object(service_initializer, '_initialize_services',
                                             side_effect=lambda: track_call('services')):
                                with patch.object(service_initializer, '_verify_initialization',
                                                 side_effect=lambda: track_call('verify')):
                                    
                                    await service_initializer.initialize_all()
                                    await asyncio.sleep(0.1)  # Let async tasks complete
        
        # Verify order
        assert calls.index('infrastructure') < calls.index('database')
        assert calls.index('database') < calls.index('memory')
        assert calls.index('memory') < calls.index('identity')
        assert calls.index('identity') < calls.index('security')
        assert calls.index('security') < calls.index('services')
        assert calls.index('services') < calls.index('verify')