from ciris_engine.logic.persistence.db.core import get_db_connection

with get_db_connection() as conn:
    cursor = conn.cursor()
    
    # Check all summary types and their edges
    summary_types = ['tsdb_summary', 'conversation_summary', 'task_summary', 'trace_summary', 'audit_summary']
    
    for summary_type in summary_types:
        print(f"\n{summary_type.upper()}:")
        print("-" * 60)
        
        # Count summaries of this type
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM graph_nodes
            WHERE node_type = ?
        """, (summary_type,))
        
        summary_count = cursor.fetchone()['count']
        print(f"Total {summary_type} nodes: {summary_count}")
        
        # Count edges FROM these summaries
        cursor.execute("""
            SELECT e.relationship, COUNT(*) as count
            FROM graph_edges e
            INNER JOIN graph_nodes n ON e.source_node_id = n.node_id
            WHERE n.node_type = ?
            GROUP BY e.relationship
            ORDER BY count DESC
        """, (summary_type,))
        
        print(f"\nEdge types FROM {summary_type}:")
        total_edges = 0
        for row in cursor:
            print(f"  {row['relationship']:<30} {row['count']:>8,}")
            total_edges += row['count']
        
        if total_edges == 0:
            print("  (no edges)")
        else:
            print(f"  {'TOTAL':<30} {total_edges:>8,}")
            print(f"  Average edges per summary: {total_edges/summary_count:.1f}")
    
    # Check a specific period
    print("\n\nFor period 2025-07-13 00:00 to 06:00:")
    print("-" * 60)
    
    for summary_type in summary_types:
        summary_id = f"{summary_type.replace('_summary', '_summary')}_20250713_00"
        
        cursor.execute("""
            SELECT COUNT(*) as count
            FROM graph_edges
            WHERE source_node_id = ?
        """, (summary_id,))
        
        edge_count = cursor.fetchone()['count']
        
        if edge_count > 0:
            # Get breakdown
            cursor.execute("""
                SELECT relationship, COUNT(*) as count
                FROM graph_edges
                WHERE source_node_id = ?
                GROUP BY relationship
            """, (summary_id,))
            
            print(f"\n{summary_id}:")
            for row in cursor:
                print(f"  {row['relationship']}: {row['count']}")
        else:
            print(f"\n{summary_id}: NO EDGES")