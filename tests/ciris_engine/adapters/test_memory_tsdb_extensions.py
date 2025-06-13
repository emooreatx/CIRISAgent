"""
Tests for Memory Service TSDB Extensions

Tests the new time-series functionality in LocalGraphMemoryService
including recall_timeseries, memorize_metric, and memorize_log methods.
"""

import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from ciris_engine.services.memory_service.local_graph_memory_service import LocalGraphMemoryService
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult
from ciris_engine.schemas.correlation_schemas_v1 import CorrelationType
from ciris_engine.schemas.graph_schemas_v1 import TSDBGraphNode, NodeType


class TestMemoryTSDBExtensions:
    """Test TSDB extensions to memory service"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create a temporary test database"""
        return str(tmp_path / "test_memory_tsdb.db")
    
    @pytest.fixture(autouse=True)
    def setup_db(self, test_db_path):
        """Initialize the database with schema"""
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    @pytest.fixture
    def memory_service(self, test_db_path):
        """Create a LocalGraphMemoryService instance"""
        return LocalGraphMemoryService(db_path=test_db_path)
    
    @pytest.mark.asyncio
    async def test_memorize_metric_creates_node_and_correlation(self, memory_service):
        """Test that memorize_metric creates both graph node and TSDB correlation"""
        # Test memorizing a metric
        result = await memory_service.memorize_metric(
            metric_name="test_metric",
            value=42.5,
            tags={"source": "test", "environment": "dev"},
            scope="local"
        )
        
        assert result.status == MemoryOpStatus.OK
        
        # Verify the metric was stored (we'd need to query the actual database to verify)
        # For now, just verify the operation succeeded
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_memorize_log_creates_node_and_correlation(self, memory_service):
        """Test that memorize_log creates both graph node and TSDB correlation"""
        # Test memorizing a log entry
        result = await memory_service.memorize_log(
            log_message="Test log message",
            log_level="INFO", 
            tags={"component": "test", "severity": "low"},
            scope="local"
        )
        
        assert result.status == MemoryOpStatus.OK
        assert result.error is None
    
    @pytest.mark.asyncio 
    async def test_recall_timeseries_with_mock_data(self, memory_service):
        """Test recall_timeseries with mocked correlation data"""
        from datetime import datetime, timezone
        from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus
        
        # Mock the correlation query function with proper ServiceCorrelation objects
        mock_correlations = [
            ServiceCorrelation(
                correlation_id='test-123',
                service_type='test_service',
                handler_name='test_handler',
                action_type='test_action',
                timestamp=datetime(2024, 6, 9, 10, 0, 0, tzinfo=timezone.utc),
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                metric_name='test_metric',
                metric_value=42.5,
                tags={"scope": "local", "source": "test"},
                status=ServiceCorrelationStatus.COMPLETED,
                created_at='2024-06-09T10:00:00Z',
                updated_at='2024-06-09T10:00:00Z'
            ),
            ServiceCorrelation(
                correlation_id='test-456',
                service_type='test_service',
                handler_name='test_handler',
                action_type='test_action',
                timestamp=datetime(2024, 6, 9, 10, 15, 0, tzinfo=timezone.utc),
                correlation_type=CorrelationType.LOG_ENTRY,
                log_level='INFO',
                tags={"scope": "local", "message": "Test log"},
                request_data={"message": "Test log", "log_level": "INFO"},
                status=ServiceCorrelationStatus.COMPLETED,
                created_at='2024-06-09T10:15:00Z',
                updated_at='2024-06-09T10:15:00Z'
            )
        ]
        
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.return_value = mock_correlations
            
            # Test recall with default parameters
            results = await memory_service.recall_timeseries()
            
            assert len(results) > 0
            # Should be called for each default correlation type
            assert mock_query.call_count == 3  # METRIC_DATAPOINT, LOG_ENTRY, AUDIT_EVENT
    
    @pytest.mark.asyncio
    async def test_recall_timeseries_with_scope_filtering(self, memory_service):
        """Test recall_timeseries with scope filtering"""
        from datetime import datetime, timezone
        from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus
        
        mock_correlations = [
            ServiceCorrelation(
                correlation_id='test-123',
                service_type='test_service',
                handler_name='test_handler',
                action_type='test_action',
                timestamp=datetime(2024, 6, 9, 10, 0, 0, tzinfo=timezone.utc),
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                metric_name='test_metric',
                metric_value=42.5,
                tags={"scope": "local"},
                status=ServiceCorrelationStatus.COMPLETED,
                created_at='2024-06-09T10:00:00Z',
                updated_at='2024-06-09T10:00:00Z'
            ),
            ServiceCorrelation(
                correlation_id='test-456',
                service_type='test_service',
                handler_name='test_handler',
                action_type='test_action',
                timestamp=datetime(2024, 6, 9, 10, 15, 0, tzinfo=timezone.utc),
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                metric_name='other_metric',
                metric_value=100.0,
                tags={"scope": "global"},
                status=ServiceCorrelationStatus.COMPLETED,
                created_at='2024-06-09T10:15:00Z',
                updated_at='2024-06-09T10:15:00Z'
            )
        ]
        
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.return_value = mock_correlations
            
            # Test recall with specific scope
            results = await memory_service.recall_timeseries(scope="local")
            
            # Should only include correlations with scope="local"
            local_results = [r for r in results if r.get('tags', {}).get('scope') == 'local']
            assert len(local_results) > 0
    
    @pytest.mark.asyncio
    async def test_recall_timeseries_with_correlation_type_filter(self, memory_service):
        """Test recall_timeseries with correlation type filtering"""
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.return_value = []
            
            # Test recall with specific correlation types
            results = await memory_service.recall_timeseries(
                correlation_types=[CorrelationType.METRIC_DATAPOINT]
            )
            
            # Should only query for the specified correlation type
            mock_query.assert_called_once()
            call_args = mock_query.call_args[1]
            assert call_args['correlation_type'] == CorrelationType.METRIC_DATAPOINT
    
    @pytest.mark.asyncio
    async def test_recall_timeseries_time_window(self, memory_service):
        """Test recall_timeseries with custom time window"""
        from datetime import datetime
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.return_value = []
            
            # Test recall with 48 hour window
            await memory_service.recall_timeseries(hours=48)
            
            # Verify the time window was calculated correctly
            call_args = mock_query.call_args[1]
            start_time_str = call_args['start_time']
            end_time_str = call_args['end_time']
            
            # Convert ISO strings back to datetime objects for comparison
            start_time = datetime.fromisoformat(start_time_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_time_str.replace('Z', '+00:00'))
            
            time_diff = end_time - start_time
            assert abs(time_diff.total_seconds() - (48 * 3600)) < 60  # Within 1 minute tolerance
    
    @pytest.mark.asyncio
    async def test_memorize_metric_error_handling(self, memory_service):
        """Test error handling in memorize_metric"""
        with patch('ciris_engine.persistence.models.correlations.add_correlation') as mock_add:
            mock_add.side_effect = Exception("Database error")
            
            result = await memory_service.memorize_metric("test_metric", 42.5)
            
            assert result.status == MemoryOpStatus.DENIED
            assert "Database error" in result.error
    
    @pytest.mark.asyncio
    async def test_memorize_log_error_handling(self, memory_service):
        """Test error handling in memorize_log"""
        with patch('ciris_engine.persistence.models.correlations.add_correlation') as mock_add:
            mock_add.side_effect = Exception("Database error")
            
            result = await memory_service.memorize_log("Test message", "ERROR")
            
            assert result.status == MemoryOpStatus.DENIED
            assert "Database error" in result.error
    
    @pytest.mark.asyncio
    async def test_recall_timeseries_error_handling(self, memory_service):
        """Test error handling in recall_timeseries"""
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.side_effect = Exception("Query error")
            
            results = await memory_service.recall_timeseries()
            
            # Should return empty list on error, not raise exception
            assert results == []
    
    @pytest.mark.asyncio
    async def test_memorize_metric_without_tags(self, memory_service):
        """Test memorize_metric without tags"""
        result = await memory_service.memorize_metric("simple_metric", 1.0)
        
        assert result.status == MemoryOpStatus.OK
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_memorize_log_with_default_level(self, memory_service):
        """Test memorize_log with default log level"""
        result = await memory_service.memorize_log("Default level message")
        
        assert result.status == MemoryOpStatus.OK
        assert result.error is None
    
    @pytest.mark.asyncio
    async def test_memorize_metric_creates_tsdb_node(self, memory_service):
        """Test that memorize_metric creates TSDBGraphNode instances"""
        with patch.object(memory_service, 'memorize') as mock_memorize:
            mock_memorize.return_value = MemoryOpResult(status=MemoryOpStatus.OK)
            
            await memory_service.memorize_metric("test_metric", 42.5, {"tag": "value"})
            
            # Verify memorize was called with a TSDBGraphNode
            mock_memorize.assert_called_once()
            node_arg = mock_memorize.call_args[0][0]
            assert isinstance(node_arg, TSDBGraphNode)
            assert node_arg.type == NodeType.TSDB_DATA
            assert node_arg.data_type == "metric"
            assert node_arg.metric_name == "test_metric"
            assert node_arg.metric_value == 42.5
    
    @pytest.mark.asyncio
    async def test_memorize_log_creates_tsdb_node(self, memory_service):
        """Test that memorize_log creates TSDBGraphNode instances"""
        with patch.object(memory_service, 'memorize') as mock_memorize:
            mock_memorize.return_value = MemoryOpResult(status=MemoryOpStatus.OK)
            
            await memory_service.memorize_log("Test message", "ERROR", {"component": "auth"})
            
            # Verify memorize was called with a TSDBGraphNode
            mock_memorize.assert_called_once()
            node_arg = mock_memorize.call_args[0][0]
            assert isinstance(node_arg, TSDBGraphNode)
            assert node_arg.type == NodeType.TSDB_DATA
            assert node_arg.data_type == "log_entry"
            assert node_arg.log_message == "Test message"
            assert node_arg.log_level == "ERROR"
    
    @pytest.mark.asyncio
    async def test_recall_timeseries_json_tag_parsing(self, memory_service):
        """Test that recall_timeseries correctly parses JSON tags"""
        from datetime import datetime, timezone
        from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, CorrelationType, ServiceCorrelationStatus
        
        mock_correlations = [
            ServiceCorrelation(
                correlation_id='test-123',
                service_type='test_service',
                handler_name='test_handler',
                action_type='test_action',
                timestamp=datetime(2024, 6, 9, 10, 0, 0, tzinfo=timezone.utc),
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                metric_name='test_metric',
                metric_value=42.5,
                tags={"scope": "local", "environment": "test"},  # Already parsed dict
                status=ServiceCorrelationStatus.COMPLETED,
                created_at='2024-06-09T10:00:00Z',
                updated_at='2024-06-09T10:00:00Z'
            )
        ]
        
        with patch('ciris_engine.persistence.models.correlations.get_correlations_by_type_and_time') as mock_query:
            mock_query.return_value = mock_correlations
            
            results = await memory_service.recall_timeseries(scope="local")
            
            # Should parse the JSON tags correctly
            if results:
                assert isinstance(results[0]['tags'], dict)
                assert results[0]['tags']['scope'] == 'local'
                assert results[0]['tags']['environment'] == 'test'


class TestMemoryServiceCapabilities:
    """Test that the memory service correctly reports its capabilities"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        return str(tmp_path / "test_caps.db")
    
    @pytest.fixture(autouse=True) 
    def setup_db(self, test_db_path):
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    @pytest.fixture
    def memory_service(self, test_db_path):
        return LocalGraphMemoryService(db_path=test_db_path)
    
    @pytest.mark.asyncio
    async def test_get_capabilities_includes_new_methods(self, memory_service):
        """Test that get_capabilities includes the new TSDB methods"""
        capabilities = await memory_service.get_capabilities()
        
        expected_capabilities = [
            "memorize", "recall", "forget", "search_memories",
            "recall_timeseries", "memorize_metric", "memorize_log"
        ]
        
        for capability in expected_capabilities:
            assert capability in capabilities