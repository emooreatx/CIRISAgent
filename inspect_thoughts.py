#!/usr/bin/env python3
"""
Inspect thoughts in the CIRIS database.
"""
import sqlite3
from datetime import datetime
from pathlib import Path
import json

def inspect_thoughts():
    db_path = Path("data/ciris_engine.db")
    if not db_path.exists():
        print(f"Database not found at {db_path}")
        return
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Get all thoughts ordered by created_at
    cursor.execute("""
        SELECT 
            thought_id,
            source_task_id,
            content,
            status,
            thought_type,
            action_type,
            created_at,
            updated_at,
            metadata
        FROM thoughts
        ORDER BY created_at DESC
        LIMIT 50
    """)
    
    thoughts = cursor.fetchall()
    
    print(f"\n=== Found {len(thoughts)} recent thoughts ===\n")
    
    # Group by status
    status_counts = {}
    for thought in thoughts:
        status = thought['status']
        status_counts[status] = status_counts.get(status, 0) + 1
    
    print("Status summary:")
    for status, count in sorted(status_counts.items()):
        print(f"  {status}: {count}")
    
    print("\n=== Detailed thought information ===\n")
    
    # Show details for each thought
    for thought in thoughts[:20]:  # Show first 20
        print(f"Thought ID: {thought['thought_id']}")
        print(f"  Task ID: {thought['source_task_id']}")
        print(f"  Status: {thought['status']}")
        print(f"  Type: {thought['thought_type']}")
        print(f"  Action: {thought['action_type']}")
        print(f"  Created: {thought['created_at']}")
        print(f"  Updated: {thought['updated_at']}")
        print(f"  Content: {thought['content'][:100]}..." if len(thought['content']) > 100 else f"  Content: {thought['content']}")
        
        # Parse metadata if it exists
        if thought['metadata']:
            try:
                metadata = json.loads(thought['metadata'])
                print(f"  Metadata: {json.dumps(metadata, indent=4)}")
            except:
                print(f"  Metadata: {thought['metadata']}")
        print()
    
    # Look for orphaned wakeup thoughts
    print("\n=== Checking for orphaned wakeup thoughts ===\n")
    
    cursor.execute("""
        SELECT 
            t.thought_id,
            t.source_task_id,
            t.status as thought_status,
            t.created_at,
            k.status as task_status,
            k.task_id
        FROM thoughts t
        LEFT JOIN tasks k ON t.source_task_id = k.task_id
        WHERE (
            t.source_task_id LIKE 'WAKEUP_%' OR
            t.source_task_id LIKE 'VERIFY_IDENTITY_%' OR
            t.source_task_id LIKE 'VALIDATE_INTEGRITY_%' OR
            t.source_task_id LIKE 'EVALUATE_RESILIENCE_%' OR
            t.source_task_id LIKE 'ACCEPT_INCOMPLETENESS_%' OR
            t.source_task_id LIKE 'EXPRESS_GRATITUDE_%'
        )
        AND t.status IN ('PENDING', 'PROCESSING')
        ORDER BY t.created_at DESC
    """)
    
    orphaned = cursor.fetchall()
    
    if orphaned:
        print(f"Found {len(orphaned)} potentially orphaned wakeup thoughts:")
        for thought in orphaned:
            print(f"\nThought: {thought['thought_id']}")
            print(f"  Task ID: {thought['source_task_id']}")
            print(f"  Thought Status: {thought['thought_status']}")
            print(f"  Task Status: {thought['task_status'] if thought['task_status'] else 'TASK NOT FOUND'}")
            print(f"  Created: {thought['created_at']}")
    else:
        print("No orphaned wakeup thoughts found.")
    
    # Check for the specific thoughts mentioned in the log
    print("\n=== Checking for specific deleted thoughts ===\n")
    
    deleted_thought_ids = [
        'th_std_12d6a185-0ce2-4761-94f4-8d91adfd4ea4',
        'th_std_30b690a2-8084-4d08-ad47-3d089af45175',
        'th_std_11fa7310-74f5-4d9e-99be-e5f8b1c197fe',
        'th_std_07678e3c-ddf1-466f-97d0-940a139dbbb1',
        'th_std_7ae0cc12-119b-4a11-b51e-fcd6e4fd850e',
        'th_followup_th_std_1_2fe78527-1c0',
        'th_followup_th_std_3_d82e688b-221',
        'th_followup_th_std_1_6e3f4db9-cd8',
        'th_followup_th_std_0_35a0c294-d9f',
        'th_followup_th_std_7_3e02f405-d31'
    ]
    
    for thought_id in deleted_thought_ids:
        cursor.execute("SELECT thought_id, status FROM thoughts WHERE thought_id = ?", (thought_id,))
        result = cursor.fetchone()
        if result:
            print(f"{thought_id}: Still exists with status {result['status']}")
        else:
            print(f"{thought_id}: DELETED (not found)")
    
    conn.close()

if __name__ == "__main__":
    inspect_thoughts()