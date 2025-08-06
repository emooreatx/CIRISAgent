#!/usr/bin/env python3
"""Check edge count in database."""
import sqlite3


def check_edges():
    """Check edges in database."""
    db_path = "/app/data/ciris_engine.db"

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Count total edges
    cursor.execute("SELECT COUNT(*) FROM graph_edges")
    total_edges = cursor.fetchone()[0]
    print(f"Total edges in database: {total_edges}")

    # Count edges by type
    cursor.execute(
        """
        SELECT edge_type, COUNT(*)
        FROM graph_edges
        GROUP BY edge_type
        ORDER BY COUNT(*) DESC
    """
    )
    print("\nEdges by type:")
    for edge_type, count in cursor.fetchall():
        print(f"  {edge_type}: {count}")

    # Sample some edges
    cursor.execute(
        """
        SELECT edge_id, edge_type, source_id, target_id
        FROM graph_edges
        LIMIT 10
    """
    )
    print("\nSample edges:")
    for row in cursor.fetchall():
        print(f"  {row[0]} [{row[1]}]: {row[2]} -> {row[3]}")

    conn.close()


if __name__ == "__main__":
    check_edges()
