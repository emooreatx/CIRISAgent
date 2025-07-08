#!/usr/bin/env python3
"""Check audit correlations directly in the container."""

import subprocess
import sys

# The Python code to run inside the container
script_content = '''
import sqlite3
from datetime import datetime, timezone, timedelta

# Connect to database
db_path = "/app/data/ciris_engine.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()

print("=== AUDIT CORRELATION INVESTIGATION ===\\n")

# 1. Check for any AUDIT_EVENT correlations
print("1. Checking for AUDIT_EVENT correlations:")
cursor.execute("""
    SELECT correlation_type, COUNT(*) as count
    FROM service_correlations
    WHERE correlation_type = 'audit_event'
    GROUP BY correlation_type
""")
result = cursor.fetchone()
print(f"   Found {result['count'] if result else 0} AUDIT_EVENT correlations\\n")

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

# 3. Check if audit_log table exists
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
            LIMIT 5
        """)
        print("   Top event types:")
        for row in cursor.fetchall():
            print(f"     {row['event_type']}: {row['count']}")
except sqlite3.OperationalError as e:
    print(f"   audit_log table error: {e}")

# 4. Check audit database specifically
print("\\n4. Checking ciris_audit.db:")
try:
    audit_conn = sqlite3.connect("/app/data/ciris_audit.db")
    audit_conn.row_factory = sqlite3.Row
    audit_cursor = audit_conn.cursor()
    
    audit_cursor.execute("SELECT COUNT(*) as count FROM audit_log")
    count = audit_cursor.fetchone()['count']
    print(f"   Found {count} entries in audit_log table in ciris_audit.db")
    
    if count > 0:
        audit_cursor.execute("""
            SELECT event_type, COUNT(*) as count
            FROM audit_log
            GROUP BY event_type
            ORDER BY count DESC
            LIMIT 5
        """)
        print("   Top event types in ciris_audit.db:")
        for row in audit_cursor.fetchall():
            print(f"     {row['event_type']}: {row['count']}")
    
    audit_conn.close()
except Exception as e:
    print(f"   Could not access ciris_audit.db: {e}")

# 5. Check for audit nodes in graph
print("\\n5. Checking for audit entries in graph_nodes:")
cursor.execute("""
    SELECT COUNT(*) as count
    FROM graph_nodes
    WHERE LOWER(node_type) LIKE '%audit%'
""")
count = cursor.fetchone()['count']
print(f"   Found {count} audit-related nodes in graph_nodes")

# 6. Check for correlations by audit_service
print("\\n6. Checking for correlations created by audit_service:")
cursor.execute("""
    SELECT handler_name, COUNT(*) as count
    FROM service_correlations
    WHERE handler_name LIKE '%audit%'
    GROUP BY handler_name
""")
for row in cursor.fetchall():
    print(f"   {row['handler_name']}: {row['count']}")

# 7. Recent handler actions
print("\\n7. Recent handler actions (last hour):")
cutoff = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
cursor.execute("""
    SELECT action_type, handler_name, COUNT(*) as count
    FROM service_correlations
    WHERE timestamp > ?
    GROUP BY action_type, handler_name
    ORDER BY count DESC
    LIMIT 10
""", (cutoff,))
for row in cursor.fetchall():
    print(f"   {row['action_type']} by {row['handler_name']}: {row['count']}")

conn.close()

print("\\n=== DIAGNOSIS ===")
print("Audit events are NOT stored as correlations in service_correlations table.")
print("They are stored in:")
print("1. audit_log table in ciris_audit.db (hash chain)")
print("2. graph_nodes as AUDIT_ENTRY nodes")
print("3. NOT in service_correlations (which is for service interactions)")
'''

# Run the script in the container
result = subprocess.run(
    ["docker", "exec", "ciris-mock", "python", "-c", script_content],
    capture_output=True,
    text=True
)

print(result.stdout)
if result.stderr:
    print("STDERR:", result.stderr)
    
sys.exit(result.returncode)