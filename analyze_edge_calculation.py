from ciris_engine.logic.persistence.db.core import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Let's check a specific summary in detail
    summary_id = "tsdb_summary_20250714_00"
    
    # Count nodes in that period
    cursor.execute("""
        SELECT COUNT(*) as node_count
        FROM graph_nodes
        WHERE scope = 'local'
          AND node_type != 'tsdb_data'
          AND datetime(created_at) >= datetime('2025-07-14T00:00:00')
          AND datetime(created_at) < datetime('2025-07-14T06:00:00')
    """)
    nodes_in_period = cursor.fetchone()["node_count"]
    
    # Count edges FROM that summary
    cursor.execute("""
        SELECT COUNT(*) as edge_count
        FROM graph_edges
        WHERE source_node_id = ?
          AND relationship = 'SUMMARIZES'
    """, (summary_id,))
    edges_from_summary = cursor.fetchone()["edge_count"]
    
    print(f"Summary: {summary_id}")
    print(f"Nodes in period: {nodes_in_period}")
    print(f"Edges FROM summary: {edges_from_summary}")
    print(f"This means: 1 summary -> {edges_from_summary} nodes")
    print()
    
    # Now let's understand what "average edges per node" should mean
    print("Understanding 'average edges per node':")
    print("Option 1: Average edges FROM each summary node")
    print("Option 2: Average edges TO each summarized node")
    print("Option 3: Average edges per node (all nodes)")
    print()
    
    # Count total summaries and their edges
    cursor.execute("""
        SELECT COUNT(*) as summary_count
        FROM graph_nodes
        WHERE node_type = 'tsdb_summary'
    """)
    total_summaries = cursor.fetchone()["summary_count"]
    
    cursor.execute("""
        SELECT COUNT(*) as edge_count
        FROM graph_edges
        WHERE relationship = 'SUMMARIZES'
    """)
    total_summarizes_edges = cursor.fetchone()["edge_count"]
    
    print(f"Total summaries: {total_summaries}")
    print(f"Total SUMMARIZES edges: {total_summarizes_edges}")
    print(f"Average edges per SUMMARY: {total_summarizes_edges / total_summaries:.1f}")
    print()
    
    # Count nodes that RECEIVE summarizes edges
    cursor.execute("""
        SELECT COUNT(DISTINCT target_node_id) as nodes_with_edges
        FROM graph_edges
        WHERE relationship = 'SUMMARIZES'
    """)
    nodes_with_edges = cursor.fetchone()["nodes_with_edges"]
    
    print(f"Nodes that have SUMMARIZES edges pointing TO them: {nodes_with_edges}")
    print(f"Average edges per summarized node: {total_summarizes_edges / nodes_with_edges:.2f}")
    
    # Check if some nodes have multiple summary edges
    cursor.execute("""
        SELECT target_node_id, COUNT(*) as edge_count
        FROM graph_edges
        WHERE relationship = 'SUMMARIZES'
        GROUP BY target_node_id
        HAVING COUNT(*) > 1
        ORDER BY edge_count DESC
        LIMIT 10
    """)
    
    print("\nNodes with multiple SUMMARIZES edges:")
    for row in cursor:
        print(f"  {row['target_node_id']}: {row['edge_count']} edges")