#!/usr/bin/env python3
"""Debug memory query issues."""

import os
import sys
import sqlite3
from datetime import datetime, timezone

# Add the ciris_engine to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ciris_engine.logic.persistence import get_db_connection, get_all_graph_nodes, get_nodes_by_type
from ciris_engine.schemas.services.graph_core import GraphScope

def check_database():
    """Check what's in the database."""
    db_path = "/app/data/ciris_main.db"
    
    print("=== Database Check ===")
    print(f"Database path: {db_path}")
    print(f"Database exists: {os.path.exists(db_path)}")
    
    if os.path.exists(db_path):
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Count all nodes
            cursor.execute("SELECT COUNT(*) FROM graph_nodes")
            total = cursor.fetchone()[0]
            print(f"Total nodes: {total}")
            
            # Count by type
            cursor.execute("SELECT node_type, COUNT(*) FROM graph_nodes GROUP BY node_type")
            for row in cursor.fetchall():
                print(f"  {row[0]}: {row[1]}")
            
            # Show recent nodes
            print("\nRecent nodes:")
            cursor.execute("SELECT node_id, node_type, scope FROM graph_nodes ORDER BY updated_at DESC LIMIT 5")
            for row in cursor.fetchall():
                print(f"  {row[0]} ({row[1]}) in {row[2]}")

def test_persistence_functions():
    """Test the persistence functions directly."""
    print("\n=== Testing Persistence Functions ===")
    
    # Test get_all_graph_nodes
    print("\n1. Testing get_all_graph_nodes()...")
    nodes = get_all_graph_nodes(limit=5)
    print(f"Found {len(nodes)} nodes")
    for node in nodes:
        print(f"  - {node.id} ({node.type})")
    
    # Test wildcard with scope
    print("\n2. Testing get_all_graph_nodes(scope=LOCAL)...")
    nodes = get_all_graph_nodes(scope=GraphScope.LOCAL, limit=5)
    print(f"Found {len(nodes)} nodes in LOCAL scope")
    
    # Test get_nodes_by_type
    print("\n3. Testing get_nodes_by_type('concept')...")
    nodes = get_nodes_by_type(node_type='concept', limit=5)
    print(f"Found {len(nodes)} concept nodes")
    for node in nodes:
        print(f"  - {node.id}")

if __name__ == "__main__":
    if os.path.exists("/app/data/ciris_main.db"):
        # Running in container
        check_database()
        test_persistence_functions()
    else:
        print("This script should be run inside the container")
        print("Use: docker exec ciris-api-mock python /debug_memory_queries.py")