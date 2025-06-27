"""
Unit tests for Self-Configuration Service API endpoints.
"""
import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock
from fastapi import FastAPI
from fastapi.testclient import TestClient

from ciris_engine.api.routes.adaptation import router
from ciris_engine.schemas.infrastructure.feedback_loop import (
    DetectedPattern, AnalysisResult, PatternType, PatternMetrics
)
from ciris_engine.schemas.infrastructure.behavioral_patterns import (
    ActionFrequency, TemporalPattern
)


@pytest.fixture
def mock_self_config_service():
    """Create a mock self-configuration service."""
    service = Mock()
    
    # Setup async methods
    service.analyze_patterns = AsyncMock()
    service.get_detected_patterns = AsyncMock()
    service.get_action_frequency = AsyncMock()
    service.get_pattern_insights = AsyncMock()
    service.get_learning_summary = AsyncMock()
    service.get_temporal_patterns = AsyncMock()
    service.get_pattern_effectiveness = AsyncMock()
    service.get_analysis_status = AsyncMock()
    
    return service


@pytest.fixture
def test_app(mock_self_config_service):
    """Create a test FastAPI app with adaptation routes."""
    app = FastAPI()
    app.include_router(router, prefix="/v1")
    
    # Add mock service to app state
    app.state.self_configuration_service = mock_self_config_service
    
    return app


@pytest.fixture
def test_client(test_app):
    """Create a test client."""
    return TestClient(test_app)


@pytest.fixture
def sample_pattern():
    """Create a sample detected pattern."""
    return DetectedPattern(
        pattern_type=PatternType.TEMPORAL,
        pattern_id="pattern_123",
        description="Peak activity between 9 AM and 5 PM",
        evidence_nodes=["node_1", "node_2"],
        detected_at=datetime.now(timezone.utc),
        metrics=PatternMetrics(
            occurrence_count=25,
            average_value=0.75,
            peak_value=0.95,
            time_range_hours=168.0,
            data_points=100,
            trend="increasing"
        )
    )


@pytest.fixture
def sample_temporal_pattern():
    """Create a sample temporal pattern."""
    return TemporalPattern(
        pattern_id="temporal_456",
        pattern_type="daily",
        time_window="09:00-17:00",
        activity_description="Business hours activity",
        occurrence_count=20,
        confidence=0.85,
        first_detected=datetime.now(timezone.utc) - timedelta(days=7),
        last_observed=datetime.now(timezone.utc),
        metrics={"activity_level": 0.8}
    )


class TestPatternEndpoint:
    """Test GET /v1/adaptation/patterns endpoint."""
    
    def test_get_patterns_success(self, test_client, mock_self_config_service, sample_pattern):
        """Test successful pattern retrieval."""
        # Setup mock
        mock_self_config_service.get_detected_patterns.return_value = [sample_pattern]
        
        # Make request
        response = test_client.get("/v1/adaptation/patterns")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["time_window_hours"] == 24
        assert len(data["patterns"]) == 1
        assert data["patterns"][0]["pattern_id"] == "pattern_123"
        
        # Verify service was called correctly
        mock_self_config_service.get_detected_patterns.assert_called_once_with(
            pattern_type=None,
            hours=24
        )
    
    def test_get_patterns_with_filters(self, test_client, mock_self_config_service):
        """Test pattern retrieval with filters."""
        # Setup mock
        mock_self_config_service.get_detected_patterns.return_value = []
        
        # Make request with filters
        response = test_client.get(
            "/v1/adaptation/patterns",
            params={"pattern_type": "temporal", "hours": 48}
        )
        
        # Verify
        assert response.status_code == 200
        mock_self_config_service.get_detected_patterns.assert_called_once_with(
            pattern_type=PatternType.TEMPORAL,
            hours=48
        )
    
    def test_get_patterns_service_unavailable(self, test_app, test_client):
        """Test when service is not available."""
        # Remove service
        delattr(test_app.state, 'self_configuration_service')
        
        # Make request
        response = test_client.get("/v1/adaptation/patterns")
        
        # Verify
        assert response.status_code == 503
        assert "Self-configuration service not available" in response.json()["detail"]


class TestInsightsEndpoint:
    """Test GET /v1/adaptation/insights endpoint."""
    
    def test_get_insights_success(self, test_client, mock_self_config_service):
        """Test successful insights retrieval."""
        # Setup mock
        mock_insights = [
            {
                "id": "insight_1",
                "pattern_id": "pattern_123",
                "insight_type": "behavioral",
                "description": "Agent shows increased activity during business hours",
                "confidence": 0.85,
                "created_at": datetime.now(timezone.utc),
                "evidence_nodes": ["node_1", "node_2", "node_3"]
            }
        ]
        mock_self_config_service.get_pattern_insights.return_value = mock_insights
        
        # Make request
        response = test_client.get("/v1/adaptation/insights")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert len(data["insights"]) == 1
        assert data["insights"][0]["insight_id"] == "insight_1"
        assert data["insights"][0]["evidence_count"] == 3
        
        # Verify service was called correctly
        mock_self_config_service.get_pattern_insights.assert_called_once_with(limit=50)
    
    def test_get_insights_with_limit(self, test_client, mock_self_config_service):
        """Test insights retrieval with custom limit."""
        # Setup mock
        mock_self_config_service.get_pattern_insights.return_value = []
        
        # Make request
        response = test_client.get("/v1/adaptation/insights", params={"limit": 100})
        
        # Verify
        assert response.status_code == 200
        mock_self_config_service.get_pattern_insights.assert_called_once_with(limit=100)


class TestHistoryEndpoint:
    """Test GET /v1/adaptation/history endpoint."""
    
    def test_get_history_success(self, test_client, mock_self_config_service):
        """Test successful history retrieval."""
        # Setup mock
        mock_summary = {
            "adaptations": [
                {
                    "timestamp": datetime.now(timezone.utc),
                    "type": "behavioral",
                    "description": "Adjusted response timing based on user patterns",
                    "trigger_pattern": "pattern_123",
                    "effectiveness": 0.75
                }
            ]
        }
        mock_self_config_service.get_learning_summary.return_value = mock_summary
        
        # Make request
        response = test_client.get("/v1/adaptation/history")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["time_range_hours"] == 48
        assert len(data["events"]) == 1
        assert data["events"][0]["event_type"] == "behavioral"
    
    def test_get_history_filters_by_time(self, test_client, mock_self_config_service):
        """Test history filtering by time window."""
        # Setup mock with old and new events
        now = datetime.now(timezone.utc)
        mock_summary = {
            "adaptations": [
                {
                    "timestamp": now - timedelta(days=5),
                    "type": "old_event",
                    "description": "Old adaptation"
                },
                {
                    "timestamp": now - timedelta(hours=12),
                    "type": "recent_event",
                    "description": "Recent adaptation"
                }
            ]
        }
        mock_self_config_service.get_learning_summary.return_value = mock_summary
        
        # Make request with 24 hour window
        response = test_client.get("/v1/adaptation/history", params={"hours": 24})
        
        # Verify only recent event is returned
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["events"][0]["event_type"] == "recent_event"


class TestEffectivenessEndpoint:
    """Test GET /v1/adaptation/effectiveness endpoint."""
    
    def test_get_effectiveness_success(self, test_client, mock_self_config_service, sample_pattern):
        """Test successful effectiveness retrieval."""
        # Setup mocks
        mock_self_config_service.get_detected_patterns.return_value = [sample_pattern]
        mock_self_config_service.get_pattern_effectiveness.return_value = {
            "metric_name": "Response time",
            "baseline_value": 1000,
            "current_value": 750,
            "confidence": 0.9,
            "samples": 100
        }
        
        # Make request
        response = test_client.get("/v1/adaptation/effectiveness")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["overall_effectiveness"] == 1.0  # 1 successful pattern
        assert data["successful_patterns"] == 1
        assert data["total_patterns"] == 1
        assert len(data["metrics"]) == 1
        assert data["metrics"][0]["improvement_percentage"] == -25.0  # 25% improvement
    
    def test_get_effectiveness_no_patterns(self, test_client, mock_self_config_service):
        """Test effectiveness when no patterns exist."""
        # Setup mock
        mock_self_config_service.get_detected_patterns.return_value = []
        
        # Make request
        response = test_client.get("/v1/adaptation/effectiveness")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["overall_effectiveness"] == 0
        assert data["total_patterns"] == 0


class TestCorrelationsEndpoint:
    """Test GET /v1/adaptation/correlations endpoint."""
    
    def test_get_correlations_success(self, test_client, mock_self_config_service, sample_temporal_pattern):
        """Test successful correlations retrieval."""
        # Setup mock with two patterns that share time window
        pattern2 = TemporalPattern(
            pattern_id="temporal_789",
            pattern_type="daily",
            time_window="09:00-17:00",  # Same window
            activity_description="Tool usage pattern",
            occurrence_count=15,
            confidence=0.80,
            first_detected=datetime.now(timezone.utc) - timedelta(days=5),
            last_observed=datetime.now(timezone.utc),
            metrics={"tool_usage": 0.9}
        )
        mock_self_config_service.get_temporal_patterns.return_value = [
            sample_temporal_pattern, pattern2
        ]
        
        # Make request
        response = test_client.get("/v1/adaptation/correlations")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["total"] == 1
        assert data["min_confidence"] == 0.5
        assert len(data["correlations"]) == 1
        assert data["correlations"][0]["correlation_type"] == "temporal"
    
    def test_get_correlations_with_min_confidence(self, test_client, mock_self_config_service):
        """Test correlations filtering by confidence."""
        # Setup mock
        mock_self_config_service.get_temporal_patterns.return_value = []
        
        # Make request
        response = test_client.get(
            "/v1/adaptation/correlations",
            params={"min_confidence": 0.8}
        )
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert data["min_confidence"] == 0.8


class TestReportEndpoint:
    """Test GET /v1/adaptation/report endpoint."""
    
    def test_get_report_success(self, test_client, mock_self_config_service, sample_pattern):
        """Test successful report generation."""
        # Setup mocks
        mock_self_config_service.get_analysis_status.return_value = {
            "total_adaptations": 10,
            "active_adaptations": 5
        }
        mock_self_config_service.get_learning_summary.return_value = {
            "top_improvements": ["Reduced response time by 25%", "Improved error handling"],
            "recommendations": ["Consider implementing caching", "Optimize database queries"],
            "insights": ["User activity peaks at 2 PM", "Error rate decreases on weekends"]
        }
        mock_self_config_service.get_detected_patterns.return_value = [sample_pattern]
        mock_self_config_service.get_pattern_effectiveness.return_value = {
            "improvement": 0.25
        }
        
        # Make request
        response = test_client.get("/v1/adaptation/report")
        
        # Verify
        assert response.status_code == 200
        data = response.json()["data"]
        assert "detected 1 behavioral patterns" in data["summary"]
        assert data["detected_patterns"] == 1
        assert data["active_adaptations"] == 5
        assert data["effectiveness_score"] == 1.0
        assert len(data["top_improvements"]) == 2
        assert len(data["recommendations"]) == 2
        assert len(data["learning_insights"]) == 2
    
    def test_get_report_service_error(self, test_client, mock_self_config_service):
        """Test report generation when service errors."""
        # Setup mock to raise error
        mock_self_config_service.get_analysis_status.side_effect = Exception("Service error")
        
        # Make request
        response = test_client.get("/v1/adaptation/report")
        
        # Verify
        assert response.status_code == 500
        assert "Service error" in response.json()["detail"]


class TestServiceUnavailable:
    """Test behavior when self-configuration service is not available."""
    
    def test_all_endpoints_return_503(self, test_app, test_client):
        """Test that all endpoints return 503 when service is unavailable."""
        # Remove service
        delattr(test_app.state, 'self_configuration_service')
        
        # Test all endpoints
        endpoints = [
            "/v1/adaptation/patterns",
            "/v1/adaptation/insights",
            "/v1/adaptation/history",
            "/v1/adaptation/effectiveness",
            "/v1/adaptation/correlations",
            "/v1/adaptation/report"
        ]
        
        for endpoint in endpoints:
            response = test_client.get(endpoint)
            assert response.status_code == 503, f"Expected 503 for {endpoint}"
            assert "Self-configuration service not available" in response.json()["detail"]