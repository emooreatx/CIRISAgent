"""
Tests for TSDB Integration

Tests the integration of metrics, logs, and audit events with the TSDB
correlations system.
"""

import pytest
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch

# TelemetryService is mocked in these tests
from ciris_engine.telemetry.log_collector import LogCorrelationCollector, TSDBLogHandler
from ciris_engine.services.tsdb_audit_service import TSDBSignedAuditService
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.correlation_schemas_v1 import CorrelationType
from ciris_engine.schemas.protocol_schemas_v1 import ActionContext
from ciris_engine.persistence.models.correlations import get_correlations_by_type_and_time, get_metrics_timeseries


@pytest.mark.skip(reason="Tests need to be updated for graph-based telemetry")
class TestTelemetryTSDBIntegration:
    """Test TelemetryService integration with TSDB"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create a temporary test database"""
        return str(tmp_path / "test_tsdb_integration.db")
    
    @pytest.fixture(autouse=True)
    def setup_db(self, test_db_path):
        """Initialize the database with schema"""
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    @pytest.fixture
    def telemetry_service(self):
        """Create a TelemetryService instance"""
        return TelemetryService()
    
    @pytest.mark.asyncio
    async def test_telemetry_stores_metrics_in_tsdb(self, telemetry_service, test_db_path):
        """Test that telemetry service stores metrics in TSDB"""
        # Start the service
        await telemetry_service.start()
        
        # Record some metrics
        await telemetry_service.record_metric("test_metric", 42.5, {"environment": "test"})
        await telemetry_service.record_metric("test_metric", 43.5, {"environment": "test"})
        await telemetry_service.record_metric("other_metric", 100.0, {"type": "gauge"})
        
        # Give async tasks time to complete
        await asyncio.sleep(0.1)
        
        # Query metrics from TSDB
        with patch('ciris_engine.persistence.models.correlations.get_db_connection') as mock_get_db:
            mock_get_db.return_value.__enter__.return_value = Mock()
            
            # Since we're mocking, we'll verify the correlation was created correctly
            # In a real test with a real DB, we'd query and verify
            assert hasattr(telemetry_service, '_enhanced_history')
            assert "test_metric" in telemetry_service._enhanced_history
            assert len(telemetry_service._enhanced_history["test_metric"]) == 2
        
        await telemetry_service.stop()
    
    @pytest.mark.asyncio
    async def test_telemetry_backward_compatibility(self, telemetry_service):
        """Test that telemetry maintains backward compatibility"""
        await telemetry_service.start()
        
        # Record metric
        await telemetry_service.record_metric("compat_test", 99.9)
        
        # Check both storage formats exist
        assert "compat_test" in telemetry_service._history
        assert hasattr(telemetry_service, '_enhanced_history')
        assert "compat_test" in telemetry_service._enhanced_history
        
        # Verify basic format
        timestamp, value = telemetry_service._history["compat_test"][0]
        assert value == 99.9
        assert isinstance(timestamp, datetime)
        
        # Verify enhanced format
        enhanced = telemetry_service._enhanced_history["compat_test"][0]
        assert enhanced['value'] == 99.9
        assert enhanced['tags'] == {}
        
        await telemetry_service.stop()


class TestLogCollectorTSDBIntegration:
    """Test LogCorrelationCollector integration with TSDB"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create a temporary test database"""
        return str(tmp_path / "test_logs_tsdb.db")
    
    @pytest.fixture(autouse=True)
    def setup_db(self, test_db_path):
        """Initialize the database with schema"""
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    @pytest.fixture
    def log_collector(self):
        """Create a LogCorrelationCollector instance"""
        return LogCorrelationCollector(
            log_levels=["INFO", "WARNING", "ERROR"],
            tags={"test": "true"}
        )
    
    @pytest.mark.asyncio
    async def test_log_collector_captures_logs(self, log_collector):
        """Test that log collector captures logs as correlations"""
        # Create a test logger
        test_logger = logging.getLogger("test_logger")
        original_level = test_logger.level
        test_logger.setLevel(logging.INFO)
        
        # Add test logger to collector
        log_collector.add_logger("test_logger")
        
        # Start collector
        await log_collector.start()
        
        # Mock the add_correlation to capture calls
        with patch('ciris_engine.telemetry.log_collector.add_correlation') as mock_add:
            # Log some messages
            test_logger.info("Test info message")
            test_logger.warning("Test warning message")
            test_logger.error("Test error message")
            
            # Give async tasks time to complete
            await asyncio.sleep(0.1)
            
            # Verify correlations were created
            assert mock_add.call_count >= 3
            
            # Check the correlations
            for call in mock_add.call_args_list:
                corr = call[0][0]
                assert corr.correlation_type == CorrelationType.LOG_ENTRY
                assert corr.service_type == "logging"
                assert corr.log_level in ["INFO", "WARNING", "ERROR"]
                assert "test" in corr.tags
        
        # Stop collector
        await log_collector.stop()
        
        # Restore logger level
        test_logger.setLevel(original_level)
    
    def test_tsdb_log_handler_sync_fallback(self):
        """Test that TSDBLogHandler can work without async loop"""
        handler = TSDBLogHandler(tags={"sync": "test"})
        
        # Create a log record
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        # Mock add_correlation
        with patch('ciris_engine.telemetry.log_collector.add_correlation') as mock_add:
            handler.emit(record)
            
            # Should have called add_correlation synchronously
            assert mock_add.call_count == 1
            corr = mock_add.call_args[0][0]
            assert corr.correlation_type == CorrelationType.LOG_ENTRY
            assert corr.log_level == "INFO"


class TestAuditServiceTSDBIntegration:
    """Test TSDBSignedAuditService integration"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create a temporary test database"""
        return str(tmp_path / "test_audit_tsdb.db")
    
    @pytest.fixture(autouse=True)
    def setup_db(self, test_db_path):
        """Initialize the database with schema"""
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    @pytest.fixture
    def audit_service(self):
        """Create a TSDBSignedAuditService instance"""
        return TSDBSignedAuditService(
            tags={"service": "test"},
            enable_file_backup=False
        )
    
    @pytest.mark.asyncio
    async def test_audit_service_stores_events_in_tsdb(self, audit_service):
        """Test that audit service stores events as correlations"""
        await audit_service.start()
        
        # Mock add_correlation
        with patch('ciris_engine.services.tsdb_audit_service.add_correlation') as mock_add:
            # Log an audit event
            context = ActionContext(
                thought_id="test-thought-123",
                task_id="test-task-456",
                handler_name="test_handler",
                parameters={
                    "agent_profile": "test_agent",
                    "round_number": 42,
                    "task_description": "Test task"
                }
            )
            
            success = await audit_service.log_action(
                HandlerActionType.SPEAK,
                context,
                outcome="Message sent successfully"
            )
            
            assert success is True
            
            # Verify correlation was created
            assert mock_add.call_count == 1
            corr = mock_add.call_args[0][0]
            
            assert corr.correlation_type == CorrelationType.AUDIT_EVENT
            assert corr.action_type == "speak"
            assert corr.request_data["thought_id"] == "test-thought-123"
            assert corr.request_data["task_id"] == "test-task-456"
            assert corr.response_data["outcome"] == "Message sent successfully"
            assert corr.tags["action"] == "speak"
            assert corr.tags["severity"] == "low"
        
        await audit_service.stop()
    
    @pytest.mark.asyncio
    async def test_audit_service_with_file_backup(self, audit_service):
        """Test audit service with file backup enabled"""
        # Create mock file audit service
        mock_file_service = AsyncMock()
        mock_file_service.log_action = AsyncMock(return_value=True)
        
        # Create audit service with file backup
        audit_service = TSDBSignedAuditService(
            enable_file_backup=True,
            file_audit_service=mock_file_service
        )
        
        await audit_service.start()
        
        # Log an action
        context = ActionContext(
            thought_id="test-thought",
            task_id="test-task",
            handler_name="test_handler",
            parameters={"test": "context"}
        )
        await audit_service.log_action(HandlerActionType.TOOL, context, "Tool executed")
        
        # Verify file service was also called
        mock_file_service.log_action.assert_called_once_with(
            HandlerActionType.TOOL,
            context,
            "Tool executed"
        )
        
        await audit_service.stop()
    
    @pytest.mark.asyncio
    async def test_audit_query_functionality(self, audit_service):
        """Test querying audit trail from TSDB"""
        # Mock the query function
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            # Create mock correlations
            from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation
            mock_corr = ServiceCorrelation(
                correlation_id="test-123",
                service_type="audit",
                handler_name="audit_service",
                action_type="SPEAK",
                correlation_type=CorrelationType.AUDIT_EVENT,
                timestamp=datetime.now(timezone.utc),
                request_data={
                    "thought_id": "thought-123",
                    "task_id": "task-456",
                    "event_summary": "Test summary"
                },
                response_data={"outcome": "Success"},
                tags={"action": "SPEAK"},
                status="completed"
            )
            mock_query.return_value = [mock_corr]
            
            # Query audit trail
            results = await audit_service.query_audit_trail(
                action_types=["SPEAK"],
                thought_id="thought-123",
                limit=10
            )
            
            assert len(results) == 1
            assert results[0].event_type == "SPEAK"
            assert results[0].details["thought_id"] == "thought-123"
            assert results[0].outcome == "Success"
    
    def test_audit_severity_classification(self, audit_service):
        """Test severity classification for different actions"""
        # High severity
        assert audit_service._get_severity(HandlerActionType.DEFER) == "high"
        assert audit_service._get_severity(HandlerActionType.REJECT) == "high"
        assert audit_service._get_severity(HandlerActionType.FORGET) == "high"
        
        # Medium severity
        assert audit_service._get_severity(HandlerActionType.TOOL) == "medium"
        assert audit_service._get_severity(HandlerActionType.MEMORIZE) == "medium"
        assert audit_service._get_severity(HandlerActionType.TASK_COMPLETE) == "medium"
        
        # Low severity
        assert audit_service._get_severity(HandlerActionType.SPEAK) == "low"
        assert audit_service._get_severity(HandlerActionType.OBSERVE) == "low"
        assert audit_service._get_severity(HandlerActionType.PONDER) == "low"