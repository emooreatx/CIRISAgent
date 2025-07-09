"""
Query management for TSDB consolidation.

Handles querying both graph nodes and service correlations for consolidation periods.
"""

import json
import logging
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Set
from collections import defaultdict

from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.services.operations import MemoryQuery
from ciris_engine.logic.buses.memory_bus import MemoryBus
from ciris_engine.logic.persistence.db.core import get_db_connection

logger = logging.getLogger(__name__)


class QueryManager:
    """Manages querying data for consolidation."""
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None):
        """
        Initialize query manager.
        
        Args:
            memory_bus: Memory bus for graph operations
        """
        self._memory_bus = memory_bus
    
    async def query_all_nodes_in_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> Dict[str, List[GraphNode]]:
        """
        Query ALL graph nodes created or updated within a period.
        
        Args:
            period_start: Period start time
            period_end: Period end time
            
        Returns:
            Dictionary mapping node types to lists of nodes
        """
        nodes_by_type = defaultdict(list)
        
        # Note: We don't actually need memory bus for direct DB queries
        # This method queries the database directly
        
        try:
            # Direct database query for efficiency
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Query all nodes updated in this period
                cursor.execute("""
                    SELECT node_id, node_type, scope, attributes_json, 
                           version, updated_by, updated_at, created_at
                    FROM graph_nodes
                    WHERE (datetime(updated_at) >= datetime(?) AND datetime(updated_at) < datetime(?))
                       OR (updated_at IS NULL AND datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?))
                    ORDER BY node_type, updated_at
                """, (
                    period_start.isoformat(),
                    period_end.isoformat(),
                    period_start.isoformat(),
                    period_end.isoformat()
                ))
                
                for row in cursor.fetchall():
                    # Parse node type
                    node_type_str = row['node_type']
                    try:
                        node_type = NodeType(node_type_str)
                    except ValueError:
                        # For unknown types, use AGENT as fallback
                        node_type = NodeType.AGENT
                    
                    # Parse attributes JSON
                    import json
                    attributes = {}
                    if row['attributes_json']:
                        try:
                            attributes = json.loads(row['attributes_json'])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse attributes for node {row['node_id']}")
                    
                    # Create GraphNode
                    node = GraphNode(
                        id=row['node_id'],
                        type=node_type,
                        scope=GraphScope(row['scope']) if row['scope'] else GraphScope.LOCAL,
                        attributes=attributes,
                        version=row['version'],
                        updated_by=row['updated_by'],
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    )
                    
                    nodes_by_type[node_type_str].append(node)
                
                logger.info(f"Found {sum(len(nodes) for nodes in nodes_by_type.values())} nodes across {len(nodes_by_type)} types for period {period_start}")
        
        except Exception as e:
            logger.error(f"Failed to query nodes for period: {e}")
        
        return dict(nodes_by_type)
    
    async def query_tsdb_data_nodes(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[GraphNode]:
        """
        Query TSDB_DATA nodes specifically for a period.
        
        Args:
            period_start: Period start time
            period_end: Period end time
            
        Returns:
            List of TSDB_DATA nodes
        """
        nodes = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Query TSDB_DATA nodes
                cursor.execute("""
                    SELECT node_id, scope, attributes_json, version, 
                           updated_by, updated_at, created_at
                    FROM graph_nodes
                    WHERE node_type = 'tsdb_data'
                      AND ((datetime(updated_at) >= datetime(?) AND datetime(updated_at) < datetime(?))
                           OR (updated_at IS NULL AND datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)))
                    ORDER BY updated_at
                """, (
                    period_start.isoformat(),
                    period_end.isoformat(),
                    period_start.isoformat(),
                    period_end.isoformat()
                ))
                
                for row in cursor.fetchall():
                    # Parse attributes JSON
                    import json
                    attributes = {}
                    if row['attributes_json']:
                        try:
                            attributes = json.loads(row['attributes_json'])
                        except json.JSONDecodeError:
                            logger.warning(f"Failed to parse attributes for node {row['node_id']}")
                    
                    node = GraphNode(
                        id=row['node_id'],
                        type=NodeType.TSDB_DATA,
                        scope=GraphScope(row['scope']) if row['scope'] else GraphScope.LOCAL,
                        attributes=attributes,
                        version=row['version'],
                        updated_by=row['updated_by'],
                        updated_at=datetime.fromisoformat(row['updated_at']) if row['updated_at'] else None
                    )
                    nodes.append(node)
                
                logger.info(f"Found {len(nodes)} TSDB_DATA nodes for period {period_start}")
        
        except Exception as e:
            logger.error(f"Failed to query TSDB data nodes: {e}")
        
        return nodes
    
    async def query_service_correlations(
        self,
        period_start: datetime,
        period_end: datetime,
        correlation_types: Optional[List[str]] = None
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        Query service correlations for a period.
        
        Args:
            period_start: Period start time
            period_end: Period end time
            correlation_types: Optional list of correlation types to filter
            
        Returns:
            Dictionary mapping correlation types to correlation data
        """
        correlations_by_type = defaultdict(list)
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Build query
                query = """
                    SELECT correlation_id, correlation_type, service_type, action_type,
                           trace_id, span_id, parent_span_id,
                           timestamp, request_data, response_data, tags
                    FROM service_correlations
                    WHERE datetime(timestamp) >= datetime(?) AND datetime(timestamp) < datetime(?)
                """
                
                params = [period_start.isoformat(), period_end.isoformat()]
                
                if correlation_types:
                    placeholders = ','.join('?' * len(correlation_types))
                    query += f" AND correlation_type IN ({placeholders})"
                    params.extend(correlation_types)
                
                query += " ORDER BY timestamp"
                
                cursor.execute(query, params)
                
                for row in cursor.fetchall():
                    # Parse timestamp
                    ts_str = row['timestamp']
                    if ts_str:
                        ts = datetime.fromisoformat(ts_str.replace('Z', '+00:00'))
                    else:
                        ts = None
                    
                    # Parse JSON fields
                    request_data = row['request_data']
                    if request_data and isinstance(request_data, str):
                        try:
                            request_data = json.loads(request_data)
                        except Exception:
                            request_data = {}
                    elif request_data is None:
                        request_data = {}
                    
                    response_data = row['response_data']
                    if isinstance(response_data, str) and response_data.strip():
                        try:
                            response_data = json.loads(response_data)
                        except Exception as e:
                            logger.debug(f"Failed to parse response_data: {e}")
                            response_data = {}
                    else:
                        response_data = {}
                    
                    tags = row['tags']
                    if isinstance(tags, str) and tags.strip():
                        try:
                            tags = json.loads(tags)
                        except Exception as e:
                            logger.debug(f"Failed to parse tags: {e}")
                            tags = {}
                    else:
                        tags = {}
                    
                    correlation = {
                        'correlation_id': row['correlation_id'],
                        'correlation_type': row['correlation_type'],
                        'service_type': row['service_type'],
                        'action_type': row['action_type'],
                        'trace_id': row['trace_id'],
                        'span_id': row['span_id'],
                        'parent_span_id': row['parent_span_id'],
                        'timestamp': ts,
                        'request_data': request_data,
                        'response_data': response_data,
                        'tags': tags
                    }
                    
                    correlations_by_type[row['correlation_type']].append(correlation)
                
                total = sum(len(corrs) for corrs in correlations_by_type.values())
                logger.info(f"Found {total} correlations across {len(correlations_by_type)} types for period {period_start}")
        
        except Exception as e:
            logger.error(f"Failed to query service correlations: {e}")
            import traceback
            traceback.print_exc()
        
        return dict(correlations_by_type)
    
    async def query_tasks_in_period(
        self,
        period_start: datetime,
        period_end: datetime
    ) -> List[Dict[str, Any]]:
        """
        Query tasks completed or updated in a period.
        
        Args:
            period_start: Period start time
            period_end: Period end time
            
        Returns:
            List of task data with outcomes
        """
        tasks = []
        
        try:
            with get_db_connection() as conn:
                cursor = conn.cursor()
                
                # Query tasks
                cursor.execute("""
                    SELECT task_id, channel_id, description, status, priority,
                           created_at, updated_at, parent_task_id, 
                           context_json, outcome_json, retry_count
                    FROM tasks
                    WHERE datetime(updated_at) >= datetime(?) AND datetime(updated_at) < datetime(?)
                    ORDER BY updated_at
                """, (period_start.isoformat(), period_end.isoformat()))
                
                for row in cursor.fetchall():
                    task = {
                        'task_id': row['task_id'],
                        'channel_id': row['channel_id'],
                        'description': row['description'],
                        'status': row['status'],
                        'priority': row['priority'],
                        'created_at': row['created_at'],
                        'updated_at': row['updated_at'],
                        'parent_task_id': row['parent_task_id'],
                        'context': row['context_json'],
                        'outcome': row['outcome_json'],
                        'retry_count': row['retry_count']
                    }
                    tasks.append(task)
                
                # Also get thoughts for these tasks
                if tasks:
                    task_ids = [t['task_id'] for t in tasks]
                    placeholders = ','.join('?' * len(task_ids))
                    
                    cursor.execute(f"""
                        SELECT source_task_id, thought_id, thought_type, status,
                               created_at, final_action_json
                        FROM thoughts
                        WHERE source_task_id IN ({placeholders})
                        ORDER BY created_at
                    """, task_ids)
                    
                    # Group thoughts by task
                    thoughts_by_task = defaultdict(list)
                    for row in cursor.fetchall():
                        thoughts_by_task[row['source_task_id']].append({
                            'thought_id': row['thought_id'],
                            'thought_type': row['thought_type'],
                            'status': row['status'],
                            'created_at': row['created_at'],
                            'final_action': row['final_action_json']
                        })
                    
                    # Add thoughts to tasks
                    for task in tasks:
                        task['thoughts'] = thoughts_by_task.get(task['task_id'], [])
                
                logger.info(f"Found {len(tasks)} tasks for period {period_start}")
        
        except Exception as e:
            logger.error(f"Failed to query tasks: {e}")
        
        return tasks
    
    async def get_special_node_types(self) -> Set[str]:
        """
        Get the list of special node types to track in summaries.
        
        Returns:
            Set of node type strings
        """
        return {
            'concept',
            'shutdown_memory',
            'identity_update',
            'config_update',
            'wise_feedback',
            'self_observation',
            'task_assignment',
            'user',
            'agent',
            'observation'
        }
    
    async def check_period_consolidated(
        self,
        period_start: datetime
    ) -> bool:
        """
        Check if a period has already been consolidated.
        
        Args:
            period_start: Start of the period
            
        Returns:
            True if already consolidated
        """
        if not self._memory_bus:
            return False
        
        try:
            # Query for any summary node for this period
            period_id = period_start.strftime('%Y%m%d_%H')
            
            # Check for TSDB summary as indicator
            query = MemoryQuery(
                node_id=f"tsdb_summary_{period_id}",
                type=NodeType.TSDB_SUMMARY,
                scope=GraphScope.LOCAL,
                include_edges=False,
                depth=1
            )
            
            summaries = await self._memory_bus.recall(query, handler_name="tsdb_consolidation")
            return len(summaries) > 0
            
        except Exception as e:
            logger.error(f"Failed to check consolidation status: {e}")
            return False