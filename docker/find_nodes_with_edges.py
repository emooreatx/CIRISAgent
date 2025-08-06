#!/usr/bin/env python3
"""Find nodes that have edges."""
import sqlite3


def find_nodes_with_edges():
    """Find nodes that have edges."""
    db_path = "/app/data/ciris_engine.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Find distinct nodes that have edges
    cursor.execute(
        """
        SELECT DISTINCT node_id, node_type, updated_at
        FROM graph_nodes
        WHERE node_id IN (
            SELECT source_node_id FROM graph_edges
            UNION
            SELECT target_node_id FROM graph_edges
        )
        AND updated_at >= datetime('now', '-7 days')
        ORDER BY updated_at DESC
        LIMIT 20
    """
    )

    nodes_with_edges = cursor.fetchall()
    print(f"Found {len(nodes_with_edges)} nodes with edges updated in last 7 days:")
    for node_id, node_type, updated_at in nodes_with_edges:
        print(f"  {node_id} ({node_type}) - {updated_at}")

        # Show edges for this node
        cursor.execute(
            """
            SELECT edge_id, source_node_id, target_node_id, relationship
            FROM graph_edges
            WHERE source_node_id = ? OR target_node_id = ?
            LIMIT 3
        """,
            (node_id, node_id),
        )

        edges = cursor.fetchall()
        for edge_id, src, tgt, rel in edges:
            if src == node_id:
                print(f"    --> {tgt} [{rel}]")
            else:
                print(f"    <-- {src} [{rel}]")

    # Also check what types of nodes have edges
    cursor.execute(
        """
        SELECT node_type, COUNT(DISTINCT gn.node_id) as count
        FROM graph_nodes gn
        JOIN (
            SELECT source_node_id as node_id FROM graph_edges
            UNION
            SELECT target_node_id FROM graph_edges
        ) edges ON gn.node_id = edges.node_id
        GROUP BY node_type
        ORDER BY count DESC
    """
    )

    print("\n\nNode types with edges:")
    for node_type, count in cursor.fetchall():
        print(f"  {node_type}: {count} nodes")

    conn.close()


if __name__ == "__main__":
    find_nodes_with_edges()
