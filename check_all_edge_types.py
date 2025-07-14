from ciris_engine.logic.persistence.db.core import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Count all edge types
    cursor.execute("""
        SELECT relationship, COUNT(*) as count
        FROM graph_edges
        GROUP BY relationship
        ORDER BY count DESC
    """)
    
    print("All edge types in the database:")
    print("-" * 40)
    total_edges = 0
    for row in cursor:
        print(f"{row['relationship']:<25} {row['count']:>10,}")
        total_edges += row['count']
    print("-" * 40)
    print(f"{'TOTAL':<25} {total_edges:>10,}")
    
    # Check edges for a specific summary node
    print("\n\nEdges for tsdb_summary_20250714_00:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT relationship, COUNT(*) as count
        FROM graph_edges
        WHERE source_node_id = 'tsdb_summary_20250714_00'
           OR target_node_id = 'tsdb_summary_20250714_00'
        GROUP BY relationship
    """)
    
    for row in cursor:
        print(f"{row['relationship']:<25} {row['count']:>10}")
    
    # Check what a typical node in a consolidated period has
    print("\n\nEdges for a typical concept node:")
    print("-" * 40)
    
    cursor.execute("""
        SELECT e.relationship, e.source_node_id, e.target_node_id
        FROM graph_edges e
        WHERE e.target_node_id = 'dream_schedule_1752387332'
           OR e.source_node_id = 'dream_schedule_1752387332'
    """)
    
    for row in cursor:
        if row['source_node_id'] == 'dream_schedule_1752387332':
            print(f"OUT: {row['relationship']} -> {row['target_node_id']}")
        else:
            print(f"IN:  {row['source_node_id']} -> {row['relationship']}")
    
    # Check cross-summary edges
    print("\n\nChecking for cross-summary edges (e.g., SAME_DAY_SUMMARY):")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM graph_edges
        WHERE relationship IN ('SAME_DAY_SUMMARY', 'TEMPORAL_PREV', 'TEMPORAL_NEXT', 
                              'DRIVES_PROCESSING', 'GENERATES_METRICS', 'TEMPORAL_CORRELATION')
    """)
    cross_edges = cursor.fetchone()['count']
    print(f"Cross-summary relationship edges: {cross_edges}")
    
    # Check if we're creating all summary types
    print("\n\nSummary types for period 2025-07-14 00:00:")
    cursor.execute("""
        SELECT node_id, node_type
        FROM graph_nodes
        WHERE node_id LIKE '%20250714_00'
          AND node_type LIKE '%_summary'
        ORDER BY node_type
    """)
    
    for row in cursor:
        print(f"  {row['node_id']}")