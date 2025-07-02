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
    python debug_tools.py trace <trace_id>   # Show trace hierarchy
    python debug_tools.py traces             # List recent trace IDs
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
from ciris_engine.schemas.runtime.enums import TaskStatus, ThoughtStatus


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


def show_correlations(limit=20, trace_id=None):
    """Show recent service correlations with trace hierarchy."""
    conn = get_db_connection()
    
    if trace_id:
        # Show trace hierarchy
        cursor = conn.execute("""
            SELECT correlation_id, service_type, handler_name, action_type, 
                   status, created_at, request_data, response_data, 
                   trace_id, span_id, parent_span_id, updated_at
            FROM service_correlations 
            WHERE trace_id = ?
            ORDER BY created_at ASC
        """, (trace_id,))
    else:
        # Show recent correlations
        cursor = conn.execute("""
            SELECT correlation_id, service_type, handler_name, action_type, 
                   status, created_at, request_data, response_data,
                   trace_id, span_id, parent_span_id, updated_at
            FROM service_correlations 
            ORDER BY created_at DESC 
            LIMIT ?
        """, (limit,))
    
    rows = cursor.fetchall()
    print(f"\n{'='*100}")
    print(f"{'TRACE HIERARCHY' if trace_id else 'RECENT CORRELATIONS'} ({len(rows)} shown)")
    print(f"{'='*100}")
    
    # Build parent-child relationships if showing trace
    traces = {}
    for row in rows:
        corr_id = row[0]
        traces[corr_id] = {
            'row': row,
            'children': []
        }
    
    # Link children to parents using span relationships
    span_to_corr = {}
    for corr_id, trace_info in traces.items():
        span_id = trace_info['row'][9]  # span_id
        if span_id:
            span_to_corr[span_id] = corr_id
    
    for corr_id, trace_info in traces.items():
        parent_span_id = trace_info['row'][10]  # parent_span_id
        if parent_span_id and parent_span_id in span_to_corr:
            parent_corr_id = span_to_corr[parent_span_id]
            if parent_corr_id in traces:
                traces[parent_corr_id]['children'].append(corr_id)
    
    # Display function with indentation
    def display_correlation(row, indent=0):
        corr_id, svc_type, handler, action, status, created, req_data, resp_data, trace_id, span_id, parent_span_id, updated = row
        prefix = "  " * indent + ("└─ " if indent > 0 else "")
        
        # Calculate duration
        duration = ""
        if updated and created:
            try:
                start = datetime.fromisoformat(created.replace('Z', '+00:00'))
                end = datetime.fromisoformat(updated.replace('Z', '+00:00'))
                duration_ms = (end - start).total_seconds() * 1000
                duration = f" [{duration_ms:.0f}ms]"
            except:
                pass
        
        print(f"\n{prefix}{created} - {handler} -> {action} ({status}){duration}")
        print(f"{prefix}  Correlation: {corr_id}")
        
        # Show trace context
        if trace_id:
            print(f"{prefix}  Trace: {trace_id} / Span: {span_id}")
            if parent_span_id:
                print(f"{prefix}  Parent Span: {parent_span_id}")
        
        # Show request details
        if req_data:
            try:
                data = json.loads(req_data)
                if 'thought_id' in data:
                    print(f"{prefix}  Thought: {data['thought_id']}")
                if 'task_id' in data:
                    print(f"{prefix}  Task: {data['task_id']}")
                if 'channel_id' in data:
                    print(f"{prefix}  Channel: {data['channel_id']}")
                if 'parameters' in data and data['parameters']:
                    print(f"{prefix}  Params: {str(data['parameters'])[:80]}...")
            except:
                pass
        
        # Show response summary
        if resp_data:
            try:
                resp = json.loads(resp_data)
                if not resp.get('success'):
                    print(f"{prefix}  ERROR: {resp.get('error_message', 'Unknown error')}")
                elif resp.get('result_summary'):
                    print(f"{prefix}  Result: {resp['result_summary'][:80]}...")
            except:
                pass
    
    if trace_id:
        # Display as hierarchy
        root_traces = [t for cid, t in traces.items() if not t['row'][10]]  # No parent_span_id
        for trace_info in root_traces:
            display_correlation(trace_info['row'])
            # Display children recursively
            def show_children(parent_id, level=1):
                for child_id in traces[parent_id]['children']:
                    display_correlation(traces[child_id]['row'], level)
                    show_children(child_id, level + 1)
            show_children(trace_info['row'][0])
    else:
        # Display flat list
        for row in rows:
            display_correlation(row)


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


def list_traces(limit=20):
    """List recent unique trace IDs."""
    conn = get_db_connection()
    cursor = conn.execute("""
        SELECT DISTINCT 
            trace_id,
            MIN(created_at) as first_seen,
            MAX(created_at) as last_seen,
            COUNT(*) as span_count
        FROM service_correlations 
        WHERE trace_id IS NOT NULL
        GROUP BY trace_id
        ORDER BY last_seen DESC
        LIMIT ?
    """, (limit,))
    
    rows = cursor.fetchall()
    print(f"\n{'='*100}")
    print(f"RECENT TRACES ({len(rows)} shown)")
    print(f"{'='*100}")
    print(f"{'Trace ID':<40} {'First Seen':<20} {'Last Seen':<20} {'Spans'}")
    print(f"{'-'*100}")
    
    for trace_id, first, last, count in rows:
        if trace_id:
            print(f"{trace_id:<40} {first[:19]:<20} {last[:19]:<20} {count}")


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
    
    elif command == "trace" and len(sys.argv) > 2:
        show_correlations(trace_id=sys.argv[2])
    
    elif command == "traces":
        list_traces()
    
    elif command == "dead-letter":
        show_dead_letter()
    
    elif command == "api-messages":
        channel = sys.argv[2] if len(sys.argv) > 2 else None
        show_api_messages(channel)
    
    else:
        print(__doc__)


if __name__ == "__main__":
    main()
