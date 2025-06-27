"""Unit tests for GraphAuditService."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional

from ciris_engine.logic.services.graph.audit_service import GraphAuditService
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.nodes import AuditEntry
from ciris_engine.schemas.services.graph.audit import AuditEventData, VerificationReport
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus


class TestGraphAuditService:
    """Test cases for GraphAuditService."""
    
    @pytest.fixture
    def mock_time_service(self):
        """Create mock time service."""
        current_time = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        return Mock(
            now=Mock(return_value=current_time),
            now_iso=Mock(return_value=current_time.isoformat())
        )
    
    @pytest.fixture
    def mock_memory_bus(self):
        """Create mock memory bus."""
        bus = Mock()
        bus.memorize = AsyncMock()
        bus.recall = AsyncMock(return_value=[])
        bus.search = AsyncMock(return_value=[])
        return bus
    
    @pytest.fixture
    def audit_service(self, mock_time_service, mock_memory_bus):
        """Create GraphAuditService instance."""
        service = GraphAuditService(
            memory_bus=mock_memory_bus,
            time_service=mock_time_service,
            retention_days=30
        )
        return service
    
    @pytest.mark.asyncio
    async def test_start_stop(self, audit_service):
        """Test service start and stop."""
        # Start
        await audit_service.start()
        assert audit_service._running is True
        
        # Stop
        await audit_service.stop()
        assert audit_service._running is False
    
    @pytest.mark.asyncio
    async def test_audit_event(self, audit_service, mock_memory_bus):
        """Test auditing an event."""
        await audit_service.start()
        
        # Audit an event
        await audit_service.audit_event(
            event_type=AuditEventType.SERVICE_START,
            service_name="TestService",
            details={"version": "1.0.0"},
            severity=AuditSeverity.INFO
        )
        
        # Should create and store audit entry
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert isinstance(node, GraphNode)
        assert node.type == NodeType.AUDIT
        # Check the audit entry in attributes
        assert node.attributes['event_type'] == AuditEventType.SERVICE_START.value
        assert node.attributes['service_name'] == "TestService"
        assert node.attributes['severity'] == AuditSeverity.INFO.value
    
    @pytest.mark.asyncio
    async def test_audit_authentication(self, audit_service, mock_memory_bus):
        """Test auditing authentication events."""
        await audit_service.start()
        
        # Audit successful auth
        await audit_service.audit_authentication(
            user_id="user123",
            success=True,
            method="token",
            ip_address="192.168.1.1"
        )
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert node.attributes['event_type'] == AuditEventType.AUTH_SUCCESS.value
        assert node.attributes['user_id'] == "user123"
        assert node.attributes['details']['method'] == "token"
        assert node.attributes['details']['ip_address'] == "192.168.1.1"
    
    @pytest.mark.asyncio
    async def test_audit_authentication_failure(self, audit_service, mock_memory_bus):
        """Test auditing failed authentication."""
        await audit_service.start()
        
        # Audit failed auth
        await audit_service.audit_authentication(
            user_id="user123",
            success=False,
            method="password",
            ip_address="192.168.1.1",
            reason="Invalid credentials"
        )
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert node.attributes['event_type'] == AuditEventType.AUTH_FAILURE.value
        assert node.attributes['severity'] == AuditSeverity.WARNING.value
        assert node.attributes['details']['reason'] == "Invalid credentials"
    
    @pytest.mark.asyncio
    async def test_audit_configuration_change(self, audit_service, mock_memory_bus):
        """Test auditing configuration changes."""
        await audit_service.start()
        
        await audit_service.audit_configuration_change(
            service_name="ConfigService",
            config_key="max_retries",
            old_value="3",
            new_value="5",
            changed_by="admin"
        )
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert node.attributes['event_type'] == AuditEventType.CONFIG_CHANGE.value
        assert node.attributes['service_name'] == "ConfigService"
        assert node.attributes['details']['config_key'] == "max_retries"
        assert node.attributes['details']['old_value'] == "3"
        assert node.attributes['details']['new_value'] == "5"
    
    @pytest.mark.asyncio
    async def test_audit_data_access(self, audit_service, mock_memory_bus):
        """Test auditing data access events."""
        await audit_service.start()
        
        await audit_service.audit_data_access(
            user_id="user123",
            resource_type="patient_record",
            resource_id="12345",
            action="read",
            success=True
        )
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert node.attributes['event_type'] == AuditEventType.DATA_ACCESS.value
        assert node.attributes['user_id'] == "user123"
        assert node.attributes['details']['resource_type'] == "patient_record"
        assert node.attributes['details']['resource_id'] == "12345"
        assert node.attributes['details']['action'] == "read"
    
    @pytest.mark.asyncio
    async def test_audit_error(self, audit_service, mock_memory_bus):
        """Test auditing error events."""
        await audit_service.start()
        
        await audit_service.audit_error(
            service_name="DataProcessor",
            error_type="ValidationError",
            error_message="Invalid input format",
            stack_trace="File x, line y..."
        )
        
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        assert node.attributes['event_type'] == AuditEventType.ERROR.value
        assert node.attributes['severity'] == AuditSeverity.ERROR.value
        assert node.attributes['service_name'] == "DataProcessor"
        assert node.attributes['details']['error_type'] == "ValidationError"
    
    @pytest.mark.asyncio
    async def test_query_audit_log(self, audit_service, mock_memory_bus, mock_time_service):
        """Test querying audit log."""
        await audit_service.start()
        
        # Mock some audit entries
        mock_entries = [
            GraphNode(
                id="audit1",
                type=NodeType.AUDIT,
                scope=GraphScope.LOCAL,
                attributes={
                    "event_type": AuditEventType.SERVICE_START.value,
                    "service_name": "Service1",
                    "timestamp": mock_time_service.now_iso(),
                    "severity": AuditSeverity.INFO.value
                }
            ),
            GraphNode(
                id="audit2",
                type=NodeType.AUDIT,
                scope=GraphScope.LOCAL,
                attributes={
                    "event_type": AuditEventType.ERROR.value,
                    "service_name": "Service2",
                    "timestamp": mock_time_service.now_iso(),
                    "severity": AuditSeverity.ERROR.value
                }
            )
        ]
        
        mock_memory_bus.search.return_value = mock_entries
        
        # Query all events
        entries = await audit_service.query_audit_log()
        
        assert len(entries) == 2
        assert all(isinstance(e, AuditEntry) for e in entries)
        assert entries[0].event_type == AuditEventType.SERVICE_START
        assert entries[1].event_type == AuditEventType.ERROR
    
    @pytest.mark.asyncio
    async def test_query_audit_log_with_filters(self, audit_service, mock_memory_bus):
        """Test querying audit log with filters."""
        await audit_service.start()
        
        # Query with filters
        await audit_service.query_audit_log(
            event_type=AuditEventType.AUTH_FAILURE,
            service_name="AuthService",
            start_time=datetime.now(timezone.utc) - timedelta(hours=1),
            end_time=datetime.now(timezone.utc)
        )
        
        # Should search with appropriate query
        mock_memory_bus.search.assert_called_once()
        call_args = mock_memory_bus.search.call_args[0]
        query = call_args[0]
        
        assert "type:audit" in query
        assert "event_type:AUTH_FAILURE" in query
        assert "service_name:AuthService" in query
    
    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, audit_service, mock_memory_bus, mock_time_service):
        """Test cleanup of old audit entries."""
        await audit_service.start()
        
        # Mock old entries
        old_time = (mock_time_service.now() - timedelta(days=35)).isoformat()
        recent_time = (mock_time_service.now() - timedelta(days=5)).isoformat()
        
        mock_entries = [
            GraphNode(
                id="old_audit",
                type=NodeType.AUDIT,
                scope=GraphScope.LOCAL,
                attributes={"timestamp": old_time}
            ),
            GraphNode(
                id="recent_audit",
                type=NodeType.AUDIT,
                scope=GraphScope.LOCAL,
                attributes={"timestamp": recent_time}
            )
        ]
        
        mock_memory_bus.search.return_value = mock_entries
        mock_memory_bus.forget = AsyncMock()
        
        # Run cleanup
        cleaned = await audit_service.cleanup_old_entries()
        
        assert cleaned == 1
        # Should only delete the old entry
        mock_memory_bus.forget.assert_called_once_with(node_id="old_audit")
    
    @pytest.mark.asyncio
    async def test_get_audit_statistics(self, audit_service, mock_memory_bus):
        """Test getting audit statistics."""
        await audit_service.start()
        
        # Mock entries for stats
        mock_entries = [
            GraphNode(
                id=f"audit{i}",
                type=NodeType.AUDIT,
                scope=GraphScope.LOCAL,
                attributes={
                    "event_type": AuditEventType.SERVICE_START.value if i % 2 == 0 
                                else AuditEventType.ERROR.value,
                    "severity": AuditSeverity.INFO.value if i % 2 == 0 
                              else AuditSeverity.ERROR.value,
                    "service_name": f"Service{i % 3}"
                }
            )
            for i in range(10)
        ]
        
        mock_memory_bus.search.return_value = mock_entries
        
        stats = await audit_service.get_audit_statistics(
            start_time=datetime.now(timezone.utc) - timedelta(days=1)
        )
        
        assert stats["total_events"] == 10
        assert stats["by_type"][AuditEventType.SERVICE_START] == 5
        assert stats["by_type"][AuditEventType.ERROR] == 5
        assert stats["by_severity"][AuditSeverity.INFO] == 5
        assert stats["by_severity"][AuditSeverity.ERROR] == 5
        assert len(stats["by_service"]) == 3
    
    def test_get_capabilities(self, audit_service):
        """Test getting service capabilities."""
        caps = audit_service.get_capabilities()
        
        assert isinstance(caps, ServiceCapabilities)
        assert caps.service_name == "GraphAuditService"
        assert "audit_event" in caps.actions
        assert "audit_authentication" in caps.actions
        assert "query_audit_log" in caps.actions
        assert caps.version == "1.0.0"
    
    def test_get_status(self, audit_service):
        """Test getting service status."""
        audit_service._running = True
        audit_service._total_events_audited = 100
        
        status = audit_service.get_status()
        
        assert isinstance(status, ServiceStatus)
        assert status.is_healthy is True
        assert status.metrics["total_events"] == 100.0
        assert status.metrics["retention_days"] == 30.0
    
    @pytest.mark.asyncio
    async def test_concurrent_audit_events(self, audit_service, mock_memory_bus):
        """Test concurrent audit event creation."""
        await audit_service.start()
        
        # Create multiple audit events concurrently
        tasks = []
        for i in range(10):
            task = audit_service.audit_event(
                event_type=AuditEventType.DATA_ACCESS,
                service_name=f"Service{i}",
                details={"index": i}
            )
            tasks.append(task)
        
        await asyncio.gather(*tasks)
        
        # All should succeed
        assert mock_memory_bus.memorize.call_count == 10
    
    @pytest.mark.asyncio
    async def test_audit_with_large_details(self, audit_service, mock_memory_bus):
        """Test auditing with large detail objects."""
        await audit_service.start()
        
        # Create large details
        large_details = {
            "data": "x" * 10000,  # 10KB of data
            "nested": {
                "level1": {
                    "level2": ["item"] * 100
                }
            }
        }
        
        await audit_service.audit_event(
            event_type=AuditEventType.DATA_ACCESS,
            service_name="LargeService",
            details=large_details
        )
        
        # Should handle large data
        mock_memory_bus.memorize.assert_called_once()
        call_args = mock_memory_bus.memorize.call_args[1]
        node = call_args['node']
        
        # Details should be preserved
        assert "data" in node.attributes['details']
        assert len(node.attributes['details']['data']) == 10000
    
    @pytest.mark.asyncio
    async def test_node_type(self, audit_service):
        """Test that audit service uses correct node type."""
        node_type = audit_service.get_node_type()
        assert node_type == NodeType.AUDIT