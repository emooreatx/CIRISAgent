from ciris_engine.logic.persistence.db.core import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Get all summary nodes
    cursor.execute("""
        SELECT 
            node_id,
            json_extract(attributes_json, '$.period_start') as period_start,
            json_extract(attributes_json, '$.period_end') as period_end,
            json_extract(attributes_json, '$.consolidation_level') as level
        FROM graph_nodes
        WHERE node_type = 'tsdb_summary'
          AND json_extract(attributes_json, '$.consolidation_level') = 'basic'
        ORDER BY period_start DESC
        LIMIT 5
    """)
    
    summaries = cursor.fetchall()
    print(f"Checking {len(summaries)} summaries...\n")
    
    total_edges = 0
    
    for summary in summaries:
        summary_id = summary["node_id"]
        period_start = summary["period_start"]
        period_end = summary["period_end"]
        level = summary["level"]
        
        # Count SUMMARIZES edges from this summary
        cursor.execute("""
            SELECT COUNT(*) as edge_count
            FROM graph_edges
            WHERE source_node_id = ?
              AND relationship = 'SUMMARIZES'
        """, (summary_id,))
        
        edge_count = cursor.fetchone()["edge_count"]
        total_edges += edge_count
        
        print(f"{summary_id}:")
        print(f"  Level: {level}")
        print(f"  Period: {period_start} to {period_end}")
        print(f"  SUMMARIZES edges: {edge_count}")
        print()
    
    print(f"Total edges from these summaries: {total_edges}")
    
    # Check if consolidation_level filter is the issue
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM graph_nodes
        WHERE node_type = 'tsdb_summary'
          AND json_extract(attributes_json, '$.consolidation_level') = 'basic'
    """)
    basic_count = cursor.fetchone()["count"]
    
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM graph_nodes
        WHERE node_type = 'tsdb_summary'
          AND json_extract(attributes_json, '$.consolidation_level') IS NULL
    """)
    null_count = cursor.fetchone()["count"]
    
    print(f"\nSummaries with level='basic': {basic_count}")
    print(f"Summaries with level=NULL: {null_count}")