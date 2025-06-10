"""
Tests for TSDBGraphNode specialized time-series graph nodes

Tests the TSDBGraphNode class functionality including:
- Creation of metric, log, and audit nodes
- Proper inheritance from GraphNode
- TSDB-specific field handling
- Correlation data conversion
"""

import pytest
from datetime import datetime, timezone
from ciris_engine.schemas.graph_schemas_v1 import (
    TSDBGraphNode, 
    GraphScope, 
    NodeType
)


class TestTSDBGraphNode:
    """Test TSDBGraphNode class functionality"""
    
    def test_tsdb_node_defaults(self):
        """Test TSDBGraphNode with default values"""
        node = TSDBGraphNode(data_type="test", scope=GraphScope.LOCAL)
        
        assert node.type == NodeType.TSDB_DATA
        assert node.data_type == "test"
        assert isinstance(node.timestamp, datetime)
        assert node.tags == {}
        assert node.retention_policy == "raw"
        assert node.aggregation_period is None
        
        # Check that attributes include TSDB fields
        assert "data_type" in node.attributes
        assert node.attributes["data_type"] == "test"
    
    def test_create_metric_node(self):
        """Test creating a metric TSDBGraphNode"""
        tags = {"source": "test", "environment": "dev"}
        node = TSDBGraphNode.create_metric_node(
            metric_name="cpu_usage",
            value=85.5,
            tags=tags,
            scope=GraphScope.LOCAL,
            retention_policy="aggregated"
        )
        
        assert node.type == NodeType.TSDB_DATA
        assert node.data_type == "metric"
        assert node.metric_name == "cpu_usage"
        assert node.metric_value == 85.5
        assert node.tags == tags
        assert node.scope == GraphScope.LOCAL
        assert node.retention_policy == "aggregated"
        assert node.id.startswith("metric_cpu_usage_")
        
        # Check attributes
        assert node.attributes["metric_name"] == "cpu_usage"
        assert node.attributes["metric_value"] == 85.5
        assert node.attributes["data_type"] == "metric"
        assert node.attributes["tags"] == tags
    
    def test_create_log_node(self):
        """Test creating a log entry TSDBGraphNode"""
        tags = {"component": "auth", "severity": "high"}
        node = TSDBGraphNode.create_log_node(
            log_message="User authentication failed",
            log_level="ERROR",
            tags=tags,
            scope=GraphScope.IDENTITY,
            retention_policy="raw"
        )
        
        assert node.type == NodeType.TSDB_DATA
        assert node.data_type == "log_entry"
        assert node.log_message == "User authentication failed"
        assert node.log_level == "ERROR"
        assert node.tags == tags
        assert node.scope == GraphScope.IDENTITY
        assert node.retention_policy == "raw"
        assert node.id.startswith("log_")
        
        # Check attributes
        assert node.attributes["log_message"] == "User authentication failed"
        assert node.attributes["log_level"] == "ERROR"
        assert node.attributes["data_type"] == "log_entry"
    
    def test_create_audit_node(self):
        """Test creating an audit event TSDBGraphNode"""
        tags = {"user_id": "123", "ip": "192.168.1.1"}
        node = TSDBGraphNode.create_audit_node(
            action_type="login",
            outcome="success",
            tags=tags,
            scope=GraphScope.ENVIRONMENT,
            retention_policy="raw"
        )
        
        assert node.type == NodeType.TSDB_DATA
        assert node.data_type == "audit_event"
        assert node.scope == GraphScope.ENVIRONMENT
        assert node.retention_policy == "raw"
        assert node.id.startswith("audit_login_")
        
        # Check that tags include the action_type and outcome
        expected_tags = {**tags, "action_type": "login", "outcome": "success"}
        assert node.tags == expected_tags
        
        # Check attributes
        assert node.attributes["action_type"] == "login"
        assert node.attributes["outcome"] == "success"
        assert node.attributes["data_type"] == "audit_event"
        assert node.attributes["tags"] == expected_tags
    
    def test_tsdb_node_with_custom_id(self):
        """Test TSDBGraphNode with custom ID"""
        node = TSDBGraphNode(
            id="custom_metric_123",
            scope=GraphScope.LOCAL,
            data_type="metric",
            metric_name="test_metric",
            metric_value=42.0
        )
        
        assert node.id == "custom_metric_123"
        assert node.metric_name == "test_metric"
        assert node.metric_value == 42.0
    
    def test_tsdb_node_auto_id_generation(self):
        """Test automatic ID generation"""
        node = TSDBGraphNode(data_type="custom_type", scope=GraphScope.LOCAL)
        
        assert node.id.startswith("tsdb_custom_type_")
        assert node.data_type == "custom_type"
    
    def test_to_correlation_data(self):
        """Test conversion to correlation data format"""
        tags = {"source": "test", "level": "info"}
        node = TSDBGraphNode.create_metric_node(
            metric_name="memory_usage",
            value=67.3,
            tags=tags,
            scope=GraphScope.LOCAL
        )
        
        correlation_data = node.to_correlation_data()
        
        expected_keys = [
            "timestamp", "metric_name", "metric_value", "log_level", 
            "log_message", "data_type", "tags", "retention_policy", "scope"
        ]
        
        for key in expected_keys:
            assert key in correlation_data
        
        assert correlation_data["metric_name"] == "memory_usage"
        assert correlation_data["metric_value"] == 67.3
        assert correlation_data["data_type"] == "metric"
        assert correlation_data["tags"] == tags
        assert correlation_data["scope"] == "local"
    
    def test_tsdb_node_inheritance(self):
        """Test that TSDBGraphNode properly inherits from GraphNode"""
        node = TSDBGraphNode.create_log_node(
            log_message="Test message",
            log_level="INFO",
            scope=GraphScope.LOCAL
        )
        
        # Should have all GraphNode fields
        assert hasattr(node, 'id')
        assert hasattr(node, 'type')
        assert hasattr(node, 'scope')
        assert hasattr(node, 'attributes')
        assert hasattr(node, 'version')
        assert hasattr(node, 'updated_by')
        assert hasattr(node, 'updated_at')
        
        # Should also have TSDBGraphNode specific fields
        assert hasattr(node, 'timestamp')
        assert hasattr(node, 'metric_name')
        assert hasattr(node, 'metric_value')
        assert hasattr(node, 'log_level')
        assert hasattr(node, 'log_message')
        assert hasattr(node, 'data_type')
        assert hasattr(node, 'tags')
        assert hasattr(node, 'retention_policy')
    
    def test_tsdb_node_timestamp_handling(self):
        """Test timestamp handling in TSDBGraphNode"""
        custom_timestamp = datetime(2024, 6, 9, 12, 0, 0, tzinfo=timezone.utc)
        
        node = TSDBGraphNode(
            data_type="test",
            scope=GraphScope.LOCAL,
            timestamp=custom_timestamp
        )
        
        assert node.timestamp == custom_timestamp
        assert isinstance(node.timestamp, datetime)
        assert node.timestamp.tzinfo == timezone.utc
    
    def test_tsdb_node_with_all_fields(self):
        """Test TSDBGraphNode with all possible fields"""
        timestamp = datetime.now(timezone.utc)
        
        node = TSDBGraphNode(
            id="test_node_123",
            scope=GraphScope.COMMUNITY,
            timestamp=timestamp,
            metric_name="test_metric",
            metric_value=100.0,
            log_level="DEBUG",
            log_message="Test log message",
            data_type="combined",
            tags={"env": "test", "version": "1.0"},
            retention_policy="downsampled",
            aggregation_period="5m"
        )
        
        assert node.id == "test_node_123"
        assert node.scope == GraphScope.COMMUNITY
        assert node.timestamp == timestamp
        assert node.metric_name == "test_metric"
        assert node.metric_value == 100.0
        assert node.log_level == "DEBUG"
        assert node.log_message == "Test log message"
        assert node.data_type == "combined"
        assert node.tags["env"] == "test"
        assert node.retention_policy == "downsampled"
        assert node.aggregation_period == "5m"
    
    def test_tsdb_node_attributes_sync(self):
        """Test that TSDB fields are properly synced to attributes"""
        node = TSDBGraphNode(
            data_type="sync_test",
            scope=GraphScope.LOCAL,
            metric_name="sync_metric",
            metric_value=42.5,
            tags={"test": "value"},
            retention_policy="aggregated"
        )
        
        # Check that all TSDB fields are in attributes
        assert node.attributes["data_type"] == "sync_test"
        assert node.attributes["metric_name"] == "sync_metric"
        assert node.attributes["metric_value"] == 42.5
        assert node.attributes["tags"] == {"test": "value"}
        assert node.attributes["retention_policy"] == "aggregated"
    
    def test_default_log_level(self):
        """Test default log level in create_log_node"""
        node = TSDBGraphNode.create_log_node(
            log_message="Default level test"
        )
        
        assert node.log_level == "INFO"
        assert node.attributes["log_level"] == "INFO"
    
    def test_empty_tags_handling(self):
        """Test handling of empty tags"""
        node = TSDBGraphNode.create_metric_node(
            metric_name="no_tags_metric",
            value=1.0
        )
        
        assert node.tags == {}
        assert node.attributes["tags"] == {}
        
        # Test with None tags
        node2 = TSDBGraphNode.create_metric_node(
            metric_name="none_tags_metric",
            value=2.0,
            tags=None
        )
        
        assert node2.tags == {}
        assert node2.attributes["tags"] == {}


class TestTSDBGraphNodeValidation:
    """Test TSDBGraphNode validation and error cases"""
    
    def test_missing_data_type_required(self):
        """Test that data_type is required"""
        with pytest.raises(Exception):  # Pydantic validation error
            TSDBGraphNode()  # Missing required data_type field
    
    def test_invalid_scope_handling(self):
        """Test handling of invalid scope values"""
        # This should work with a valid scope
        node = TSDBGraphNode.create_metric_node(
            metric_name="test",
            value=1.0,
            scope=GraphScope.LOCAL
        )
        assert node.scope == GraphScope.LOCAL
    
    def test_numeric_validation(self):
        """Test numeric field validation"""
        # Valid numeric value
        node = TSDBGraphNode.create_metric_node(
            metric_name="test",
            value=123.45
        )
        assert node.metric_value == 123.45
        
        # Test with integer
        node2 = TSDBGraphNode.create_metric_node(
            metric_name="test",
            value=42
        )
        assert node2.metric_value == 42.0  # Should be converted to float