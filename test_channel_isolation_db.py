#!/usr/bin/env python3
"""Test channel isolation by examining the database directly"""

import sqlite3
import json
import os

def check_memory_isolation(db_path):
    """Check how memories are stored in the database"""
    
    if not os.path.exists(db_path):
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Check graph_nodes table structure
    print("\n=== Graph Nodes Table Structure ===")
    cursor.execute("PRAGMA table_info(graph_nodes)")
    columns = cursor.fetchall()
    for col in columns:
        print(f"  {col[1]} ({col[2]})")
    
    # Look for recent memory nodes
    print("\n=== Recent Memory Nodes ===")
    cursor.execute("""
        SELECT node_id, node_type, scope, attributes_json, created_at
        FROM graph_nodes
        WHERE node_type IN ('CONCEPT', 'OBSERVATION', 'USER')
        ORDER BY created_at DESC
        LIMIT 10
    """)
    
    nodes = cursor.fetchall()
    for node in nodes:
        node_id, node_type, scope, attributes_json, created_at = node
        print(f"\nNode ID: {node_id}")
        print(f"Type: {node_type}, Scope: {scope}")
        print(f"Created: {created_at}")
        
        if attributes_json:
            try:
                attrs = json.loads(attributes_json)
                # Look for channel_id in attributes
                if 'channel_id' in attrs:
                    print(f"Channel ID: {attrs['channel_id']}")
                elif 'context' in attrs and isinstance(attrs['context'], dict):
                    if 'channel_id' in attrs['context']:
                        print(f"Channel ID (from context): {attrs['context']['channel_id']}")
                
                # Show some attribute keys
                print(f"Attributes: {list(attrs.keys())[:5]}...")
            except json.JSONDecodeError:
                print("Attributes: <invalid JSON>")
    
    # Check for ObservationNode entries specifically
    print("\n=== Observation Nodes ===")
    cursor.execute("""
        SELECT node_id, attributes_json
        FROM graph_nodes  
        WHERE node_type = 'OBSERVATION'
        ORDER BY created_at DESC
        LIMIT 5
    """)
    
    obs_nodes = cursor.fetchall()
    for node_id, attrs_json in obs_nodes:
        print(f"\nObservation {node_id}:")
        if attrs_json:
            try:
                attrs = json.loads(attrs_json)
                if 'channel_id' in attrs:
                    print(f"  Channel: {attrs['channel_id']}")
                if 'content' in attrs:
                    print(f"  Content: {attrs['content'][:100]}...")
            except:
                pass
    
    conn.close()

def check_container_db(container_name):
    """Check database in a specific container"""
    print(f"\n{'='*60}")
    print(f"Checking {container_name}")
    print(f"{'='*60}")
    
    # Copy database from container
    os.system(f"docker cp {container_name}:/app/data/ciris_engine.db /tmp/{container_name}_db.sqlite 2>/dev/null")
    
    db_path = f"/tmp/{container_name}_db.sqlite"
    if os.path.exists(db_path):
        check_memory_isolation(db_path)
        os.remove(db_path)
    else:
        print(f"Could not access database from {container_name}")

if __name__ == "__main__":
    # Check container 3
    check_container_db("ciris_mock_llm_container3")
    
    print("\n\n=== CHANNEL ISOLATION ANALYSIS ===")
    print("""
    Key Questions:
    1. Are channel_id values stored with memory nodes?
    2. Is channel_id used to filter recall operations?
    3. Can one channel access another channel's memories?
    
    Expected Behavior:
    - Each memory should be tagged with its source channel_id
    - Recall operations should filter by the requesting channel_id
    - Cross-channel access should be prevented
    """)