"""
Conversation consolidation for service interactions.

Consolidates SERVICE_INTERACTION correlations into ConversationSummaryNode.
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


class ConversationConsolidator:
    """Consolidates conversation and interaction data."""
    
    def __init__(self, memory_bus: Optional[MemoryBus] = None):
        """
        Initialize conversation consolidator.
        
        Args:
            memory_bus: Memory bus for storing results
        """
        self._memory_bus = memory_bus
    
    async def consolidate(
        self,
        period_start: datetime,
        period_end: datetime,
        period_label: str,
        service_interactions: List[Dict[str, Any]]
    ) -> Optional[GraphNode]:
        """
        Consolidate service interactions into a conversation summary.
        
        Args:
            period_start: Start of consolidation period
            period_end: End of consolidation period
            period_label: Human-readable period label
            service_interactions: List of service_interaction correlations
            
        Returns:
            ConversationSummaryNode as GraphNode if successful
        """
        if not service_interactions:
            logger.info(f"No service interactions found for period {period_start} - creating empty summary")
        
        logger.info(f"Consolidating {len(service_interactions)} service interactions")
        
        # Group by channel and build conversation history
        conversations_by_channel = defaultdict(list)
        unique_users = set()
        action_counts: Dict[str, int] = defaultdict(int)
        service_calls: Dict[str, int] = defaultdict(int)
        total_response_time = 0.0
        response_count = 0
        error_count = 0
        
        for interaction in service_interactions:
            # Extract key data
            correlation_id = interaction.get('correlation_id', 'unknown')
            action_type = interaction.get('action_type', 'unknown')
            service_type = interaction.get('service_type', 'unknown')
            timestamp = interaction.get('timestamp')
            
            # Parse request data
            channel_id = 'unknown'
            content = ''
            author_id = None
            author_name = None
            
            if interaction.get('request_data'):
                try:
                    req_data = json.loads(interaction['request_data']) if isinstance(interaction['request_data'], str) else interaction['request_data']
                    channel_id = req_data.get('channel_id', 'unknown')
                    
                    # Extract message content based on action type
                    if action_type in ['speak', 'observe']:
                        params = req_data.get('parameters', {})
                        content = params.get('content', '')
                        author_id = params.get('author_id')
                        author_name = params.get('author_name')
                        
                        if author_id:
                            unique_users.add(author_id)
                except Exception as e:
                    logger.warning(f"Failed to parse request data: {e}")
            
            # Parse response data
            execution_time = 0
            success = True
            
            if interaction.get('response_data'):
                try:
                    resp_data = json.loads(interaction['response_data']) if isinstance(interaction['response_data'], str) else interaction['response_data']
                    execution_time = resp_data.get('execution_time_ms', 0)
                    success = resp_data.get('success', True)
                    
                    if execution_time > 0:
                        total_response_time += execution_time
                        response_count += 1
                    
                    if not success:
                        error_count += 1
                except:
                    pass
            
            # Build conversation entry
            conv_entry = {
                'timestamp': timestamp.isoformat() if timestamp else None,
                'correlation_id': correlation_id,
                'action_type': action_type,
                'content': content,
                'author_id': author_id,
                'author_name': author_name,
                'execution_time_ms': execution_time,
                'success': success
            }
            
            conversations_by_channel[channel_id].append(conv_entry)
            action_counts[action_type] += 1
            service_calls[service_type] += 1
        
        # Calculate metrics
        total_messages = sum(len(msgs) for msgs in conversations_by_channel.values())
        messages_by_channel = {ch: len(msgs) for ch, msgs in conversations_by_channel.items()}
        avg_response_time = total_response_time / response_count if response_count > 0 else 0.0
        success_rate = 1.0 - (error_count / len(service_interactions)) if len(service_interactions) > 0 else 1.0
        
        # Sort conversations by timestamp
        for channel_id in conversations_by_channel:
            conversations_by_channel[channel_id].sort(
                key=lambda x: x['timestamp'] if x['timestamp'] else ''
            )
        
        # Create summary data
        summary_data = {
            'id': f"conversation_summary_{period_start.strftime('%Y%m%d_%H')}",
            'period_start': period_start.isoformat(),
            'period_end': period_end.isoformat(),
            'period_label': period_label,
            'conversations_by_channel': dict(conversations_by_channel),
            'total_messages': total_messages,
            'messages_by_channel': messages_by_channel,
            'unique_users': len(unique_users),
            'user_list': list(unique_users),
            'action_counts': dict(action_counts),
            'service_calls': dict(service_calls),
            'avg_response_time_ms': avg_response_time,
            'total_processing_time_ms': total_response_time,
            'error_count': error_count,
            'success_rate': success_rate,
            'source_correlation_count': len(service_interactions),
            'created_at': period_end.isoformat(),
            'updated_at': period_end.isoformat()
        }
        
        # Create GraphNode
        summary_node = GraphNode(
            id=str(summary_data['id']),
            type=NodeType.CONVERSATION_SUMMARY,
            scope=GraphScope.LOCAL,
            attributes=summary_data,
            updated_by="tsdb_consolidation",
            updated_at=period_end  # Use period end as timestamp
        )
        
        # Store summary
        if self._memory_bus:
            result = await self._memory_bus.memorize(node=summary_node)
            if result.status != MemoryOpStatus.OK:
                logger.error(f"Failed to store conversation summary: {result.error}")
                return None
        else:
            logger.warning("No memory bus available - summary not stored")
        
        return summary_node
    
    def get_edges(
        self,
        summary_node: GraphNode,
        service_interactions: List[Dict[str, Any]]
    ) -> List[Tuple[GraphNode, GraphNode, str, Dict[str, Any]]]:
        """
        Get edges to create for conversation summary.
        
        Returns edges from summary to:
        - User participants (INVOLVED_USER)
        - Channels where conversations happened (OCCURRED_IN_CHANNEL)
        """
        edges = []
        
        # Get participant data
        participant_data = self.get_participant_data(service_interactions)
        
        # Create edges to participants
        for user_id, data in participant_data.items():
            if user_id and data['message_count'] > 0:
                # Create user node if needed (edge creation will handle this)
                user_node = GraphNode(
                    id=f"user_{user_id}",
                    type=NodeType.USER,
                    scope=GraphScope.LOCAL,
                    attributes={
                        "user_id": user_id,
                        "username": data.get('author_name', user_id)
                    },
                    updated_by="tsdb_consolidation",
                    updated_at=datetime.utcnow()
                )
                
                edges.append((
                    summary_node,
                    user_node,
                    'INVOLVED_USER',
                    {
                        'message_count': data['message_count'],
                        'channels': list(data['channels'])
                    }
                ))
        
        # Create edges to channels
        channels = set()
        for interaction in service_interactions:
            channel_id = interaction.get('context', {}).get('channel_id')
            if channel_id:
                channels.add(channel_id)
        
        for channel_id in channels:
            channel_node = GraphNode(
                id=f"channel_{channel_id}",
                type=NodeType.CHANNEL,
                scope=GraphScope.LOCAL,
                attributes={
                    "channel_id": channel_id
                },
                updated_by="tsdb_consolidation",
                updated_at=datetime.utcnow()
            )
            
            edges.append((
                summary_node,
                channel_node,
                'OCCURRED_IN_CHANNEL',
                {
                    'message_count': len([i for i in service_interactions 
                                        if i.get('context', {}).get('channel_id') == channel_id])
                }
            ))
        
        return edges
    
    def get_participant_data(self, service_interactions: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        """
        Extract participant data for edge creation.
        
        Returns a dict mapping user_id to participation metrics.
        """
        participants: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
            'message_count': 0,
            'channels': set(),
            'author_name': None
        })
        
        for interaction in service_interactions:
            if interaction.get('request_data'):
                try:
                    req_data = json.loads(interaction['request_data']) if isinstance(interaction['request_data'], str) else interaction['request_data']
                    
                    if interaction.get('action_type') in ['speak', 'observe']:
                        params = req_data.get('parameters', {})
                        author_id = params.get('author_id')
                        
                        if author_id:
                            participants[author_id]['message_count'] += 1
                            participants[author_id]['channels'].add(req_data.get('channel_id', 'unknown'))
                            if params.get('author_name'):
                                participants[author_id]['author_name'] = params['author_name']
                except:
                    pass
        
        # Convert sets to lists for serialization
        for user_id in participants:
            participants[user_id]['channels'] = list(participants[user_id]['channels'])
        
        return dict(participants)