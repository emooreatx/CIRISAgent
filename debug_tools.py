#!/usr/bin/env python3
"""Debug tools for investigating CIRIS processing issues."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from datetime import datetime, timedelta
from ciris_engine.logic.persistence import models as persistence_models
from ciris_engine.logic.persistence.models.thoughts import get_thoughts_by_status
from ciris_engine.logic.persistence.models.tasks import get_tasks
from ciris_engine.logic.persistence.models.correlations import get_correlations, get_correlations_by_trace_id
from ciris_engine.logic.services.infrastructure.time import TimeService

def show_correlations(limit=20, trace_id=None):
    """Show recent service correlations with trace hierarchy."""
    time_service = TimeService()
    
    if trace_id:
        correlations = get_correlations_by_trace_id(trace_id, time_service)
        print(f"\n=== Correlations for trace {trace_id} ===")
    else:
        correlations = get_correlations(limit=limit)
        print(f"\n=== Recent {limit} Correlations ===")
    
    # Group by trace_id to show hierarchy
    traces = {}
    for corr in correlations:
        tid = corr.trace_context.get('trace_id') if corr.trace_context else 'no_trace'
        if tid not in traces:
            traces[tid] = []
        traces[tid].append(corr)
    
    for trace_id, trace_corrs in traces.items():
        print(f"\nTrace: {trace_id}")
        # Sort by timestamp
        trace_corrs.sort(key=lambda x: x.timestamp or x.created_at)
        
        for corr in trace_corrs:
            parent = corr.trace_context.get('parent_span_id', '') if corr.trace_context else ''
            indent = "  " if parent else ""
            print(f"{indent}{corr.timestamp} - {corr.action_type} - {corr.handler_name} - {corr.status}")
            if corr.request_data and hasattr(corr.request_data, 'parameters'):
                params = corr.request_data.parameters
                if 'content' in params:
                    print(f"{indent}  Content: {params['content'][:100]}...")
                if 'thought_id' in params:
                    print(f"{indent}  Thought ID: {params['thought_id']}")

def list_traces(limit=20):
    """List recent unique trace IDs with span counts."""
    correlations = get_correlations(limit=limit*10)
    traces = {}
    
    for corr in correlations:
        if corr.trace_context and 'trace_id' in corr.trace_context:
            trace_id = corr.trace_context['trace_id']
            if trace_id not in traces:
                traces[trace_id] = {
                    'count': 0,
                    'first_seen': corr.timestamp or corr.created_at,
                    'last_seen': corr.timestamp or corr.created_at,
                    'actions': set()
                }
            traces[trace_id]['count'] += 1
            traces[trace_id]['actions'].add(corr.action_type)
            if (corr.timestamp or corr.created_at) < traces[trace_id]['first_seen']:
                traces[trace_id]['first_seen'] = corr.timestamp or corr.created_at
            if (corr.timestamp or corr.created_at) > traces[trace_id]['last_seen']:
                traces[trace_id]['last_seen'] = corr.timestamp or corr.created_at
    
    print(f"\n=== Recent {limit} Traces ===")
    sorted_traces = sorted(traces.items(), key=lambda x: x[1]['last_seen'], reverse=True)[:limit]
    
    for trace_id, info in sorted_traces:
        duration = (info['last_seen'] - info['first_seen']).total_seconds()
        print(f"\n{trace_id[:16]}...")
        print(f"  Spans: {info['count']}")
        print(f"  Duration: {duration:.2f}s")
        print(f"  Actions: {', '.join(sorted(info['actions']))}")
        print(f"  First: {info['first_seen']}")
        print(f"  Last: {info['last_seen']}")

def show_thoughts(status='PENDING', limit=20):
    """Show thoughts by status."""
    thoughts = get_thoughts_by_status(status, limit=limit)
    print(f"\n=== {status} Thoughts (limit {limit}) ===")
    
    for thought in thoughts:
        print(f"\nThought: {thought.thought_id}")
        print(f"  Created: {thought.created_at}")
        print(f"  Updated: {thought.updated_at}")
        print(f"  Status: {thought.status}")
        print(f"  Depth: {thought.depth}")
        print(f"  Task ID: {thought.task_id}")
        if thought.content:
            print(f"  Content: {thought.content[:100]}...")
        if thought.final_action:
            print(f"  Final Action: {thought.final_action}")
        if thought.parent_thought_id:
            print(f"  Parent: {thought.parent_thought_id}")

def show_tasks(limit=10):
    """Show recent tasks with their thoughts."""
    tasks = get_tasks(limit=limit)
    print(f"\n=== Recent {limit} Tasks ===")
    
    for task in tasks:
        print(f"\nTask: {task.task_id}")
        print(f"  Created: {task.created_at}")
        print(f"  Status: {task.status}")
        print(f"  Description: {task.description}")
        print(f"  Channel: {task.channel_id}")
        
        # Count thoughts for this task
        thoughts = get_thoughts_by_status('COMPLETED', limit=100)
        task_thoughts = [t for t in thoughts if t.task_id == task.task_id]
        print(f"  Thoughts: {len(task_thoughts)}")

def show_handler_metrics():
    """Show handler execution metrics from correlations."""
    correlations = get_correlations(limit=1000)
    
    handler_stats = {}
    for corr in correlations:
        if corr.handler_name and corr.action_type:
            key = f"{corr.handler_name}:{corr.action_type}"
            if key not in handler_stats:
                handler_stats[key] = {
                    'count': 0,
                    'success': 0,
                    'failed': 0,
                    'total_time': 0.0
                }
            
            handler_stats[key]['count'] += 1
            if corr.status == 'COMPLETED':
                handler_stats[key]['success'] += 1
            else:
                handler_stats[key]['failed'] += 1
            
            if corr.response_data and hasattr(corr.response_data, 'execution_time_ms'):
                handler_stats[key]['total_time'] += corr.response_data.execution_time_ms or 0.0
    
    print("\n=== Handler Execution Metrics ===")
    for handler, stats in sorted(handler_stats.items()):
        avg_time = stats['total_time'] / stats['count'] if stats['count'] > 0 else 0
        print(f"\n{handler}")
        print(f"  Count: {stats['count']}")
        print(f"  Success: {stats['success']}")
        print(f"  Failed: {stats['failed']}")
        print(f"  Avg Time: {avg_time:.2f}ms")

if __name__ == "__main__":
    print("CIRIS Debug Tools")
    print("=" * 50)
    print("\nAvailable functions:")
    print("  show_correlations(limit=20, trace_id=None)")
    print("  list_traces(limit=20)")
    print("  show_thoughts(status='PENDING')")
    print("  show_tasks(limit=10)")
    print("  show_handler_metrics()")
    print("\nStarting interactive Python shell...")
    
    # Start interactive shell
    import code
    code.interact(local=locals())