"""Test get_services_by_type method for redundancy and broadcasting."""

import pytest
from ciris_engine.registries.base import ServiceRegistry, Priority
from ciris_engine.schemas.foundational_schemas_v1 import ServiceType


class MockAuditService:
    """Mock audit service for testing"""
    def __init__(self, name: str):
        self.name = name
    
    async def log_event(self, event_type: str, event_data: dict) -> None:
        pass


class MockToolService:
    """Mock tool service for testing"""
    def __init__(self, name: str):
        self.name = name
        self.tools = {f"tool_{name}": {"description": f"Tool from {name}"}}
    
    async def get_available_tools(self) -> dict:
        return self.tools


@pytest.mark.asyncio
async def test_get_services_by_type_audit():
    """Test getting all audit services for broadcasting."""
    registry = ServiceRegistry()
    
    # Register 3 audit services with different priorities
    audit1 = MockAuditService("audit1")
    audit2 = MockAuditService("audit2")
    audit3 = MockAuditService("audit3")
    
    # Register globally
    registry.register_global(ServiceType.AUDIT, audit1, Priority.CRITICAL)
    registry.register_global(ServiceType.AUDIT, audit2, Priority.HIGH)
    registry.register_global(ServiceType.AUDIT, audit3, Priority.NORMAL)
    
    # Get all audit services
    audit_services = registry.get_services_by_type('audit')
    
    # Should return all 3 services
    assert len(audit_services) == 3
    assert audit1 in audit_services
    assert audit2 in audit_services
    assert audit3 in audit_services


@pytest.mark.asyncio
async def test_get_services_by_type_tool():
    """Test getting all tool services for aggregation."""
    registry = ServiceRegistry()
    
    # Register multiple tool services
    tool1 = MockToolService("discord")
    tool2 = MockToolService("cli")
    tool3 = MockToolService("core")
    
    # Mix of handler-specific and global registrations
    registry.register("ToolHandler", ServiceType.TOOL, tool1, Priority.HIGH)
    registry.register("ToolHandler", ServiceType.TOOL, tool2, Priority.NORMAL)
    registry.register_global(ServiceType.TOOL, tool3, Priority.HIGH)
    
    # Get all tool services
    tool_services = registry.get_services_by_type('tool')
    
    # Should return all 3 services
    assert len(tool_services) == 3
    assert tool1 in tool_services
    assert tool2 in tool_services
    assert tool3 in tool_services


@pytest.mark.asyncio
async def test_get_services_by_type_no_duplicates():
    """Test that the same service instance is not returned multiple times."""
    registry = ServiceRegistry()
    
    # Register the same service multiple times
    audit = MockAuditService("shared")
    
    # Register for different handlers
    registry.register("Handler1", ServiceType.AUDIT, audit, Priority.HIGH)
    registry.register("Handler2", ServiceType.AUDIT, audit, Priority.NORMAL)
    registry.register_global(ServiceType.AUDIT, audit, Priority.HIGH)
    
    # Get all audit services
    audit_services = registry.get_services_by_type('audit')
    
    # Should return only one instance
    assert len(audit_services) == 1
    assert audit_services[0] is audit


@pytest.mark.asyncio
async def test_get_services_by_type_with_enum():
    """Test that ServiceType enum can be passed directly."""
    registry = ServiceRegistry()
    
    audit = MockAuditService("test")
    registry.register_global(ServiceType.AUDIT, audit, Priority.HIGH)
    
    # Pass enum directly instead of string
    audit_services = registry.get_services_by_type(ServiceType.AUDIT)
    
    assert len(audit_services) == 1
    assert audit_services[0] is audit


@pytest.mark.asyncio
async def test_get_services_by_type_unknown():
    """Test handling of unknown service type."""
    registry = ServiceRegistry()
    
    # Try to get services of non-existent type
    services = registry.get_services_by_type('unknown_type')
    
    # Should return empty list
    assert services == []


@pytest.mark.asyncio
async def test_get_services_by_type_empty():
    """Test when no services are registered."""
    registry = ServiceRegistry()
    
    # Get services when none are registered
    audit_services = registry.get_services_by_type('audit')
    
    # Should return empty list
    assert audit_services == []