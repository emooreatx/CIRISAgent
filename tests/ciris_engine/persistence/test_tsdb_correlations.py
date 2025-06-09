"""
Tests for TSDB Correlations functionality

Verifies that the enhanced correlations system can store and retrieve
metrics, logs, traces, and audit events as time series data.
"""

import pytest
import json
from datetime import datetime, timezone, timedelta
from uuid import uuid4

from ciris_engine.persistence.models.correlations import (
    add_correlation,
    get_correlation,
    get_correlations_by_type_and_time,
    get_metrics_timeseries,
)
from ciris_engine.schemas.correlation_schemas_v1 import (
    ServiceCorrelation,
    ServiceCorrelationStatus,
    CorrelationType,
)


class TestTSDBCorrelations:
    """Test suite for TSDB-enhanced correlations"""
    
    @pytest.fixture
    def test_db_path(self, tmp_path):
        """Create a temporary test database"""
        return str(tmp_path / "test_tsdb.db")
    
    @pytest.fixture(autouse=True)
    def setup_db(self, test_db_path):
        """Initialize the database with schema"""
        from ciris_engine.persistence.db.setup import initialize_database
        initialize_database(test_db_path)
    
    def test_add_metric_correlation(self, test_db_path):
        """Test adding a metric as a correlation"""
        metric_corr = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="telemetry",
            handler_name="metrics_collector",
            action_type="record_metric",
            correlation_type=CorrelationType.METRIC_DATAPOINT,
            timestamp=datetime.now(timezone.utc),
            metric_name="cpu_usage",
            metric_value=45.5,
            tags={"host": "agent-1", "environment": "production"},
            retention_policy="raw"
        )
        
        corr_id = add_correlation(metric_corr, db_path=test_db_path)
        assert corr_id == metric_corr.correlation_id
        
        # Retrieve and verify
        retrieved = get_correlation(corr_id, db_path=test_db_path)
        assert retrieved is not None
        assert retrieved.correlation_type == CorrelationType.METRIC_DATAPOINT
        assert retrieved.metric_name == "cpu_usage"
        assert retrieved.metric_value == 45.5
        assert retrieved.tags["host"] == "agent-1"
    
    def test_add_log_correlation(self, test_db_path):
        """Test adding a log entry as a correlation"""
        log_corr = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="logging",
            handler_name="log_collector",
            action_type="record_log",
            correlation_type=CorrelationType.LOG_ENTRY,
            timestamp=datetime.now(timezone.utc),
            log_level="ERROR",
            request_data={"message": "Failed to connect to service"},
            tags={"service": "api", "error_code": "CONNECTION_REFUSED"},
            retention_policy="raw"
        )
        
        corr_id = add_correlation(log_corr, db_path=test_db_path)
        
        retrieved = get_correlation(corr_id, db_path=test_db_path)
        assert retrieved.correlation_type == CorrelationType.LOG_ENTRY
        assert retrieved.log_level == "ERROR"
        assert retrieved.request_data["message"] == "Failed to connect to service"
    
    def test_add_trace_correlation(self, test_db_path):
        """Test adding a trace span as a correlation"""
        trace_id = str(uuid4())
        span_id = str(uuid4())
        parent_span_id = str(uuid4())
        
        trace_corr = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="tracing",
            handler_name="trace_collector",
            action_type="record_span",
            correlation_type=CorrelationType.TRACE_SPAN,
            timestamp=datetime.now(timezone.utc),
            trace_id=trace_id,
            span_id=span_id,
            parent_span_id=parent_span_id,
            request_data={"operation": "process_thought", "duration_ms": 125},
            tags={"service": "thought_processor", "status": "success"},
            retention_policy="raw"
        )
        
        corr_id = add_correlation(trace_corr, db_path=test_db_path)
        
        retrieved = get_correlation(corr_id, db_path=test_db_path)
        assert retrieved.correlation_type == CorrelationType.TRACE_SPAN
        assert retrieved.trace_id == trace_id
        assert retrieved.span_id == span_id
        assert retrieved.parent_span_id == parent_span_id
    
    def test_get_correlations_by_type_and_time(self, test_db_path):
        """Test querying correlations by type with time filtering"""
        base_time = datetime.now(timezone.utc)
        
        # Add metrics at different times
        for i in range(5):
            metric_corr = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="telemetry",
                handler_name="metrics_collector",
                action_type="record_metric",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=base_time - timedelta(minutes=i*10),
                metric_name="memory_usage",
                metric_value=100.0 + i*10,
                tags={"host": "agent-1"},
                retention_policy="raw"
            )
            add_correlation(metric_corr, db_path=test_db_path)
        
        # Query last 30 minutes
        start_time = (base_time - timedelta(minutes=30)).isoformat()
        end_time = base_time.isoformat()
        
        results = get_correlations_by_type_and_time(
            CorrelationType.METRIC_DATAPOINT,
            start_time=start_time,
            end_time=end_time,
            metric_names=["memory_usage"],
            db_path=test_db_path
        )
        
        assert len(results) >= 3  # Should get at least 3 recent metrics
        assert all(r.correlation_type == CorrelationType.METRIC_DATAPOINT for r in results)
        assert all(r.metric_name == "memory_usage" for r in results)
    
    def test_get_metrics_timeseries(self, test_db_path):
        """Test retrieving metrics as time series data"""
        base_time = datetime.now(timezone.utc)
        
        # Add CPU metrics over time
        for i in range(10):
            metric_corr = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="telemetry",
                handler_name="metrics_collector",
                action_type="record_metric",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=base_time - timedelta(minutes=i),
                metric_name="cpu_usage",
                metric_value=30.0 + i*2,
                tags={"host": "agent-1", "core": "0"},
                retention_policy="raw"
            )
            add_correlation(metric_corr, db_path=test_db_path)
        
        # Query time series
        results = get_metrics_timeseries(
            "cpu_usage",
            start_time=(base_time - timedelta(minutes=15)).isoformat(),
            tags={"host": "agent-1"},
            db_path=test_db_path
        )
        
        assert len(results) > 0
        assert all(r.metric_name == "cpu_usage" for r in results)
        # Results should be in ascending time order
        for i in range(1, len(results)):
            assert results[i].timestamp >= results[i-1].timestamp
    
    def test_metric_summarization_types(self, test_db_path):
        """Test different retention policy types for metric summarization"""
        # Raw metric
        raw_metric = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="telemetry",
            handler_name="metrics_collector",
            action_type="record_metric",
            correlation_type=CorrelationType.METRIC_DATAPOINT,
            timestamp=datetime.now(timezone.utc),
            metric_name="request_count",
            metric_value=100,
            retention_policy="raw"
        )
        
        # Hourly summary
        hourly_summary = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="telemetry",
            handler_name="correlations_cleaner",
            action_type="summarize_metrics",
            correlation_type=CorrelationType.METRIC_HOURLY_SUMMARY,
            timestamp=datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0),
            metric_name="request_count",
            metric_value=5000,  # Sum for the hour
            request_data={"count": 50, "min": 80, "max": 120, "avg": 100},
            retention_policy="hourly_summary"
        )
        
        # Daily summary
        daily_summary = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="telemetry",
            handler_name="correlations_cleaner",
            action_type="summarize_metrics",
            correlation_type=CorrelationType.METRIC_DAILY_SUMMARY,
            timestamp=datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0),
            metric_name="request_count",
            metric_value=120000,  # Sum for the day
            request_data={"count": 1200, "min": 50, "max": 200, "avg": 100},
            retention_policy="daily_summary"
        )
        
        # Add all correlations
        for corr in [raw_metric, hourly_summary, daily_summary]:
            add_correlation(corr, db_path=test_db_path)
        
        # Query by different correlation types
        raw_results = get_correlations_by_type_and_time(
            CorrelationType.METRIC_DATAPOINT,
            metric_names=["request_count"],
            db_path=test_db_path
        )
        assert len(raw_results) == 1
        
        hourly_results = get_correlations_by_type_and_time(
            CorrelationType.METRIC_HOURLY_SUMMARY,
            metric_names=["request_count"],
            db_path=test_db_path
        )
        assert len(hourly_results) == 1
        assert hourly_results[0].request_data["count"] == 50
        
        daily_results = get_correlations_by_type_and_time(
            CorrelationType.METRIC_DAILY_SUMMARY,
            metric_names=["request_count"],
            db_path=test_db_path
        )
        assert len(daily_results) == 1
        assert daily_results[0].metric_value == 120000
    
    def test_log_level_filtering(self, test_db_path):
        """Test filtering logs by level"""
        log_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        base_time = datetime.now(timezone.utc)
        
        # Add logs of different levels
        for i, level in enumerate(log_levels):
            log_corr = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="logging",
                handler_name="log_collector",
                action_type="record_log",
                correlation_type=CorrelationType.LOG_ENTRY,
                timestamp=base_time - timedelta(minutes=i),
                log_level=level,
                request_data={"message": f"Test {level} message"},
                retention_policy="raw"
            )
            add_correlation(log_corr, db_path=test_db_path)
        
        # Query only ERROR and CRITICAL logs
        results = get_correlations_by_type_and_time(
            CorrelationType.LOG_ENTRY,
            log_levels=["ERROR", "CRITICAL"],
            db_path=test_db_path
        )
        
        assert len(results) == 2
        assert all(r.log_level in ["ERROR", "CRITICAL"] for r in results)
    
    def test_tag_based_filtering(self, test_db_path):
        """Test filtering metrics by tags"""
        base_time = datetime.now(timezone.utc)
        
        # Add metrics with different tag combinations
        hosts = ["agent-1", "agent-2", "agent-3"]
        environments = ["production", "staging", "development"]
        
        for i, (host, env) in enumerate(zip(hosts, environments)):
            metric_corr = ServiceCorrelation(
                correlation_id=str(uuid4()),
                service_type="telemetry",
                handler_name="metrics_collector",
                action_type="record_metric",
                correlation_type=CorrelationType.METRIC_DATAPOINT,
                timestamp=base_time - timedelta(minutes=i),
                metric_name="api_latency",
                metric_value=50.0 + i*10,
                tags={"host": host, "environment": env},
                retention_policy="raw"
            )
            add_correlation(metric_corr, db_path=test_db_path)
        
        # Query with tag filter
        results = get_metrics_timeseries(
            "api_latency",
            tags={"environment": "production"},
            db_path=test_db_path
        )
        
        assert len(results) == 1
        assert results[0].tags["environment"] == "production"
        assert results[0].tags["host"] == "agent-1"
    
    def test_audit_event_correlation(self, test_db_path):
        """Test storing audit events as correlations"""
        audit_corr = ServiceCorrelation(
            correlation_id=str(uuid4()),
            service_type="audit",
            handler_name="audit_service",
            action_type="log_action",
            correlation_type=CorrelationType.AUDIT_EVENT,
            timestamp=datetime.now(timezone.utc),
            request_data={
                "action": "SPEAK",
                "actor": "agent",
                "target": "channel_123",
                "details": {"message": "Hello, world!"}
            },
            tags={"severity": "info", "source": "action_handler"},
            retention_policy="raw"
        )
        
        corr_id = add_correlation(audit_corr, db_path=test_db_path)
        
        retrieved = get_correlation(corr_id, db_path=test_db_path)
        assert retrieved.correlation_type == CorrelationType.AUDIT_EVENT
        assert retrieved.request_data["action"] == "SPEAK"
        assert retrieved.tags["severity"] == "info"