"""
Trace consolidation for trace spans and task processing.

Consolidates TRACE_SPAN correlations into TraceSummaryNode.
"""

import logging
import json
from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict

from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.operations import MemoryOpStatus
from ciris_engine.logic.buses.memory_bus import MemoryBus

logger = logging.getLogger(__name__)


class TraceConsolidator:
    """Consolidates trace span data into summaries."""
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None):
        """
        Initialize trace consolidator.
        
        Args:
            memory_bus: Memory bus for storing results
        """
        self._memory_bus = memory_bus
    
    async def consolidate(
        self,
        period_start: datetime,
        period_end: datetime,
        period_label: str,
        trace_spans: List[Dict[str, Any]]
    ) -> Optional[GraphNode]:
        """
        Consolidate trace spans into a summary showing task processing patterns.
        
        Args:
            period_start: Start of consolidation period
            period_end: End of consolidation period
            period_label: Human-readable period label
            trace_spans: List of trace_span correlations
            
        Returns:
            TraceSummaryNode as GraphNode if successful
        """
        if not trace_spans:
            logger.info(f"No trace spans found for period {period_start} - creating empty summary")
        
        logger.info(f"Consolidating {len(trace_spans)} trace spans")
        
        # Initialize tracking structures
        task_summaries = {}  # task_id -> summary data
        unique_tasks = set()
        unique_thoughts = set()
        tasks_by_status: Dict[str, int] = defaultdict(int)
        thoughts_by_type: Dict[str, int] = defaultdict(int)
        component_calls: Dict[str, int] = defaultdict(int)
        component_failures: Dict[str, int] = defaultdict(int)
        component_latencies = defaultdict(list)
        handler_actions: Dict[str, int] = defaultdict(int)
        errors_by_component: Dict[str, int] = defaultdict(int)
        total_errors = 0
        guardrail_violations: Dict[str, int] = defaultdict(int)
        dma_decisions: Dict[str, int] = defaultdict(int)
        
        for span in trace_spans:
            # Extract tags if available
            tags = {}
            if span.get('tags'):
                try:
                    tags = json.loads(span['tags']) if isinstance(span['tags'], str) else span['tags']
                except:
                    pass
            
            # Extract key identifiers
            trace_id = span.get('trace_id')
            span_id = span.get('span_id')
            parent_span_id = span.get('parent_span_id')
            timestamp = span.get('timestamp')
            
            # Extract from tags
            task_id = tags.get('task_id')
            thought_id = tags.get('thought_id')
            component_type = tags.get('component_type', 'unknown')
            
            # Track unique entities
            if task_id:
                unique_tasks.add(task_id)
                
                # Initialize task summary if needed
                if task_id not in task_summaries:
                    task_summaries[task_id] = {
                        'task_id': task_id,
                        'status': 'processing',
                        'thoughts': [],
                        'start_time': timestamp,
                        'end_time': timestamp,
                        'handlers_selected': [],
                        'trace_ids': set()
                    }
                
                task_summaries[task_id]['trace_ids'].add(trace_id)
                task_summaries[task_id]['end_time'] = timestamp
            
            if thought_id:
                unique_thoughts.add(thought_id)
                
                # Track thought type
                thought_type = tags.get('thought_type', 'unknown')
                thoughts_by_type[thought_type] += 1
                
                # Track handler selection
                if component_type == 'handler' and task_id:
                    action_type = tags.get('action_type', 'unknown')
                    handler_actions[action_type] += 1
                    
                    if task_id in task_summaries:
                        task_summaries[task_id]['handlers_selected'].append(action_type)
                        task_summaries[task_id]['thoughts'].append({
                            'thought_id': thought_id,
                            'handler': action_type,
                            'timestamp': timestamp.isoformat() if timestamp else None
                        })
            
            # Track task completion
            if task_id and tags.get('task_status'):
                status = tags['task_status']
                tasks_by_status[status] += 1
                if task_id in task_summaries:
                    task_summaries[task_id]['status'] = status
            
            # Component tracking
            component_calls[component_type] += 1
            
            # Parse response data for metrics
            if span.get('response_data'):
                try:
                    resp_data = json.loads(span['response_data']) if isinstance(span['response_data'], str) else span['response_data']
                    
                    if not resp_data.get('success', True):
                        component_failures[component_type] += 1
                        errors_by_component[component_type] += 1
                        total_errors += 1
                    
                    if 'execution_time_ms' in resp_data:
                        try:
                            latency = float(resp_data['execution_time_ms'])
                            component_latencies[component_type].append(latency)
                        except (TypeError, ValueError):
                            pass
                except:
                    pass
            
            # Track guardrail violations
            if component_type == 'guardrail':
                guardrail_type = tags.get('guardrail_type', 'unknown')
                if tags.get('violation') == 'true':
                    guardrail_violations[guardrail_type] += 1
            
            # Track DMA decisions
            if component_type == 'dma':
                dma_type = tags.get('dma_type', 'unknown')
                dma_decisions[dma_type] += 1
        
        # Calculate latency statistics
        component_latency_stats = {}
        for component, latencies in component_latencies.items():
            if latencies:
                sorted_latencies = sorted(latencies)
                component_latency_stats[component] = {
                    'avg': sum(latencies) / len(latencies),
                    'p50': sorted_latencies[len(sorted_latencies) // 2],
                    'p95': sorted_latencies[int(len(sorted_latencies) * 0.95)],
                    'p99': sorted_latencies[int(len(sorted_latencies) * 0.99)]
                }
        
        # Calculate task processing times
        task_processing_times = []
        for task_id, summary in task_summaries.items():
            if summary['start_time'] and summary['end_time']:
                duration_ms = (summary['end_time'] - summary['start_time']).total_seconds() * 1000
                task_processing_times.append(duration_ms)
                summary['duration_ms'] = duration_ms
            
            # Convert sets to lists for JSON serialization
            summary['trace_ids'] = list(summary['trace_ids'])
        
        # Calculate task time percentiles
        avg_task_time = 0.0
        p50_task_time = 0.0
        p95_task_time = 0.0
        p99_task_time = 0.0
        
        if task_processing_times:
            sorted_times = sorted(task_processing_times)
            avg_task_time = sum(task_processing_times) / len(task_processing_times)
            p50_task_time = sorted_times[len(sorted_times) // 2]
            p95_task_time = sorted_times[int(len(sorted_times) * 0.95)]
            p99_task_time = sorted_times[int(len(sorted_times) * 0.99)]
        
        # Calculate trace depth metrics
        trace_depths = [len(s.get('thoughts', [])) for s in task_summaries.values()]
        max_trace_depth = max(trace_depths) if trace_depths else 0
        avg_trace_depth = sum(trace_depths) / len(trace_depths) if trace_depths else 0.0
        
        # Calculate error rate
        total_calls = sum(component_calls.values())
        error_rate = total_errors / total_calls if total_calls > 0 else 0.0
        
        # Calculate avg thoughts per task
        avg_thoughts_per_task = len(unique_thoughts) / len(unique_tasks) if unique_tasks else 0.0
        
        # Create summary data
        summary_data = {
            'id': f"trace_summary_{period_start.strftime('%Y%m%d_%H')}",
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'period_label': period_label,
            'total_tasks_processed': len(unique_tasks),
            'tasks_by_status': dict(tasks_by_status),
            'unique_task_ids': list(unique_tasks),
            'task_summaries': task_summaries,
            'total_thoughts_processed': len(unique_thoughts),
            'thoughts_by_type': dict(thoughts_by_type),
            'avg_thoughts_per_task': avg_thoughts_per_task,
            'component_calls': dict(component_calls),
            'component_failures': dict(component_failures),
            'component_latency_ms': component_latency_stats,
            'dma_decisions': dict(dma_decisions),
            'guardrail_violations': dict(guardrail_violations),
            'handler_actions': dict(handler_actions),
            'avg_task_processing_time_ms': avg_task_time,
            'p50_task_processing_time_ms': p50_task_time,
            'p95_task_processing_time_ms': p95_task_time,
            'p99_task_processing_time_ms': p99_task_time,
            'total_processing_time_ms': sum(task_processing_times) if task_processing_times else 0.0,
            'total_errors': total_errors,
            'errors_by_component': dict(errors_by_component),
            'error_rate': error_rate,
            'max_trace_depth': max_trace_depth,
            'avg_trace_depth': avg_trace_depth,
            'source_correlation_count': len(trace_spans),
            'created_at': period_end.isoformat(),
            'updated_at': period_end.isoformat()
        }
        
        # Create GraphNode
        summary_node = GraphNode(
            id=str(summary_data['id']),
            type=NodeType.TRACE_SUMMARY,
            scope=GraphScope.LOCAL,
            attributes=summary_data,
            updated_by="tsdb_consolidation",
            updated_at=period_end  # Use period end as timestamp
        )
        
        # Store summary
        if self._memory_bus:
            result = await self._memory_bus.memorize(node=summary_node)
            if result.status != MemoryOpStatus.OK:
                logger.error(f"Failed to store trace summary: {result.error}")
                return None
        else:
            logger.warning("No memory bus available - summary not stored")
        
        return summary_node
    
    def get_edges(
        self,
        summary_node: GraphNode,
        trace_spans: List[Dict[str, Any]]
    ) -> List[Tuple[GraphNode, GraphNode, str, Dict[str, Any]]]:
        """
        Get edges to create for trace summary.
        
        Returns edges from summary to:
        - Tasks with high latency
        - Components with errors
        """
        edges = []
        
        # Find unique tasks
        tasks_with_errors = set()
        high_latency_tasks = set()
        
        for span in trace_spans:
            task_id = span.get('trace_id')
            if task_id:
                # Check for errors in tags
                if span.get('tags', {}).get('error', False):
                    tasks_with_errors.add(task_id)
                
                # Also check for failed tasks in response_data
                resp_data = span.get('response_data', {})
                if isinstance(resp_data, dict):
                    success = resp_data.get('success', 'true')
                    # Handle string boolean values
                    if isinstance(success, str) and success.lower() == 'false':
                        tasks_with_errors.add(task_id)
                    elif success is False:
                        tasks_with_errors.add(task_id)
                
                # Check for high latency (> 5 seconds)
                resp_data = span.get('response_data', {})
                if isinstance(resp_data, dict):
                    latency_str = resp_data.get('execution_time_ms', 0)
                    try:
                        latency = float(latency_str) if isinstance(latency_str, str) else latency_str
                        if latency > 5000:
                            high_latency_tasks.add(task_id)
                    except (ValueError, TypeError):
                        pass
        
        # Create edges to problematic tasks (limit to 10 each)
        for i, task_id in enumerate(list(tasks_with_errors)[:10]):
            edges.append((
                summary_node,
                summary_node,  # Self-reference with task data
                'ERROR_TASK',
                {
                    'task_id': task_id,
                    'error_type': 'trace_error'
                }
            ))
        
        for i, task_id in enumerate(list(high_latency_tasks)[:10]):
            edges.append((
                summary_node,
                summary_node,  # Self-reference with task data
                'HIGH_LATENCY_TASK',
                {
                    'task_id': task_id,
                    'latency_category': 'high'
                }
            ))
        
        return edges