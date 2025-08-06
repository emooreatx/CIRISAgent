#!/usr/bin/env python3
"""Test edges directly."""
import sqlite3


def test_edges():
    """Test edges query."""
    db_path = "/app/data/ciris_engine.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Get some node IDs
    cursor.execute(
        """
        SELECT node_id
        FROM graph_nodes
        WHERE updated_at >= datetime('now', '-7 days')
        LIMIT 10
    """
    )
    node_ids = [row[0] for row in cursor.fetchall()]
    print(f"Found {len(node_ids)} recent nodes:")
    for nid in node_ids:
        print(f"  {nid}")

    # Check if any of these nodes have edges
    if node_ids:
        placeholders = ",".join("?" * len(node_ids))
        query = f"""
        SELECT edge_id, source_node_id, target_node_id, scope, relationship
        FROM graph_edges
        WHERE source_node_id IN ({placeholders}) OR target_node_id IN ({placeholders})
        """

        cursor.execute(query, node_ids + node_ids)
        edges = cursor.fetchall()
        print(f"\nFound {len(edges)} edges for these nodes:")
        for edge in edges[:10]:  # Show first 10
            print(f"  {edge[0]}: {edge[1]} --[{edge[4]}]--> {edge[2]}")

    conn.close()


if __name__ == "__main__":
    test_edges()
