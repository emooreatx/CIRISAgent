#!/usr/bin/env python3
"""
Run full consolidation and deletion for period 2025-07-03 12:00-18:00
"""
import sqlite3
import json
import asyncio
from datetime import datetime, timezone
from collections import defaultdict

# Import the actual consolidation service
import sys
sys.path.append('/home/emoore/CIRISAgent')
from ciris_engine.logic.services.graph.tsdb_consolidation.consolidators import (
    MetricsConsolidator,
    ConversationConsolidator,
    TraceConsolidator,
    AuditConsolidator,
    TaskConsolidator
)
from ciris_engine.logic.services.graph.tsdb_consolidation.consolidators.memory import (
    MemoryGraphConsolidator
)

def report_before_state():
    """Report the state before consolidation"""
    conn = sqlite3.connect('data/ciris_engine.db')
    cursor = conn.cursor()
    
    print("="*80)
    print("BEFORE CONSOLIDATION - Period: 2025-07-03 12:00-18:00")
    print("="*80)
    
    # Count nodes by type in period
    cursor.execute("""
        SELECT node_type, COUNT(*) as count
        FROM graph_nodes
        WHERE datetime(created_at) >= datetime('2025-07-03 12:00:00')
          AND datetime(created_at) < datetime('2025-07-03 18:00:00')
        GROUP BY node_type
        ORDER BY count DESC
    """)
    
    print("\nNodes in period:")
    total_nodes = 0
    for node_type, count in cursor.fetchall():
        print(f"  {node_type}: {count:,}")
        total_nodes += count
    print(f"  TOTAL: {total_nodes:,}")
    
    # Count edges
    cursor.execute("""
        SELECT COUNT(*) FROM graph_edges
    """)
    edge_count = cursor.fetchone()[0]
    print(f"\nTotal edges in database: {edge_count:,}")
    
    # Count service correlations in period
    conn_correlations = sqlite3.connect('data/ciris_correlations.db')
    cursor_corr = conn_correlations.cursor()
    
    cursor_corr.execute("""
        SELECT COUNT(*) FROM service_correlations
        WHERE datetime(created_at) >= datetime('2025-07-03 12:00:00')
          AND datetime(created_at) < datetime('2025-07-03 18:00:00')
    """)
    corr_count = cursor_corr.fetchone()[0]
    print(f"\nService correlations in period: {corr_count:,}")
    
    # Count audit entries
    conn_audit = sqlite3.connect('data/ciris_audit.db')
    cursor_audit = conn_audit.cursor()
    
    cursor_audit.execute("""
        SELECT COUNT(*) FROM audit_trail
        WHERE datetime(timestamp) >= datetime('2025-07-03 12:00:00')
          AND datetime(timestamp) < datetime('2025-07-03 18:00:00')
    """)
    audit_count = cursor_audit.fetchone()[0]
    print(f"Audit entries in period: {audit_count:,}")
    
    conn.close()
    conn_correlations.close()
    conn_audit.close()
    
    return total_nodes, corr_count, audit_count

async def run_consolidation():
    """Run the consolidation"""
    print("\n" + "="*80)
    print("RUNNING CONSOLIDATION")
    print("="*80)
    
    # Set up parameters
    start_time = datetime(2025, 7, 3, 12, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2025, 7, 3, 18, 0, 0, tzinfo=timezone.utc)
    
    # Create consolidators
    consolidators = [
        MetricsConsolidator(start_time, end_time),
        ConversationConsolidator(start_time, end_time),
        TraceConsolidator(start_time, end_time),
        AuditConsolidator(start_time, end_time),
        TaskConsolidator(start_time, end_time)
    ]
    
    # Memory consolidator (edges only)
    memory_consolidator = MemoryGraphConsolidator(start_time, end_time)
    
    # Run consolidation
    summaries = []
    for consolidator in consolidators:
        print(f"\nRunning {consolidator.__class__.__name__}...")
        summary = await consolidator.consolidate()
        if summary:
            summaries.append(summary)
            print(f"  Created: {summary.node_id}")
            print(f"  Edges created: {len(summary.edges)}")
    
    # Run memory consolidator
    print(f"\nRunning MemoryGraphConsolidator...")
    memory_edges = await memory_consolidator.consolidate()
    print(f"  Created {len(memory_edges)} edges")
    
    return summaries

def validate_and_delete():
    """Validate consolidation claims and delete consolidated data"""
    print("\n" + "="*80)
    print("VALIDATING AND DELETING CONSOLIDATED DATA")
    print("="*80)
    
    conn = sqlite3.connect('data/ciris_engine.db')
    cursor = conn.cursor()
    
    # Get summaries for this period
    cursor.execute("""
        SELECT node_id, node_type, attributes_json
        FROM graph_nodes
        WHERE node_type LIKE '%_summary'
          AND datetime(created_at) = datetime('2025-07-03 18:00:00')
        ORDER BY node_type
    """)
    
    summaries = cursor.fetchall()
    print(f"\nFound {len(summaries)} summaries to validate")
    
    total_deleted = 0
    
    for node_id, node_type, attrs_json in summaries:
        attrs = json.loads(attrs_json) if attrs_json else {}
        print(f"\n{node_type}: {node_id}")
        
        if node_type == 'tsdb_summary':
            claimed_count = attrs.get('source_node_count', 0)
            print(f"  Claims to have consolidated: {claimed_count:,} TSDB nodes")
            
            # Validate
            cursor.execute("""
                SELECT COUNT(*) FROM graph_nodes
                WHERE node_type = 'tsdb_data'
                  AND datetime(created_at) >= datetime('2025-07-03 12:00:00')
                  AND datetime(created_at) < datetime('2025-07-03 18:00:00')
            """)
            actual_count = cursor.fetchone()[0]
            print(f"  Actual count in database: {actual_count:,}")
            
            if claimed_count == actual_count:
                print("  ✓ Counts match! Deleting...")
                cursor.execute("""
                    DELETE FROM graph_nodes
                    WHERE node_type = 'tsdb_data'
                      AND datetime(created_at) >= datetime('2025-07-03 12:00:00')
                      AND datetime(created_at) < datetime('2025-07-03 18:00:00')
                """)
                deleted = cursor.rowcount
                print(f"  Deleted {deleted:,} TSDB nodes")
                total_deleted += deleted
            else:
                print("  ✗ COUNT MISMATCH! Not deleting.")
        
        elif node_type == 'audit_summary':
            claimed_count = attrs.get('source_node_count', 0)
            print(f"  Claims to have consolidated: {claimed_count:,} audit entries")
            
            # Validate
            cursor.execute("""
                SELECT COUNT(*) FROM graph_nodes
                WHERE node_type = 'audit_entry'
                  AND datetime(created_at) >= datetime('2025-07-03 12:00:00')
                  AND datetime(created_at) < datetime('2025-07-03 18:00:00')
            """)
            actual_count = cursor.fetchone()[0]
            print(f"  Actual count in database: {actual_count:,}")
            
            if claimed_count == actual_count:
                print("  ✓ Counts match! Deleting...")
                cursor.execute("""
                    DELETE FROM graph_nodes
                    WHERE node_type = 'audit_entry'
                      AND datetime(created_at) >= datetime('2025-07-03 12:00:00')
                      AND datetime(created_at) < datetime('2025-07-03 18:00:00')
                """)
                deleted = cursor.rowcount
                print(f"  Deleted {deleted:,} audit entries")
                total_deleted += deleted
            else:
                print("  ✗ COUNT MISMATCH! Not deleting.")
        
        elif node_type == 'trace_summary':
            # Delete service correlations
            conn_corr = sqlite3.connect('data/ciris_correlations.db')
            cursor_corr = conn_corr.cursor()
            
            claimed_count = attrs.get('source_correlation_count', 0)
            print(f"  Claims to have consolidated: {claimed_count:,} correlations")
            
            # Validate
            cursor_corr.execute("""
                SELECT COUNT(*) FROM service_correlations
                WHERE datetime(created_at) >= datetime('2025-07-03 12:00:00')
                  AND datetime(created_at) < datetime('2025-07-03 18:00:00')
            """)
            actual_count = cursor_corr.fetchone()[0]
            print(f"  Actual count in database: {actual_count:,}")
            
            if claimed_count == actual_count:
                print("  ✓ Counts match! Deleting...")
                cursor_corr.execute("""
                    DELETE FROM service_correlations
                    WHERE datetime(created_at) >= datetime('2025-07-03 12:00:00')
                      AND datetime(created_at) < datetime('2025-07-03 18:00:00')
                """)
                deleted = cursor_corr.rowcount
                print(f"  Deleted {deleted:,} correlations")
                total_deleted += deleted
                conn_corr.commit()
            else:
                print("  ✗ COUNT MISMATCH! Not deleting.")
            
            conn_corr.close()
    
    conn.commit()
    conn.close()
    
    return total_deleted

def report_after_state():
    """Report the state after consolidation and deletion"""
    conn = sqlite3.connect('data/ciris_engine.db')
    cursor = conn.cursor()
    
    print("\n" + "="*80)
    print("AFTER CONSOLIDATION AND DELETION")
    print("="*80)
    
    # Count all nodes by type
    cursor.execute("""
        SELECT node_type, COUNT(*) as count
        FROM graph_nodes
        GROUP BY node_type
        ORDER BY count DESC
    """)
    
    print("\nAll nodes remaining:")
    total_nodes = 0
    for node_type, count in cursor.fetchall():
        print(f"  {node_type}: {count:,}")
        total_nodes += count
    print(f"  TOTAL: {total_nodes:,}")
    
    # Count edges
    cursor.execute("""
        SELECT COUNT(*) FROM graph_edges
    """)
    edge_count = cursor.fetchone()[0]
    print(f"\nTotal edges: {edge_count:,}")
    
    # Show summaries
    cursor.execute("""
        SELECT node_id, attributes_json
        FROM graph_nodes
        WHERE node_type LIKE '%_summary'
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    print("\nLatest summaries:")
    for node_id, attrs_json in cursor.fetchall():
        attrs = json.loads(attrs_json) if attrs_json else {}
        period_start = attrs.get('period_start', '?')
        print(f"  {node_id} (period: {period_start})")
    
    conn.close()

async def main():
    # Report before
    nodes_before, corr_before, audit_before = report_before_state()
    
    # Run consolidation
    summaries = await run_consolidation()
    
    # Validate and delete
    deleted_count = validate_and_delete()
    
    # Report after
    report_after_state()
    
    # Final summary
    print("\n" + "="*80)
    print("CONSOLIDATION SUMMARY")
    print("="*80)
    print(f"Period: 2025-07-03 12:00:00 to 18:00:00")
    print(f"\nBefore:")
    print(f"  Nodes in period: {nodes_before:,}")
    print(f"  Correlations in period: {corr_before:,}")
    print(f"  Audit entries in period: {audit_before:,}")
    print(f"\nConsolidation:")
    print(f"  Summaries created: {len(summaries)}")
    print(f"  Records deleted: {deleted_count:,}")
    print(f"\nResult:")
    print(f"  Successfully consolidated {deleted_count:,} records into {len(summaries)} summaries")

if __name__ == "__main__":
    asyncio.run(main())