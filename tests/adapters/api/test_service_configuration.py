"""
Tests for API service configuration.
"""
import pytest
from typing import List, Tuple, Union, Optional

from ciris_engine.logic.adapters.api.service_configuration import (
    ServiceMapping, ApiServiceConfiguration, AdapterService
)


class TestServiceMapping:
    """Tests for ServiceMapping dataclass."""
    
    def test_service_mapping_defaults(self):
        """Test ServiceMapping with default app_state_names."""
        mapping = ServiceMapping("test_service", description="Test service")
        assert mapping.runtime_attr == "test_service"
        assert mapping.app_state_names == ["test_service"]
        assert mapping.special_handler is None
        assert mapping.description == "Test service"
    
    def test_service_mapping_with_explicit_names(self):
        """Test ServiceMapping with explicit app_state_names."""
        mapping = ServiceMapping(
            "wa_auth_system",
            app_state_names=["wise_authority_service", "wa_service"],
            description="Wise Authority"
        )
        assert mapping.runtime_attr == "wa_auth_system"
        assert mapping.app_state_names == ["wise_authority_service", "wa_service"]
    
    def test_service_mapping_with_handler(self):
        """Test ServiceMapping with special handler."""
        mapping = ServiceMapping(
            "auth_service",
            special_handler="_handle_auth_service",
            description="Auth service"
        )
        assert mapping.special_handler == "_handle_auth_service"


class TestApiServiceConfiguration:
    """Tests for ApiServiceConfiguration."""
    
    def test_service_categories_exist(self):
        """Test that all service categories are defined."""
        assert hasattr(ApiServiceConfiguration, 'GRAPH_SERVICES')
        assert hasattr(ApiServiceConfiguration, 'INFRASTRUCTURE_SERVICES')
        assert hasattr(ApiServiceConfiguration, 'GOVERNANCE_SERVICES')
        assert hasattr(ApiServiceConfiguration, 'RUNTIME_SERVICES')
        assert hasattr(ApiServiceConfiguration, 'TOOL_SERVICES')
        assert hasattr(ApiServiceConfiguration, 'INFRASTRUCTURE_COMPONENTS')
    
    def test_service_counts(self):
        """Test that service counts match expected values."""
        assert len(ApiServiceConfiguration.GRAPH_SERVICES) == 6
        assert len(ApiServiceConfiguration.INFRASTRUCTURE_SERVICES) == 7
        assert len(ApiServiceConfiguration.GOVERNANCE_SERVICES) == 4
        assert len(ApiServiceConfiguration.RUNTIME_SERVICES) == 3
        assert len(ApiServiceConfiguration.TOOL_SERVICES) == 1
        assert len(ApiServiceConfiguration.INFRASTRUCTURE_COMPONENTS) == 1
    
    def test_get_current_mappings_as_tuples(self):
        """Test the get_current_mappings_as_tuples method."""
        mappings = ApiServiceConfiguration.get_current_mappings_as_tuples()
        
        # Should return list of tuples
        assert isinstance(mappings, list)
        assert len(mappings) == 22  # 6+7+4+3+1+1
        
        # Check tuple format
        for mapping in mappings:
            assert isinstance(mapping, tuple)
            assert len(mapping) == 3
            runtime_attr, app_attrs, handler = mapping
            assert isinstance(runtime_attr, str)
            assert isinstance(app_attrs, (str, list))
            assert handler is None or isinstance(handler, str)
    
    def test_specific_service_mappings(self):
        """Test specific important service mappings."""
        mappings = ApiServiceConfiguration.get_current_mappings_as_tuples()
        mapping_dict = {m[0]: m for m in mappings}
        
        # Check memory service
        assert "memory_service" in mapping_dict
        assert mapping_dict["memory_service"][1] == "memory_service"
        
        # Check wise authority - returns string when only one name
        assert "wa_auth_system" in mapping_dict
        assert mapping_dict["wa_auth_system"][1] == "wise_authority_service"
        
        # Check authentication with handler
        assert "authentication_service" in mapping_dict
        assert mapping_dict["authentication_service"][2] == "_handle_auth_service"
        
        # Check runtime control service mapping
        assert "runtime_control_service" in mapping_dict
        assert mapping_dict["runtime_control_service"][1] == "main_runtime_control_service"
        
        # Check service registry
        assert "service_registry" in mapping_dict
        assert mapping_dict["service_registry"][1] == "service_registry"
    
    def test_adapter_created_services(self):
        """Test adapter-created services configuration."""
        assert hasattr(ApiServiceConfiguration, 'ADAPTER_CREATED_SERVICES')
        services = ApiServiceConfiguration.ADAPTER_CREATED_SERVICES
        
        assert len(services) == 3
        assert all(isinstance(s, AdapterService) for s in services)
        
        # Check specific services
        service_names = [s.attr_name for s in services]
        assert "runtime_control" in service_names
        assert "communication" in service_names
        assert "tool_service" in service_names


class TestAdapterService:
    """Tests for AdapterService dataclass."""
    
    def test_adapter_service_creation(self):
        """Test AdapterService creation."""
        service = AdapterService(
            "test_attr",
            "test_app_state",
            "Test description"
        )
        assert service.attr_name == "test_attr"
        assert service.app_state_name == "test_app_state"
        assert service.description == "Test description"


class TestServiceConfigurationIntegration:
    """Integration tests for service configuration."""
    
    def test_no_duplicate_runtime_attrs(self):
        """Test that there are no duplicate runtime attributes."""
        mappings = ApiServiceConfiguration.get_current_mappings_as_tuples()
        runtime_attrs = [m[0] for m in mappings]
        assert len(runtime_attrs) == len(set(runtime_attrs)), "Duplicate runtime attributes found"
    
    def test_all_services_have_descriptions(self):
        """Test that all services have descriptions."""
        all_services = (
            ApiServiceConfiguration.GRAPH_SERVICES +
            ApiServiceConfiguration.INFRASTRUCTURE_SERVICES +
            ApiServiceConfiguration.GOVERNANCE_SERVICES +
            ApiServiceConfiguration.RUNTIME_SERVICES +
            ApiServiceConfiguration.TOOL_SERVICES +
            ApiServiceConfiguration.INFRASTRUCTURE_COMPONENTS
        )
        
        for service in all_services:
            assert service.description, f"Service {service.runtime_attr} missing description"
    
    def test_empty_app_state_names_uses_runtime_attr(self):
        """Test that empty app_state_names defaults to runtime_attr."""
        # Create a mapping with empty list
        mapping = ServiceMapping("test_service", app_state_names=[], description="Test")
        # Should default to runtime_attr in a list
        assert mapping.app_state_names == ["test_service"]
    
    def test_mappings_handle_all_tuple_positions(self):
        """Test that all tuple positions are correctly populated."""
        mappings = ApiServiceConfiguration.get_current_mappings_as_tuples()
        
        for runtime_attr, app_attrs, handler in mappings:
            # Runtime attr should always be a non-empty string
            assert isinstance(runtime_attr, str)
            assert runtime_attr
            
            # App attrs should be string or list of strings
            if isinstance(app_attrs, list):
                assert all(isinstance(attr, str) for attr in app_attrs)
                assert all(attr for attr in app_attrs)  # No empty strings
            else:
                assert isinstance(app_attrs, str)
                assert app_attrs  # Not empty
            
            # Handler should be None or a string
            if handler is not None:
                assert isinstance(handler, str)
                assert handler  # Not empty
    
    def test_all_categories_have_services(self):
        """Test that no service category is empty."""
        assert len(ApiServiceConfiguration.GRAPH_SERVICES) > 0
        assert len(ApiServiceConfiguration.INFRASTRUCTURE_SERVICES) > 0
        assert len(ApiServiceConfiguration.GOVERNANCE_SERVICES) > 0
        assert len(ApiServiceConfiguration.RUNTIME_SERVICES) > 0
        assert len(ApiServiceConfiguration.TOOL_SERVICES) > 0
        assert len(ApiServiceConfiguration.INFRASTRUCTURE_COMPONENTS) > 0