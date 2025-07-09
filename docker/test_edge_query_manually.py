#!/usr/bin/env python3
"""Test edge query manually."""
import sqlite3
import json

def test_edge_query():
    """Test the exact edge query from memory.py."""
    db_path = "/app/data/ciris_engine.db"
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Get some nodes that should have edges
    test_node_ids = [
        'trace_summary_20250708_12',
        'conversation_summary_20250706_00',
        'tsdb_summary_20250706_12',
        'dream_schedule_1751953692',
        'dream_schedule_1751926349'
    ]
    
    print(f"Testing edge query with {len(test_node_ids)} nodes:")
    for nid in test_node_ids:
        print(f"  {nid}")
    
    # Run the exact query from memory.py
    placeholders = ','.join('?' * len(test_node_ids))
    query = f"""
    SELECT edge_id, source_node_id, target_node_id, scope, relationship, weight, attributes_json, created_at
    FROM graph_edges
    WHERE source_node_id IN ({placeholders}) OR target_node_id IN ({placeholders})
    """
    
    cursor.execute(query, test_node_ids + test_node_ids)
    edges = cursor.fetchall()
    
    print(f"\nFound {len(edges)} edges")
    for edge in edges[:10]:
        print(f"\nEdge: {edge[0]}")
        print(f"  {edge[1]} --[{edge[4]}]--> {edge[2]}")
        print(f"  scope: {edge[3]}, weight: {edge[5]}")
        if edge[6]:
            attrs = json.loads(edge[6])
            print(f"  attributes: {json.dumps(attrs, indent=2)}")
    
    conn.close()

if __name__ == "__main__":
    test_edge_query()