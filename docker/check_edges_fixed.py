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

    # Get table schema
    cursor.execute("PRAGMA table_info(graph_edges)")
    print("\nTable schema:")
    for col in cursor.fetchall():
        print(f"  {col[1]} ({col[2]})")

    # Sample some edges
    cursor.execute(
        """
        SELECT *
        FROM graph_edges
        LIMIT 5
    """
    )
    print("\nSample edges:")
    cols = [desc[0] for desc in cursor.description]
    print(f"  Columns: {cols}")
    for row in cursor.fetchall():
        print(f"  {row}")

    conn.close()


if __name__ == "__main__":
    check_edges()
