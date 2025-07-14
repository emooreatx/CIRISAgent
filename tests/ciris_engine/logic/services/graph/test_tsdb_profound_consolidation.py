"""Unit tests for TSDB profound consolidation (in-place compression)."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json
import sqlite3

from ciris_engine.logic.services.graph.tsdb_consolidation import TSDBConsolidationService
from ciris_engine.logic.services.graph.tsdb_consolidation.compressor import SummaryCompressor
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope


@pytest.fixture
def mock_memory_bus():
    """Create a mock memory bus."""
    mock = Mock()
    mock.memorize = AsyncMock()
    mock.recall = AsyncMock(return_value=[])
    return mock


@pytest.fixture  
def mock_time_service():
    """Create a mock time service that returns first of month."""
    mock = Mock()
    # Set to August 1, 2025 at 01:00 UTC (so July data gets compressed)
    mock.now = Mock(return_value=datetime(2025, 8, 1, 1, 0, 0, tzinfo=timezone.utc))
    return mock


@pytest.fixture
def tsdb_service(mock_memory_bus, mock_time_service):
    """Create TSDB service with custom target MB/day."""
    service = TSDBConsolidationService(
        memory_bus=mock_memory_bus,
        time_service=mock_time_service
    )
    # Set a very low target to force compression
    service._profound_target_mb_per_day = 0.005  # 5KB/day
    return service


@pytest.fixture
def mock_db_connection():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    
    # Create necessary tables
    conn.execute("""
        CREATE TABLE graph_nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT,
            scope TEXT,
            attributes_json TEXT,
            version INTEGER DEFAULT 1,
            updated_by TEXT,
            updated_at TEXT,
            created_at TEXT
        )
    """)
    
    return conn


def create_daily_summary(date: datetime, node_type: str = "tsdb_summary", large: bool = True) -> dict:
    """Create a daily summary with extensive data for testing compression."""
    attributes = {
        "consolidation_level": "extensive",
        "period_start": date.isoformat(),
        "period_end": (date + timedelta(days=1)).isoformat(),
        "period_label": date.strftime('%Y-%m-%d'),
        "source_summary_count": 4
    }
    
    if node_type == "tsdb_summary" and large:
        # Add lots of metrics to make it large
        attributes["metrics"] = {
            f"metric_{i}": {
                "count": 100 + i,
                "sum": 1000.0 + i * 10,
                "min": 10.0 + i,
                "max": 200.0 + i * 2,
                "avg": 100.0 + i
            }
            for i in range(50)  # 50 metrics
        }
        attributes["total_tokens"] = 50000
        attributes["total_cost_cents"] = 500.0
        attributes["action_counts"] = {f"ACTION_{i}": 100 + i for i in range(20)}
        attributes["detailed_description"] = "A" * 1000  # 1KB of text
        attributes["full_context"] = "B" * 2000  # 2KB of text
        attributes["debug_info"] = {"data": "C" * 500}
    
    return attributes


class TestSummaryCompressor:
    """Test the compression logic."""
    
    def test_compress_metrics(self):
        """Test metric compression keeps only significant values."""
        compressor = SummaryCompressor(target_mb_per_day=1.0)
        
        attrs = {
            "metrics": {
                "important_metric": {"count": 1000, "sum": 50000.0, "avg": 50.0},
                "minor_metric": {"count": 2, "sum": 5.0, "avg": 2.5},
                "zero_metric": {"count": 0, "sum": 0.0, "avg": 0.0}
            }
        }
        
        compressed, ratio = compressor.compress_summary(attrs)
        
        # Should keep important metric, drop others
        assert "important_metric" in compressed["metrics"]
        assert "minor_metric" not in compressed["metrics"]
        assert "zero_metric" not in compressed["metrics"]
        
        # Should use shortened keys
        important = compressed["metrics"]["important_metric"]
        assert "c" in important  # count -> c
        assert "s" in important  # sum -> s
        assert "a" in important  # avg -> a
        assert "count" not in important
    
    def test_compress_descriptions(self):
        """Test description compression removes verbosity."""
        compressor = SummaryCompressor(target_mb_per_day=1.0)
        
        attrs = {
            "messages_by_channel": {
                "channel_123": {"count": 100, "description": "Long channel description"},
                "channel_456": {"count": 50, "other_data": "stuff"}
            },
            "participants": {
                "user_1": {
                    "message_count": 25,
                    "author_name": "Very Long Username That Should Be Truncated",
                    "extra_field": "data"
                }
            },
            "detailed_description": "This is a very detailed description",
            "full_context": "Lots of context here"
        }
        
        compressed, _ = compressor.compress_summary(attrs)
        
        # Channels should only have counts
        assert compressed["messages_by_channel"]["channel_123"] == 100
        assert compressed["messages_by_channel"]["channel_456"] == 50
        
        # Participants compressed
        user = compressed["participants"]["user_1"]
        assert user["msg_count"] == 25
        assert len(user["name"]) <= 20
        assert "extra_field" not in user
        
        # Verbose fields removed
        assert "detailed_description" not in compressed
        assert "full_context" not in compressed
    
    def test_remove_redundancy(self):
        """Test redundancy removal."""
        compressor = SummaryCompressor(target_mb_per_day=1.0)
        
        attrs = {
            "period_start": "2025-07-01T00:00:00Z",
            "start_time": "2025-07-01T00:00:00Z",  # Duplicate
            "period_end": "2025-07-02T00:00:00Z",
            "end_time": "2025-07-02T00:00:00Z",  # Duplicate
            "errors": [
                {"type": "timeout", "message": "Request timed out"},
                {"type": "timeout", "message": "Another timeout"},
                {"type": "parse", "message": "Parse error"}
            ],
            "created_by": "system",
            "version": 1
        }
        
        compressed, _ = compressor.compress_summary(attrs)
        
        # Duplicates removed
        assert "start_time" not in compressed
        assert "end_time" not in compressed
        
        # Errors summarized
        assert "errors" not in compressed
        assert compressed["error_summary"]["timeout"] == 2
        assert compressed["error_summary"]["parse"] == 1
        
        # Low-value fields removed
        assert "created_by" not in compressed
        assert "version" not in compressed
    
    def test_estimate_daily_size(self):
        """Test daily size estimation."""
        compressor = SummaryCompressor(target_mb_per_day=1.0)
        
        # Create some summaries
        summaries = [
            {"data": "A" * 1024},  # 1KB
            {"data": "B" * 2048},  # 2KB
            {"data": "C" * 1024}   # 1KB
        ]
        
        # Total 4KB over 30 days
        daily_mb = compressor.estimate_daily_size(summaries, 30)
        expected_mb = (4 * 1024) / (1024 * 1024) / 30  # ~0.00013 MB/day
        
        assert abs(daily_mb - expected_mb) < 0.0001


class TestProfoundConsolidation:
    """Test profound consolidation process."""
    
    @pytest.mark.asyncio
    async def test_compress_daily_summaries_in_place(self, tsdb_service, mock_db_connection):
        """Test that profound consolidation compresses summaries in-place."""
        with patch('ciris_engine.logic.persistence.db.core.get_db_connection', return_value=mock_db_connection):
            cursor = mock_db_connection.cursor()
            
            # Create daily summaries for July 2025
            for day in range(1, 32):  # Full month
                date = datetime(2025, 7, day, tzinfo=timezone.utc)
                node_id = f"tsdb_summary_daily_{date.strftime('%Y%m%d')}"
                attrs = create_daily_summary(date, large=True)
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, version, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    node_id,
                    "tsdb_summary",
                    "local",
                    json.dumps(attrs),
                    1,
                    date.isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Check size before compression
            cursor.execute("SELECT attributes_json FROM graph_nodes")
            before_size = sum(len(row[0]) for row in cursor.fetchall())
            
            # Run profound consolidation
            await tsdb_service._run_profound_consolidation()
            
            # Check that nodes were updated, not created
            cursor.execute("SELECT COUNT(*) as count FROM graph_nodes")
            assert cursor.fetchone()['count'] == 31  # Same number of nodes
            
            # Check that nodes were compressed
            cursor.execute("""
                SELECT node_id, attributes_json, version
                FROM graph_nodes
                WHERE node_type = 'tsdb_summary'
                ORDER BY node_id
            """)
            
            compressed_count = 0
            after_size = 0
            
            for node_id, attrs_json, version in cursor.fetchall():
                attrs = json.loads(attrs_json)
                after_size += len(attrs_json)
                
                # Check compression metadata
                if attrs.get('profound_compressed'):
                    compressed_count += 1
                    assert 'compression_date' in attrs
                    assert 'compression_ratio' in attrs
                    assert attrs['compression_ratio'] > 0
                    assert version == 2  # Version incremented
                    
                    # Check that verbose data was removed
                    assert 'detailed_description' not in attrs
                    assert 'full_context' not in attrs
                    assert 'debug_info' not in attrs
            
            assert compressed_count == 31  # All summaries compressed
            assert after_size < before_size  # Total size reduced
            
            reduction_ratio = 1.0 - (after_size / before_size)
            assert reduction_ratio > 0.3  # At least 30% reduction
    
    @pytest.mark.asyncio
    async def test_skip_compression_if_under_target(self, tsdb_service, mock_db_connection):
        """Test that compression is skipped if already under target."""
        # Set high target so compression isn't needed
        tsdb_service._profound_target_mb_per_day = 100.0
        
        with patch('ciris_engine.logic.persistence.db.core.get_db_connection', return_value=mock_db_connection):
            cursor = mock_db_connection.cursor()
            
            # Create small daily summaries
            for day in range(1, 8):  # Just one week
                date = datetime(2025, 7, day, tzinfo=timezone.utc)
                node_id = f"tsdb_summary_daily_{date.strftime('%Y%m%d')}"
                attrs = create_daily_summary(date, large=False)  # Small summaries
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    node_id,
                    "tsdb_summary",
                    "local",
                    json.dumps(attrs),
                    date.isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Run profound consolidation
            await tsdb_service._run_profound_consolidation()
            
            # Check that nodes were NOT compressed
            cursor.execute("""
                SELECT attributes_json
                FROM graph_nodes
                WHERE json_extract(attributes_json, '$.profound_compressed') = true
            """)
            
            assert cursor.fetchone() is None  # No compression happened
    
    @pytest.mark.asyncio
    async def test_cleanup_old_basic_summaries(self, tsdb_service, mock_db_connection):
        """Test that old basic summaries are cleaned up during profound consolidation."""
        with patch('ciris_engine.logic.persistence.db.core.get_db_connection', return_value=mock_db_connection):
            cursor = mock_db_connection.cursor()
            
            # Create daily summaries for July
            for day in range(1, 32):
                date = datetime(2025, 7, day, tzinfo=timezone.utc)
                node_id = f"tsdb_summary_daily_{date.strftime('%Y%m%d')}"
                attrs = create_daily_summary(date)
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    node_id,
                    "tsdb_summary",
                    "local",
                    json.dumps(attrs),
                    date.isoformat()
                ))
            
            # Also create some old basic summaries (from June)
            for day in range(1, 10):
                date = datetime(2025, 6, day, tzinfo=timezone.utc)
                for hour in [0, 6, 12, 18]:
                    period_start = date.replace(hour=hour)
                    node_id = f"tsdb_summary_{period_start.strftime('%Y%m%d_%H')}"
                    attrs = {
                        "consolidation_level": "basic",
                        "period_start": period_start.isoformat(),
                        "period_end": (period_start + timedelta(hours=6)).isoformat()
                    }
                    
                    cursor.execute("""
                        INSERT INTO graph_nodes 
                        (node_id, node_type, scope, attributes_json, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        node_id,
                        "tsdb_summary",
                        "local",
                        json.dumps(attrs),
                        period_start.isoformat()
                    ))
            
            mock_db_connection.commit()
            
            # Count basic summaries before
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_nodes
                WHERE json_extract(attributes_json, '$.consolidation_level') = 'basic'
            """)
            basic_before = cursor.fetchone()['count']
            assert basic_before == 36  # 9 days * 4 summaries per day
            
            # Run profound consolidation
            await tsdb_service._run_profound_consolidation()
            
            # Count basic summaries after
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_nodes
                WHERE json_extract(attributes_json, '$.consolidation_level') = 'basic'
            """)
            basic_after = cursor.fetchone()['count']
            assert basic_after == 0  # All cleaned up (older than 30 days)
    
    @pytest.mark.asyncio  
    async def test_month_boundary_handling(self, tsdb_service, mock_db_connection):
        """Test consolidation handles month boundaries correctly."""
        # Set time to September 1st to consolidate August
        tsdb_service._time_service.now = Mock(
            return_value=datetime(2025, 9, 1, 1, 0, 0, tzinfo=timezone.utc)
        )
        
        with patch('ciris_engine.logic.persistence.db.core.get_db_connection', return_value=mock_db_connection):
            cursor = mock_db_connection.cursor()
            
            # Create summaries for August (31 days)
            for day in range(1, 32):
                date = datetime(2025, 8, day, tzinfo=timezone.utc)
                node_id = f"tsdb_summary_daily_{date.strftime('%Y%m%d')}"
                attrs = create_daily_summary(date)
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    node_id,
                    "tsdb_summary",
                    "local",
                    json.dumps(attrs),
                    date.isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Run consolidation
            await tsdb_service._run_profound_consolidation()
            
            # Verify only August summaries were compressed
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_nodes
                WHERE json_extract(attributes_json, '$.profound_compressed') = true
                  AND json_extract(attributes_json, '$.period_start') LIKE '2025-08-%'
            """)
            
            assert cursor.fetchone()['count'] == 31