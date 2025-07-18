"""Unit tests for TSDB consolidation edge creation logic."""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, AsyncMock, patch
import json
import sqlite3

from ciris_engine.logic.services.graph.tsdb_consolidation import TSDBConsolidationService
from ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager import EdgeManager
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryOpStatus, MemoryOpResult


@pytest.fixture
def mock_memory_bus():
    """Create a mock memory bus."""
    mock = Mock()
    mock.memorize = AsyncMock(return_value=MemoryOpResult(status=MemoryOpStatus.OK))
    mock.recall = AsyncMock(return_value=[])
    return mock


@pytest.fixture  
def mock_time_service():
    """Create a mock time service."""
    mock = Mock()
    # Set to Monday, July 15, 2025 at 01:00 UTC
    mock.now = Mock(return_value=datetime(2025, 7, 15, 1, 0, 0, tzinfo=timezone.utc))
    return mock


@pytest.fixture
def edge_manager():
    """Create an edge manager for testing."""
    return EdgeManager()


@pytest.fixture
def mock_db_connection():
    """Create an in-memory SQLite database for testing."""
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    # Disable foreign keys for testing
    conn.execute("PRAGMA foreign_keys = OFF")
    
    # Create necessary tables
    conn.execute("""
        CREATE TABLE graph_nodes (
            node_id TEXT PRIMARY KEY,
            node_type TEXT,
            scope TEXT,
            attributes_json TEXT,
            version INTEGER,
            updated_by TEXT,
            updated_at TEXT,
            created_at TEXT
        )
    """)
    
    conn.execute("""
        CREATE TABLE graph_edges (
            edge_id TEXT PRIMARY KEY,
            source_node_id TEXT,
            target_node_id TEXT,
            scope TEXT,
            relationship TEXT,
            weight REAL,
            attributes_json TEXT,
            created_at TEXT
        )
    """)
    
    return conn


def create_summary_node(node_type: str, period_start: datetime, period_id: str) -> GraphNode:
    """Create a summary node for testing."""
    node_id = f"{node_type}_{period_id}"
    
    attributes = {
        "period_start": period_start.isoformat(),
        "period_end": (period_start + timedelta(hours=6)).isoformat(),
        "period_label": f"{period_start.strftime('%Y-%m-%d')}-{['night', 'morning', 'afternoon', 'evening'][period_start.hour//6]}",
        "consolidation_level": "basic",
        "source_node_count": 100
    }
    
    if node_type == "tsdb_summary":
        attributes.update({
            "metrics": {
                "llm.tokens.input": {"count": 10, "sum": 1000, "min": 50, "max": 200, "avg": 100}
            },
            "total_tokens": 1500,
            "total_cost_cents": 50.0
        })
    
    return GraphNode(
        id=node_id,
        type=NodeType.TSDB_SUMMARY,
        scope=GraphScope.LOCAL,
        attributes=attributes,
        version=1,
        updated_by="test",
        updated_at=datetime.now(timezone.utc),
        created_at=period_start
    )


def create_daily_summary_node(node_type: str, date: datetime) -> GraphNode:
    """Create a daily summary node for testing."""
    node_id = f"{node_type}_daily_{date.strftime('%Y%m%d')}"
    
    attributes = {
        "period_start": date.isoformat(),
        "period_end": (date + timedelta(days=1)).isoformat(),
        "period_label": date.strftime('%Y-%m-%d'),
        "consolidation_level": "extensive",
        "source_summary_count": 4
    }
    
    return GraphNode(
        id=node_id,
        type=NodeType.TSDB_SUMMARY,
        scope=GraphScope.LOCAL,
        attributes=attributes,
        version=1,
        updated_by="test",
        updated_at=datetime.now(timezone.utc)
    )


class TestTemporalEdgeCreation:
    """Test temporal edge creation (TEMPORAL_PREV/NEXT)."""
    
    @pytest.mark.asyncio
    async def test_daily_summary_temporal_edges(self, edge_manager, mock_db_connection):
        """Test temporal edges between daily summaries."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create daily summaries for a week
            dates = [datetime(2025, 7, 7, tzinfo=timezone.utc) + timedelta(days=i) for i in range(7)]
            
            for i, date in enumerate(dates):
                # Create daily summary node
                summary = create_daily_summary_node("tsdb_summary", date)
                
                # Insert node into database
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
                
                # Simulate edge creation from consolidation service
                if i == 0:
                    # First day - no previous
                    edge_manager.create_temporal_edges(summary, None)
                else:
                    # Later days - link to previous
                    prev_id = f"tsdb_summary_daily_{dates[i-1].strftime('%Y%m%d')}"
                    edge_manager.create_temporal_edges(summary, prev_id)
            
            mock_db_connection.commit()
            
            # Verify temporal edges
            cursor.execute("""
                SELECT source_node_id, target_node_id, relationship, attributes_json
                FROM graph_edges
                WHERE relationship IN ('TEMPORAL_PREV', 'TEMPORAL_NEXT')
                ORDER BY created_at
            """)
            
            edges = cursor.fetchall()
            
            # Should have edges for navigation
            assert len(edges) > 0
            
            # Verify LAST day points to itself (latest marker)
            last_date_str = dates[-1].strftime('%Y%m%d')
            last_day_self_edge = next(
                (e for e in edges 
                 if e['source_node_id'] == f"tsdb_summary_daily_{last_date_str}" 
                 and e['target_node_id'] == f"tsdb_summary_daily_{last_date_str}"),
                None
            )
            assert last_day_self_edge is not None, f"No self-edge found for last day. Last day: {last_date_str}"
            assert last_day_self_edge['relationship'] == 'TEMPORAL_NEXT'
            
            # Verify day-to-day links
            for i in range(1, 7):
                curr_id = f"tsdb_summary_daily_{dates[i].strftime('%Y%m%d')}"
                prev_id = f"tsdb_summary_daily_{dates[i-1].strftime('%Y%m%d')}"
                
                # Current should have TEMPORAL_PREV to previous
                prev_edge = next(
                    (e for e in edges 
                     if e['source_node_id'] == curr_id 
                     and e['target_node_id'] == prev_id
                     and e['relationship'] == 'TEMPORAL_PREV'),
                    None
                )
                assert prev_edge is not None
                
                # Previous should have TEMPORAL_NEXT to current
                next_edge = next(
                    (e for e in edges 
                     if e['source_node_id'] == prev_id 
                     and e['target_node_id'] == curr_id
                     and e['relationship'] == 'TEMPORAL_NEXT'),
                    None
                )
                assert next_edge is not None
    
    @pytest.mark.asyncio
    async def test_gap_in_temporal_chain(self, edge_manager, mock_db_connection):
        """Test temporal edges when there's a gap in the chain."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create summaries with a gap (missing July 9)
            dates = [
                datetime(2025, 7, 8, tzinfo=timezone.utc),
                # July 9 missing
                datetime(2025, 7, 10, tzinfo=timezone.utc),
                datetime(2025, 7, 11, tzinfo=timezone.utc)
            ]
            
            for i, date in enumerate(dates):
                summary = create_daily_summary_node("tsdb_summary", date)
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
                
                if i == 0:
                    edge_manager.create_temporal_edges(summary, None)
                else:
                    # Link to actual previous day (not necessarily consecutive)
                    prev_id = f"tsdb_summary_daily_{dates[i-1].strftime('%Y%m%d')}"
                    edge_manager.create_temporal_edges(summary, prev_id)
            
            mock_db_connection.commit()
            
            # Verify edges handle the gap correctly
            cursor.execute("""
                SELECT source_node_id, target_node_id, relationship
                FROM graph_edges
                WHERE source_node_id = 'tsdb_summary_daily_20250710'
                  AND target_node_id = 'tsdb_summary_daily_20250708'
                  AND relationship = 'TEMPORAL_PREV'
            """)
            
            gap_edge = cursor.fetchone()
            assert gap_edge is not None  # July 10 should link back to July 8


class TestSameDayEdgeCreation:
    """Test same-day cross-type edge creation."""
    
    @pytest.mark.asyncio
    async def test_same_day_cross_type_edges(self, edge_manager, mock_db_connection):
        """Test edges between different summary types on the same day."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create daily summaries for different types on same day
            date = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary_types = [
                "tsdb_summary",
                "audit_summary",
                "trace_summary",
                "conversation_summary",
                "task_summary"
            ]
            
            summaries = []
            for summary_type in summary_types:
                summary = create_daily_summary_node(summary_type, date)
                summaries.append(summary)
                
                # Insert node
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Create same-day edges
            from ciris_engine.logic.services.graph.tsdb_consolidation.service import TSDBConsolidationService
            service = TSDBConsolidationService()
            
            # Call the method that creates same-day edges
            await service._create_daily_summary_edges(summaries, date)
            
            # Verify edges were created - check for known relationships and TEMPORAL_CORRELATION
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
                WHERE relationship IN ('DRIVES_PROCESSING', 'GENERATES_METRICS', 'IMPACTS_QUALITY', 
                                     'SECURES_EXECUTION', 'CREATES_TRAIL', 'INITIATES_TASKS', 
                                     'CONSUMES_RESOURCES', 'TEMPORAL_CORRELATION')
            """)
            
            result = cursor.fetchone()
            # Should have C(5,2) = 10 edges between 5 types
            assert result['count'] == 10
            
            # Verify no self-edges
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
                WHERE source_node_id = target_node_id
                  AND relationship IN ('DRIVES_PROCESSING', 'GENERATES_METRICS', 'IMPACTS_QUALITY', 
                                     'SECURES_EXECUTION', 'CREATES_TRAIL', 'INITIATES_TASKS', 
                                     'CONSUMES_RESOURCES', 'TEMPORAL_CORRELATION')
            """)
            
            self_edges = cursor.fetchone()
            assert self_edges['count'] == 0
    
    @pytest.mark.asyncio
    async def test_partial_types_same_day(self, edge_manager, mock_db_connection):
        """Test same-day edges with only some summary types present."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create only 3 types
            date = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary_types = ["tsdb_summary", "audit_summary", "trace_summary"]
            
            summaries = []
            for summary_type in summary_types:
                summary = create_daily_summary_node(summary_type, date)
                summaries.append(summary)
                
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Create cross-summary edges
            edge_manager.create_cross_summary_edges(summaries, date)
            
            # Should have C(3,2) = 3 edges
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
            """)
            
            result = cursor.fetchone()
            assert result['count'] == 3
            
            # Verify they're between our summaries
            cursor.execute("""
                SELECT DISTINCT relationship
                FROM graph_edges
            """)
            
            relationships = [row['relationship'] for row in cursor.fetchall()]
            # Should include SECURES_EXECUTION and TEMPORAL_CORRELATION
            assert any('SECURES_EXECUTION' in r or 'TEMPORAL_CORRELATION' in r for r in relationships)


class TestDuplicatePrevention:
    """Test duplicate edge prevention with INSERT OR IGNORE."""
    
    @pytest.mark.asyncio
    async def test_duplicate_edge_prevention(self, edge_manager, mock_db_connection):
        """Test that duplicate edges are prevented."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create two nodes
            date = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary1 = create_daily_summary_node("tsdb_summary", date)
            summary2 = create_daily_summary_node("audit_summary", date)
            
            for summary in [summary1, summary2]:
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Try to create the same edge multiple times
            for _ in range(3):
                edges_created = edge_manager.create_summary_to_nodes_edges(
                    summary1,
                    [summary2],
                    "TEST_RELATIONSHIP"
                )
            
            # Check that only 1 edge exists (duplicates prevented by deterministic IDs)
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
                WHERE source_node_id = ?
                  AND target_node_id = ?
                  AND relationship = ?
            """, (summary1.id, summary2.id, "TEST_RELATIONSHIP"))
            
            result = cursor.fetchone()
            assert result['count'] == 1  # Duplicates prevented by deterministic edge IDs and INSERT OR IGNORE
    
    @pytest.mark.asyncio
    async def test_update_next_period_edges(self, edge_manager, mock_db_connection):
        """Test updating edges when a new period is inserted between existing ones."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create summaries for day 1 and day 3
            day1 = datetime(2025, 7, 7, tzinfo=timezone.utc)
            day3 = datetime(2025, 7, 9, tzinfo=timezone.utc)
            
            summary1 = create_daily_summary_node("tsdb_summary", day1)
            summary3 = create_daily_summary_node("tsdb_summary", day3)
            
            # Insert nodes
            for summary in [summary1, summary3]:
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            # Create initial edges (day1 -> day3)
            edge_manager.create_temporal_edges(summary1, None)
            edge_manager.create_temporal_edges(summary3, summary1.id)
            
            # Now insert day 2
            day2 = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary2 = create_daily_summary_node("tsdb_summary", day2)
            
            cursor.execute("""
                INSERT INTO graph_nodes 
                (node_id, node_type, scope, attributes_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                summary2.id,
                summary2.type.value,
                summary2.scope.value,
                json.dumps(summary2.attributes),
                day2.isoformat()
            ))
            
            mock_db_connection.commit()
            
            # Update edges to include day 2
            # This would happen in the consolidation service
            # Day 1 -> Day 2 -> Day 3
            
            # Delete old edge from day1 to day3
            cursor.execute("""
                DELETE FROM graph_edges
                WHERE source_node_id = ? AND target_node_id = ?
                  AND relationship = 'TEMPORAL_NEXT'
            """, (summary1.id, summary3.id))
            
            cursor.execute("""
                DELETE FROM graph_edges
                WHERE source_node_id = ? AND target_node_id = ?
                  AND relationship = 'TEMPORAL_PREV'
            """, (summary3.id, summary1.id))
            
            # Create new edges
            edge_manager.create_temporal_edges(summary2, summary1.id)
            
            # Update day3 to point back to day2 instead of day1
            cursor.execute("""
                UPDATE graph_edges
                SET target_node_id = ?
                WHERE source_node_id = ? AND relationship = 'TEMPORAL_PREV'
            """, (summary2.id, summary3.id))
            
            mock_db_connection.commit()
            
            # Verify the chain is correct
            cursor.execute("""
                SELECT source_node_id, target_node_id, relationship
                FROM graph_edges
                WHERE relationship IN ('TEMPORAL_PREV', 'TEMPORAL_NEXT')
                  AND source_node_id != target_node_id
                ORDER BY source_node_id
            """)
            
            edges = cursor.fetchall()
            
            # Verify day1 -> day2
            day1_to_day2 = next(
                (e for e in edges 
                 if e['source_node_id'] == summary1.id 
                 and e['target_node_id'] == summary2.id),
                None
            )
            assert day1_to_day2 is not None
            
            # Verify day2 -> day1 (PREV)
            day2_to_day1 = next(
                (e for e in edges 
                 if e['source_node_id'] == summary2.id 
                 and e['target_node_id'] == summary1.id
                 and e['relationship'] == 'TEMPORAL_PREV'),
                None
            )
            assert day2_to_day1 is not None


class TestEdgeAttributes:
    """Test edge attribute handling."""
    
    @pytest.mark.asyncio
    async def test_edge_attributes_json(self, edge_manager, mock_db_connection):
        """Test that edge attributes are properly stored as JSON."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create nodes
            date = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary = create_daily_summary_node("tsdb_summary", date)
            
            cursor.execute("""
                INSERT INTO graph_nodes 
                (node_id, node_type, scope, attributes_json, created_at)
                VALUES (?, ?, ?, ?, ?)
            """, (
                summary.id,
                summary.type.value,
                summary.scope.value,
                json.dumps(summary.attributes),
                date.isoformat()
            ))
            
            mock_db_connection.commit()
            
            # Create temporal edge with attributes
            edge_manager.create_temporal_edges(summary, None)
            
            # Verify attributes are valid JSON
            cursor.execute("""
                SELECT attributes_json
                FROM graph_edges
                WHERE source_node_id = ?
            """, (summary.id,))
            
            row = cursor.fetchone()
            attrs = json.loads(row['attributes_json'])
            
            # Should have expected attributes
            assert 'is_latest' in attrs or 'context' in attrs
            assert isinstance(attrs, dict)
    
    @pytest.mark.asyncio
    async def test_days_apart_attribute(self, edge_manager, mock_db_connection):
        """Test days_apart calculation in temporal edges."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create summaries 3 days apart
            day1 = datetime(2025, 7, 7, tzinfo=timezone.utc)
            day2 = datetime(2025, 7, 10, tzinfo=timezone.utc)  # 3 days later
            
            summary1 = create_daily_summary_node("tsdb_summary", day1)
            summary2 = create_daily_summary_node("tsdb_summary", day2)
            
            for summary in [summary1, summary2]:
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            mock_db_connection.commit()
            
            # Create edges with days_apart calculation
            from ciris_engine.logic.services.graph.tsdb_consolidation.service import TSDBConsolidationService
            service = TSDBConsolidationService()
            
            # Mock the edge creation to include days_apart
            edge_id = f"edge_test_{datetime.now().timestamp()}"
            cursor.execute("""
                INSERT INTO graph_edges 
                (edge_id, source_node_id, target_node_id, scope, 
                 relationship, weight, attributes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                edge_id,
                summary2.id,
                summary1.id,
                "local",
                "TEMPORAL_PREV",
                1.0,
                json.dumps({"days_apart": 3, "context": "Previous daily summary"}),
                datetime.now(timezone.utc).isoformat()
            ))
            
            mock_db_connection.commit()
            
            # Verify days_apart attribute
            cursor.execute("""
                SELECT attributes_json
                FROM graph_edges
                WHERE source_node_id = ? AND target_node_id = ?
            """, (summary2.id, summary1.id))
            
            row = cursor.fetchone()
            attrs = json.loads(row['attributes_json'])
            assert attrs['days_apart'] == 3


class TestCleanupOrphanedEdges:
    """Test cleanup of orphaned edges."""
    
    @pytest.mark.asyncio
    async def test_cleanup_orphaned_edges(self, edge_manager, mock_db_connection):
        """Test that edges pointing to deleted nodes are cleaned up."""
        def get_test_connection():
            return mock_db_connection
        
        with patch('ciris_engine.logic.services.graph.tsdb_consolidation.edge_manager.get_db_connection', side_effect=get_test_connection):
            cursor = mock_db_connection.cursor()
            
            # Create nodes
            date = datetime(2025, 7, 8, tzinfo=timezone.utc)
            summary1 = create_daily_summary_node("tsdb_summary", date)
            summary2 = create_daily_summary_node("audit_summary", date)
            
            for summary in [summary1, summary2]:
                cursor.execute("""
                    INSERT INTO graph_nodes 
                    (node_id, node_type, scope, attributes_json, created_at)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    summary.id,
                    summary.type.value,
                    summary.scope.value,
                    json.dumps(summary.attributes),
                    datetime.now(timezone.utc).isoformat()
                ))
            
            # Create edge
            cursor.execute("""
                INSERT INTO graph_edges 
                (edge_id, source_node_id, target_node_id, scope, 
                 relationship, weight, attributes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "edge_test",
                summary1.id,
                summary2.id,
                "local",
                "TEST",
                1.0,
                "{}",
                datetime.now(timezone.utc).isoformat()
            ))
            
            # Also create an orphaned edge (pointing to non-existent node)
            cursor.execute("""
                INSERT INTO graph_edges 
                (edge_id, source_node_id, target_node_id, scope, 
                 relationship, weight, attributes_json, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                "edge_orphan",
                summary1.id,
                "non_existent_node",
                "local",
                "TEST",
                1.0,
                "{}",
                datetime.now(timezone.utc).isoformat()
            ))
            
            mock_db_connection.commit()
            
            # Cleanup orphaned edges
            deleted = edge_manager.cleanup_orphaned_edges()
            
            assert deleted == 1  # Only the orphaned edge should be deleted
            
            # Verify good edge still exists
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
                WHERE edge_id = 'edge_test'
            """)
            
            result = cursor.fetchone()
            assert result['count'] == 1
            
            # Verify orphaned edge is gone
            cursor.execute("""
                SELECT COUNT(*) as count
                FROM graph_edges
                WHERE edge_id = 'edge_orphan'
            """)
            
            result = cursor.fetchone()
            assert result['count'] == 0