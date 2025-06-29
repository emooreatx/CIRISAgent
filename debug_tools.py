#!/usr/bin/env python3
"""
CIRIS Debug Tools - Direct persistence and protocol queries for troubleshooting.

Usage:
    python debug_tools.py tasks              # List all tasks with status
    python debug_tools.py task <task_id>     # Show task details with thoughts
    python debug_tools.py thoughts <task_id> # List thoughts for a task
    python debug_tools.py thought <id>       # Show thought details
    python debug_tools.py channel <task_id>  # Trace channel context
    python debug_tools.py correlations       # Show recent service correlations
    python debug_tools.py dead-letter        # Show dead letter queue
    python debug_tools.py api-messages       # Show API message queue
"""

import sys
import json
from datetime import datetime
from pathlib import Path

# Add the project root to path
sys.path.insert(0, str(Path(__file__).parent))

from ciris_engine.logic import persistence
from ciris_engine.logic.persistence.db.core import get_db_connection
from ciris_engine.schemas.foundational_schemas_v1 import TaskStatus, ThoughtStatus


def list_tasks(status_filter=None):
    """List all tasks with basic info."""
    tasks = persistence.get_all_tasks()
    if status_filter:
        tasks = [t for t in tasks if t.status.value == status_filter]
    
    print(f"\n{'='*100}")
    print(f"TASKS ({len(tasks)} total)")
    print(f"{'='*100}")
    print(f"{'Task ID':<40} {'Status':<15} {'Priority':<8} {'Description'}")
    print(f"{'-'*100}")
    
    for task in sorted(tasks, key=lambda t: t.created_at, reverse=True)[:20]:
        desc = task.description[:40] + "..." if len(task.description) > 40 else task.description
        print(f"{task.task_id:<40} {task.status.value:<15} {task.priority:<8} {desc}")


def show_task_details(task_id):
    """Show detailed task information including thoughts."""
    task = persistence.get_task_by_id(task_id)
    if not task:
        print(f"Task {task_id} not found")
        return
    
    print(f"\n{'='*100}")
    print(f"TASK DETAILS: {task_id}")
    print(f"{'='*100}")
    print(f"Description: {task.description}")
    print(f"Status: {task.status.value}")
    print(f"Priority: {task.priority}")
    print(f"Created: {task.created_at}")
    print(f"Updated: {task.updated_at}")
    
    # Show context
    print(f"\nContext Type: {type(task.context).__name__}")
    if hasattr(task.context, 'initial_task_context') and task.context.initial_task_context:
        itc = task.context.initial_task_context
        print(f"  Author: {itc.author_name} ({itc.author_id})")
        print(f"  Origin: {itc.origin_service}")
        if itc.channel_context:
            print(f"  Channel: {itc.channel_context.channel_id} ({itc.channel_context.channel_type})")
    
    # Show thoughts
    thoughts = persistence.get_thoughts_by_task_id(task_id)
    print(f"\nThoughts ({len(thoughts)}):")
    print(f"{'-'*100}")
    for i, thought in enumerate(thoughts):
        print(f"{i+1}. [{thought.thought_type.value}] (depth {thought.thought_depth}, status: {thought.status.value})")
        print(f"   ID: {thought.thought_id}")
        print(f"   Content: {thought.content[:80]}...")


def trace_channel_context(task_id):
    """Trace channel context through task and thoughts."""
    task = persistence.get_task_by_id(task_id)
    if not task:
        print(f"Task {task_id} not found")
        return
    
    print(f"\n{'='*100}")
    print(f"CHANNEL CONTEXT TRACE: {task_id}")
    print(f"{'='*100}")
    
    def extract_channel(context, prefix=""):
        """Extract channel info from context."""
        if not context:
            print(f"{prefix}Context: None")
            return
            
        print(f"{prefix}Context Type: {type(context).__name__}")
        
        if hasattr(context, 'initial_task_context') and context.initial_task_context:
            itc = context.initial_task_context
            if itc.channel_context:
                cc = itc.channel_context
                print(f"{prefix}  Channel via initial_task_context: {cc.channel_id} (type: {cc.channel_type})")
            else:
                print(f"{prefix}  No channel_context in initial_task_context")
        
        if hasattr(context, 'system_snapshot') and context.system_snapshot:
            ss = context.system_snapshot
            if ss.channel_context:
                cc = ss.channel_context
                print(f"{prefix}  Channel via system_snapshot: {cc.channel_id} (type: {cc.channel_type})")
            else:
                print(f"{prefix}  No channel_context in system_snapshot")
    
    print("\nTask Context:")
    extract_channel(task.context, "  ")
    
    thoughts = persistence.get_thoughts_by_task_id(task_id)
    print(f"\nThought Contexts ({len(thoughts)} thoughts):")
    for i, thought in enumerate(thoughts):
        print(f"\n{i+1}. Thought {thought.thought_id} [{thought.thought_type.value}]:")
        extract_channel(thought.context, "  ")


def show_correlations(limit=20):
    """Show recent service correlations."""
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT correlation_id, service_type, handler_name, action_type, 
               status, created_at, request_data
        FROM service_correlations 
        ORDER BY created_at DESC 
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    print(f"\n{'='*100}")
    print(f"RECENT CORRELATIONS ({len(rows)} shown)")
    print(f"{'='*100}")
    
    for row in rows:
        corr_id, svc_type, handler, action, status, created, req_data = row
        print(f"\n{created} - {handler} -> {action}")
        print(f"  Correlation: {corr_id}")
        print(f"  Status: {status}")
        if req_data:
            try:
                data = json.loads(req_data)
                if 'channel_id' in data:
                    print(f"  Channel: {data['channel_id']}")
                if 'thought_id' in data:
                    print(f"  Thought: {data['thought_id']}")
                if 'task_id' in data:
                    print(f"  Task: {data['task_id']}")
            except:
                pass


def show_dead_letter():
    """Show recent dead letter queue entries."""
    dead_letter_path = Path("logs/dead_letter_latest.log")
    if not dead_letter_path.exists():
        print("Dead letter log not found")
        return
    
    print(f"\n{'='*100}")
    print(f"DEAD LETTER QUEUE (last 50 lines)")
    print(f"{'='*100}")
    
    with open(dead_letter_path) as f:
        lines = f.readlines()
        for line in lines[-50:]:
            print(line.rstrip())


def show_api_messages(channel_id=None):
    """Show API message queue."""
    try:
        from ciris_engine.logic.adapters.api.api_adapter import APIAdapter
        # This is a debug tool, so we'll query the database directly
        conn = get_db_connection()
        
        # Check if there's a messages table (if API adapter stores them)
        cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name LIKE '%message%'")
        tables = cursor.fetchall()
        
        if tables:
            print(f"\n{'='*100}")
            print(f"MESSAGE TABLES FOUND:")
            print(f"{'='*100}")
            for table in tables:
                print(f"  - {table[0]}")
        else:
            print("No message tables found in database")
            
    except Exception as e:
        print(f"Error accessing API messages: {e}")


def main():
    """Main entry point."""
    if len(sys.argv) < 2:
        print(__doc__)
        return
    
    command = sys.argv[1]
    
    if command == "tasks":
        status = sys.argv[2] if len(sys.argv) > 2 else None
        list_tasks(status)
    
    elif command == "task" and len(sys.argv) > 2:
        show_task_details(sys.argv[2])
    
    elif command == "thoughts" and len(sys.argv) > 2:
        task_id = sys.argv[2]
        thoughts = persistence.get_thoughts_by_task_id(task_id)
        print(f"\nThoughts for task {task_id}:")
        for i, t in enumerate(thoughts):
            print(f"{i+1}. [{t.thought_type.value}] {t.thought_id} (depth {t.thought_depth}, status: {t.status.value})")
            print(f"   {t.content[:100]}...")
    
    elif command == "thought" and len(sys.argv) > 2:
        thought = persistence.get_thought_by_id(sys.argv[2])
        if thought:
            print(f"\nThought {thought.thought_id}:")
            print(f"  Type: {thought.thought_type.value}")
            print(f"  Status: {thought.status.value}")
            print(f"  Depth: {thought.thought_depth}")
            print(f"  Task: {thought.source_task_id}")
            print(f"  Content: {thought.content}")
            print(f"  Context: {thought.context}")
        else:
            print("Thought not found")
    
    elif command == "channel" and len(sys.argv) > 2:
        trace_channel_context(sys.argv[2])
    
    elif command == "correlations":
        show_correlations()
    
    elif command == "dead-letter":
        show_dead_letter()
    
    elif command == "api-messages":
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        show_api_messages(channel)
    
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
