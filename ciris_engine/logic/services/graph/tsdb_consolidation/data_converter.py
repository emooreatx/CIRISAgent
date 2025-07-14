"""
Data converter for TSDB consolidation.

Converts raw Dict[str, Any] data to typed Pydantic schemas.
"""
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Union

from ciris_engine.schemas.services.graph.consolidation import (
    ServiceInteractionData,
    RequestData,
    ResponseData,
    InteractionContext,
    MetricCorrelationData,
    TraceSpanData,
    SpanTags,
    TaskCorrelationData,
    ThoughtSummary,
    TaskMetadata
)

logger = logging.getLogger(__name__)


class TSDBDataConverter:
    """Converts raw dictionary data to typed schemas."""
    
    @staticmethod
    def convert_service_interaction(raw_data: Dict[str, Any]) -> Optional[ServiceInteractionData]:
        """Convert raw correlation data to ServiceInteractionData."""
        try:
            # Extract raw request/response data
            raw_request = raw_data.get('request_data', {})
            raw_response = raw_data.get('response_data', {})
            parameters = raw_request.get('parameters', {})
            
            # Build typed request data
            request_data = None
            if raw_request:
                request_data = RequestData(
                    channel_id=raw_request.get('channel_id'),
                    author_id=parameters.get('author_id') or raw_request.get('author_id'),
                    author_name=parameters.get('author_name') or raw_request.get('author_name'),
                    content=parameters.get('content') or raw_request.get('content'),
                    parameters=parameters,
                    headers=raw_request.get('headers', {}),
                    metadata=raw_request.get('metadata', {})
                )
            
            # Build typed response data
            response_data = None
            if raw_response:
                response_data = ResponseData(
                    execution_time_ms=raw_response.get('execution_time_ms'),
                    success=raw_response.get('success'),
                    error=raw_response.get('error'),
                    error_type=raw_response.get('error_type'),
                    result=raw_response.get('result'),
                    resource_usage=raw_response.get('resource_usage', {}),
                    metadata=raw_response.get('metadata', {})
                )
            
            # Build interaction context if available
            context = None
            context_data = raw_data.get('context', {})
            if context_data:
                context = InteractionContext(
                    trace_id=context_data.get('trace_id'),
                    span_id=context_data.get('span_id'),
                    parent_span_id=context_data.get('parent_span_id'),
                    user_id=context_data.get('user_id'),
                    session_id=context_data.get('session_id'),
                    environment=context_data.get('environment'),
                    additional_data=context_data.get('additional_data', {})
                )
            
            # Create ServiceInteractionData
            return ServiceInteractionData(
                correlation_id=raw_data['correlation_id'],
                action_type=raw_data.get('action_type', 'unknown'),
                service_type=raw_data.get('service_type', 'unknown'),
                timestamp=raw_data['timestamp'],
                channel_id=raw_request.get('channel_id', 'unknown'),
                request_data=request_data,
                author_id=request_data.author_id if request_data else None,
                author_name=request_data.author_name if request_data else None,
                content=request_data.content if request_data else None,
                response_data=response_data,
                execution_time_ms=response_data.execution_time_ms if response_data else 0.0,
                success=response_data.success if response_data else True,
                error_message=response_data.error if response_data else None,
                context=context
            )
        except Exception as e:
            logger.warning(f"Failed to convert service interaction data: {e}")
            return None
    
    @staticmethod
    def convert_metric_correlation(raw_data: Dict[str, Any]) -> Optional[MetricCorrelationData]:
        """Convert raw correlation data to MetricCorrelationData."""
        try:
            raw_request = raw_data.get('request_data', {})
            raw_response = raw_data.get('response_data', {})
            
            # Build typed request/response data
            request_data = None
            if raw_request:
                request_data = RequestData(
                    channel_id=raw_request.get('channel_id'),
                    parameters=raw_request.get('parameters', {}),
                    headers=raw_request.get('headers', {}),
                    metadata=raw_request.get('metadata', {})
                )
            
            response_data = None
            if raw_response:
                response_data = ResponseData(
                    execution_time_ms=raw_response.get('execution_time_ms'),
                    success=raw_response.get('success'),
                    error=raw_response.get('error'),
                    error_type=raw_response.get('error_type'),
                    resource_usage=raw_response.get('resource_usage', {}),
                    metadata=raw_response.get('metadata', {})
                )
            
            return MetricCorrelationData(
                correlation_id=raw_data['correlation_id'],
                metric_name=raw_request.get('metric_name', 'unknown'),
                value=float(raw_request.get('value', 0)),
                timestamp=raw_data['timestamp'],
                request_data=request_data,
                response_data=response_data,
                tags=raw_data.get('tags', {}),
                source='correlation',
                unit=raw_request.get('unit'),
                aggregation_type=raw_request.get('aggregation_type')
            )
        except Exception as e:
            logger.warning(f"Failed to convert metric correlation data: {e}")
            return None
    
    @staticmethod
    def convert_trace_span(raw_data: Dict[str, Any]) -> Optional[TraceSpanData]:
        """Convert raw correlation data to TraceSpanData."""
        try:
            raw_tags = raw_data.get('tags', {})
            raw_request = raw_data.get('request_data', {})
            raw_response = raw_data.get('response_data', {})
            
            # Build typed span tags
            tags = None
            if raw_tags:
                tags = SpanTags(
                    task_id=raw_tags.get('task_id') or raw_request.get('task_id'),
                    thought_id=raw_tags.get('thought_id') or raw_request.get('thought_id'),
                    component_type=raw_tags.get('component_type') or raw_data.get('service_type'),
                    handler_name=raw_tags.get('handler_name'),
                    user_id=raw_tags.get('user_id'),
                    channel_id=raw_tags.get('channel_id'),
                    environment=raw_tags.get('environment'),
                    version=raw_tags.get('version'),
                    additional_tags={k: v for k, v in raw_tags.items() 
                                   if k not in ['task_id', 'thought_id', 'component_type', 
                                              'handler_name', 'user_id', 'channel_id', 
                                              'environment', 'version']}
                )
            
            return TraceSpanData(
                trace_id=raw_data.get('trace_id', ''),
                span_id=raw_data.get('span_id', ''),
                parent_span_id=raw_data.get('parent_span_id'),
                timestamp=raw_data['timestamp'],
                duration_ms=raw_response.get('duration_ms', 0.0),
                operation_name=raw_data.get('action_type', 'unknown'),
                service_name=raw_data.get('service_type', 'unknown'),
                status='ok' if raw_response.get('success', True) else 'error',
                tags=tags,
                task_id=tags.task_id if tags else None,
                thought_id=tags.thought_id if tags else None,
                component_type=tags.component_type if tags else None,
                error=not raw_response.get('success', True),
                error_message=raw_response.get('error'),
                error_type=raw_response.get('error_type'),
                latency_ms=raw_response.get('execution_time_ms'),
                resource_usage=raw_response.get('resource_usage', {})
            )
        except Exception as e:
            logger.warning(f"Failed to convert trace span data: {e}")
            return None
    
    @staticmethod
    def convert_task(raw_task: Dict[str, Any]) -> Optional[TaskCorrelationData]:
        """Convert raw task data to TaskCorrelationData."""
        try:
            # Extract handlers from thoughts
            handlers_used = []
            final_handler = None
            thoughts = []
            
            for raw_thought in raw_task.get('thoughts', []):
                # Convert thought to ThoughtSummary
                thought_summary = TSDBDataConverter._convert_thought(raw_thought)
                if thought_summary:
                    thoughts.append(thought_summary)
                    if thought_summary.handler:
                        handlers_used.append(thought_summary.handler)
                        final_handler = thought_summary.handler  # Last one is final
            
            # Parse dates
            created_at = TSDBDataConverter._parse_datetime(raw_task.get('created_at'))
            updated_at = TSDBDataConverter._parse_datetime(raw_task.get('updated_at'))
            
            # Build task metadata
            metadata = None
            if raw_task.get('metadata'):
                raw_meta = raw_task['metadata']
                metadata = TaskMetadata(
                    priority=raw_meta.get('priority'),
                    tags=raw_meta.get('tags', []),
                    source=raw_meta.get('source'),
                    parent_task_id=raw_meta.get('parent_task_id'),
                    correlation_id=raw_meta.get('correlation_id'),
                    custom_fields={k: v for k, v in raw_meta.items() 
                                 if k not in ['priority', 'tags', 'source', 
                                            'parent_task_id', 'correlation_id']}
                )
            
            return TaskCorrelationData(
                task_id=raw_task['task_id'],
                status=raw_task['status'],
                created_at=created_at,
                updated_at=updated_at,
                channel_id=raw_task.get('channel_id'),
                user_id=raw_task.get('user_id'),
                task_type=raw_task.get('description', '').split()[0] if raw_task.get('description') else None,
                retry_count=raw_task.get('retry_count', 0),
                duration_ms=(updated_at - created_at).total_seconds() * 1000,
                thoughts=thoughts,
                handlers_used=handlers_used,
                final_handler=final_handler,
                success=raw_task['status'] in ['completed', 'success'],
                error_message=raw_task.get('error_message'),
                result_summary=raw_task.get('description'),
                metadata=metadata
            )
        except Exception as e:
            logger.warning(f"Failed to convert task data: {e}")
            return None
    
    @staticmethod
    def _convert_thought(raw_thought: Dict[str, Any]) -> Optional[ThoughtSummary]:
        """Convert raw thought data to ThoughtSummary."""
        try:
            final_action = None
            handler = None
            
            if raw_thought.get('final_action'):
                try:
                    action_data = json.loads(raw_thought['final_action']) if isinstance(raw_thought['final_action'], str) else raw_thought['final_action']
                    final_action = action_data
                    handler = action_data.get('handler')
                except (json.JSONDecodeError, TypeError):
                    pass
            
            return ThoughtSummary(
                thought_id=raw_thought.get('thought_id', 'unknown'),
                thought_type=raw_thought.get('thought_type', 'standard'),
                status=raw_thought.get('status', 'unknown'),
                created_at=raw_thought.get('created_at', ''),
                content=raw_thought.get('content'),
                final_action=final_action,
                handler=handler,
                round_number=raw_thought.get('round_number', 0),
                depth=raw_thought.get('depth', 0)
            )
        except Exception as e:
            logger.warning(f"Failed to convert thought data: {e}")
            return None
    
    @staticmethod
    def _parse_datetime(date_str: Optional[str]) -> datetime:
        """Parse datetime string to datetime object."""
        if not date_str:
            return datetime.now(timezone.utc)
        
        try:
            # Handle ISO format with Z suffix
            if date_str.endswith('Z'):
                date_str = date_str[:-1] + '+00:00'
            return datetime.fromisoformat(date_str)
        except (ValueError, AttributeError):
            return datetime.now(timezone.utc)


__all__ = ["TSDBDataConverter"]