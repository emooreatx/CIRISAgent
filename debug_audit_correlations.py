#!/usr/bin/env python3
"""Debug script to investigate why audit events are not appearing as correlations."""

import sqlite3
import json
import subprocess
from datetime import datetime, timezone, timedelta
from pathlib import Path

def run_in_container():
    """Run the investigation inside the Docker container."""
    cmd = ["docker", "exec", "ciris-mock", "python", "-c", """
import sqlite3
import json
from datetime import datetime, timezone, timedelta

# Connect to database
db_path = '/app/data/ciris_engine.db'
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()"""]
    
    print("=== AUDIT CORRELATION INVESTIGATION ===\n")
    
    # 1. Check for any AUDIT_EVENT correlations
    print("1. Checking for AUDIT_EVENT correlations in service_correlations table:")
    cursor.execute("""
        SELECT correlation_type, COUNT(*) as count
        FROM service_correlations
        WHERE correlation_type = 'audit_event'
    """)
    result = cursor.fetchone()
    print(f"   Found {result['count'] if result else 0} AUDIT_EVENT correlations\n")
    
    # 2. Check all correlation types
    print("2. All correlation types in service_correlations:")
    cursor.execute("""
        SELECT correlation_type, COUNT(*) as count
        FROM service_correlations
        GROUP BY correlation_type
        ORDER BY count DESC
    """)
    for row in cursor.fetchall():
        print(f"   {row['correlation_type']}: {row['count']}")
    print()
    
    # 3. Check if audit_log table exists and has data
    print("3. Checking audit_log table (hash chain):")
    try:
        cursor.execute("SELECT COUNT(*) as count FROM audit_log")
        count = cursor.fetchone()['count']
        print(f"   Found {count} entries in audit_log table")
        
        if count > 0:
            cursor.execute("""
                SELECT event_type, COUNT(*) as count
                FROM audit_log
                GROUP BY event_type
                ORDER BY count DESC
                LIMIT 10
            """)
            print("   Top event types:")
            for row in cursor.fetchall():
                print(f"     {row['event_type']}: {row['count']}")
    except sqlite3.OperationalError:
        print("   audit_log table does not exist!")
    print()
    
    # 4. Check for audit entries in graph_nodes
    print("4. Checking for audit entries in graph_nodes:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM graph_nodes
        WHERE node_type = 'AUDIT_ENTRY' OR node_type = 'audit_entry'
    """)
    count = cursor.fetchone()['count']
    print(f"   Found {count} AUDIT_ENTRY nodes in graph_nodes")
    
    # Check for any nodes with 'audit' in the type
    cursor.execute("""
        SELECT DISTINCT node_type
        FROM graph_nodes
        WHERE LOWER(node_type) LIKE '%audit%'
    """)
    audit_types = cursor.fetchall()
    if audit_types:
        print("   Node types containing 'audit':")
        for row in audit_types:
            print(f"     {row['node_type']}")
    print()
    
    # 5. Check recent handler actions in correlations
    print("5. Recent handler actions in correlations (last 24 hours):")
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
    cursor.execute("""
        SELECT action_type, COUNT(*) as count
        FROM service_correlations
        WHERE timestamp > ?
        GROUP BY action_type
        ORDER BY count DESC
        LIMIT 10
    """, (cutoff,))
    for row in cursor.fetchall():
        print(f"   {row['action_type']}: {row['count']}")
    print()
    
    # 6. Look for any correlations that might be audit-related
    print("6. Searching for potential audit-related correlations:")
    cursor.execute("""
        SELECT correlation_id, action_type, handler_name, timestamp
        FROM service_correlations
        WHERE handler_name LIKE '%audit%' 
           OR action_type LIKE '%audit%'
           OR json_extract(request_data, '$.event_type') LIKE '%audit%'
        ORDER BY timestamp DESC
        LIMIT 5
    """)
    audit_related = cursor.fetchall()
    if audit_related:
        print("   Found audit-related correlations:")
        for row in audit_related:
            print(f"     {row['correlation_id']}: {row['action_type']} by {row['handler_name']} at {row['timestamp']}")
    else:
        print("   No audit-related correlations found")
    print()
    
    # 7. Check if audit service is creating any correlations
    print("7. Checking for correlations created by audit_service:")
    cursor.execute("""
        SELECT COUNT(*) as count
        FROM service_correlations
        WHERE handler_name = 'audit_service'
    """)
    count = cursor.fetchone()['count']
    print(f"   Found {count} correlations with handler_name='audit_service'")
    
    # 8. Sample a recent correlation to see its structure
    print("\n8. Sample recent correlation structure:")
    cursor.execute("""
        SELECT *
        FROM service_correlations
        ORDER BY timestamp DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    if row:
        print("   Recent correlation fields:")
        for key in row.keys():
            value = row[key]
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            print(f"     {key}: {value}")
    
    conn.close()
    
    print("\n=== DIAGNOSIS ===")
    print("Based on the investigation:")
    print("1. The audit_service is creating entries in audit_log table (hash chain)")
    print("2. It may also be creating nodes in graph_nodes as AUDIT_ENTRY type")
    print("3. But it does NOT appear to be creating correlations with type AUDIT_EVENT")
    print("4. This is likely because audit events are stored differently than other telemetry")
    print("\nThe audit service uses its own storage mechanisms:")
    print("- audit_log table for hash chain integrity")
    print("- graph nodes for graph-based storage")
    print("- NOT service_correlations table (which is for service interactions)")

if __name__ == "__main__":
    main()