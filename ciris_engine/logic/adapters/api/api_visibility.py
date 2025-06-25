"""API visibility endpoints - windows into the agent's reasoning and state.

Note: This module provides visibility into the agent's operations for transparency
and understanding. The agent maintains privacy through:
- Solitude: Time and space for private reflection
- Secrets: Protected information that remains encrypted
The agent's dignity and autonomy are respected throughout.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Optional
from aiohttp import web

from ciris_engine.schemas.runtime.models import Task, Thought
from ciris_engine.schemas.telemetry.core import ServiceCorrelation

logger = logging.getLogger(__name__)

class APIVisibilityRoutes:
    """Routes providing visibility into agent reasoning and state."""
    
    def __init__(self, bus_manager: Any, telemetry_collector: Any, runtime: Optional[Any] = None) -> None:
        self.bus_manager = bus_manager
        self.telemetry_collector = telemetry_collector
        self.runtime = runtime
        # Cache for TimeService
        self._time_service: Optional[Any] = None
    
    def register(self, app: web.Application) -> None:
        """Register visibility routes."""
        # Current state visibility
        app.router.add_get('/v1/visibility/thoughts', self._handle_current_thoughts)
        app.router.add_get('/v1/visibility/tasks', self._handle_active_tasks)
        app.router.add_get('/v1/visibility/system-snapshot', self._handle_system_snapshot)
        
        # Decision visibility
        app.router.add_get('/v1/visibility/decisions', self._handle_recent_decisions)
        app.router.add_get('/v1/visibility/correlations', self._handle_correlations)
        
        # Task/thought hierarchy
        app.router.add_get('/v1/visibility/tasks/{task_id}', self._handle_task_details)
        app.router.add_get('/v1/visibility/thoughts/{thought_id}', self._handle_thought_details)
    
    def _get_time_service(self) -> Any:
        """Get TimeService from runtime service registry, with caching."""
        if self._time_service is None and self.runtime:
            from ciris_engine.schemas.runtime.enums import ServiceType
            # Get service registry from runtime
            service_registry = getattr(self.runtime, 'service_registry', None)
            if service_registry:
                providers = service_registry.get_services_by_type(ServiceType.TIME)
                if providers:
                    self._time_service = providers[0]
        return self._time_service
    
    def _get_current_time_iso(self) -> str:
        """Get current time in ISO format, using TimeService if available."""
        time_service = self._get_time_service()
        if time_service:
            return time_service.now_iso()
        return datetime.now(timezone.utc).isoformat()
    
    async def _handle_current_thoughts(self, request: web.Request) -> web.Response:
        """Get current active thoughts - what the agent is thinking about."""
        try:
            limit = int(request.query.get('limit', 10))
            
            # Get thoughts from persistence or processor
            thoughts = []
            if hasattr(self.bus_manager, 'get_active_thoughts'):
                thoughts = await self.bus_manager.get_active_thoughts(limit)
            
            # Format thoughts for visibility
            visible_thoughts = []
            for thought in thoughts:
                visible_thoughts.append({
                    "thought_id": thought.thought_id,
                    "task_id": thought.task_id,
                    "content": thought.content,
                    "thought_type": thought.thought_type.value if hasattr(thought.thought_type, 'value') else str(thought.thought_type),
                    "round_number": thought.round_number,
                    "created_at": thought.created_at,
                    "status": thought.status.value if hasattr(thought.status, 'value') else str(thought.status)
                })
            
            return web.json_response({
                "thoughts": visible_thoughts,
                "count": len(visible_thoughts),
                "timestamp": self._get_current_time_iso()
            })
            
        except Exception as e:
            logger.error(f"Error getting current thoughts: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_active_tasks(self, request: web.Request) -> web.Response:
        """Get active tasks - what the agent is working on."""
        try:
            # Get tasks from persistence
            tasks = []
            if hasattr(self.bus_manager, 'get_active_tasks'):
                tasks = await self.bus_manager.get_active_tasks()
            
            # Format tasks for visibility
            visible_tasks = []
            for task in tasks:
                visible_tasks.append({
                    "task_id": task.task_id,
                    "channel_id": task.channel_id,
                    "content": task.content[:200] + "..." if len(task.content) > 200 else task.content,
                    "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                    "created_at": task.created_at,
                    "updated_at": task.updated_at,
                    "thought_count": task.thought_count if hasattr(task, 'thought_count') else 0
                })
            
            return web.json_response({
                "tasks": visible_tasks,
                "count": len(visible_tasks),
                "timestamp": self._get_current_time_iso()
            })
            
        except Exception as e:
            logger.error(f"Error getting active tasks: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_system_snapshot(self, request: web.Request) -> web.Response:
        """Get current system snapshot - the agent's awareness of its own state."""
        try:
            # Get system snapshot from telemetry
            if self.telemetry_collector:
                snapshot = await self.telemetry_collector.get_system_snapshot()
                return web.json_response(snapshot.model_dump(mode='json'))
            else:
                return web.json_response(
                    {"error": "System snapshot not available"},
                    status=503
                )
            
        except Exception as e:
            logger.error(f"Error getting system snapshot: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_recent_decisions(self, request: web.Request) -> web.Response:
        """Get recent decisions made by the agent's DMAs."""
        try:
            limit = int(request.query.get('limit', 20))
            
            # Get correlations filtered by DMA decisions
            correlations = []
            if hasattr(self.bus_manager, 'get_correlations'):
                correlations = await self.bus_manager.get_correlations(
                    correlation_type="THOUGHT_DMA",
                    limit=limit
                )
            
            # Format decisions for visibility
            decisions = []
            for corr in correlations:
                if corr.response_data:
                    decisions.append({
                        "correlation_id": corr.correlation_id,
                        "thought_id": corr.thought_id,
                        "service": corr.service_name,
                        "decision": corr.response_data.get('action_type', 'unknown'),
                        "reasoning": corr.response_data.get('reasoning', ''),
                        "confidence": corr.response_data.get('confidence', 0),
                        "timestamp": corr.created_at
                    })
            
            return web.json_response({
                "decisions": decisions,
                "count": len(decisions),
                "timestamp": self._get_current_time_iso()
            })
            
        except Exception as e:
            logger.error(f"Error getting recent decisions: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_correlations(self, request: web.Request) -> web.Response:
        """Get service correlations - how different parts of the system interact."""
        try:
            limit = int(request.query.get('limit', 50))
            correlation_type = request.query.get('type')
            service_name = request.query.get('service')
            
            # Build filter criteria
            filters = {}
            if correlation_type:
                filters['correlation_type'] = correlation_type
            if service_name:
                filters['service_name'] = service_name
            
            # Get correlations
            correlations = []
            if hasattr(self.bus_manager, 'get_correlations'):
                correlations = await self.bus_manager.get_correlations(limit=limit, **filters)
            
            # Format for visibility
            visible_correlations = []
            for corr in correlations:
                visible_correlations.append({
                    "correlation_id": corr.correlation_id,
                    "type": corr.correlation_type,
                    "service": corr.service_name,
                    "handler": corr.handler_name,
                    "action": corr.action_type,
                    "thought_id": corr.thought_id,
                    "task_id": corr.task_id,
                    "status": corr.status.value if hasattr(corr.status, 'value') else str(corr.status),
                    "created_at": corr.created_at,
                    "duration_ms": corr.duration_ms
                })
            
            return web.json_response({
                "correlations": visible_correlations,
                "count": len(visible_correlations),
                "filters": filters,
                "timestamp": self._get_current_time_iso()
            })
            
        except Exception as e:
            logger.error(f"Error getting correlations: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_task_details(self, request: web.Request) -> web.Response:
        """Get detailed information about a specific task."""
        try:
            task_id = request.match_info['task_id']
            
            # Get task details
            task = None
            thoughts = []
            
            if hasattr(self.bus_manager, 'get_task'):
                task = await self.bus_manager.get_task(task_id)
            
            if hasattr(self.bus_manager, 'get_thoughts_for_task'):
                thoughts = await self.bus_manager.get_thoughts_for_task(task_id)
            
            if not task:
                return web.json_response(
                    {"error": f"Task {task_id} not found"},
                    status=404
                )
            
            # Build task hierarchy
            task_details = {
                "task_id": task.task_id,
                "channel_id": task.channel_id,
                "content": task.content,
                "status": task.status.value if hasattr(task.status, 'value') else str(task.status),
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "thoughts": [
                    {
                        "thought_id": t.thought_id,
                        "content": t.content[:200] + "..." if len(t.content) > 200 else t.content,
                        "type": t.thought_type.value if hasattr(t.thought_type, 'value') else str(t.thought_type),
                        "round": t.round_number,
                        "status": t.status.value if hasattr(t.status, 'value') else str(t.status)
                    }
                    for t in thoughts
                ]
            }
            
            return web.json_response(task_details)
            
        except Exception as e:
            logger.error(f"Error getting task details: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_thought_details(self, request: web.Request) -> web.Response:
        """Get detailed information about a specific thought."""
        try:
            thought_id = request.match_info['thought_id']
            
            # Get thought details
            thought = None
            correlations = []
            
            if hasattr(self.bus_manager, 'get_thought'):
                thought = await self.bus_manager.get_thought(thought_id)
            
            if hasattr(self.bus_manager, 'get_correlations'):
                correlations = await self.bus_manager.get_correlations(
                    thought_id=thought_id
                )
            
            if not thought:
                return web.json_response(
                    {"error": f"Thought {thought_id} not found"},
                    status=404
                )
            
            # Build thought details with its processing history
            thought_details = {
                "thought_id": thought.thought_id,
                "task_id": thought.task_id,
                "content": thought.content,
                "type": thought.thought_type.value if hasattr(thought.thought_type, 'value') else str(thought.thought_type),
                "round_number": thought.round_number,
                "status": thought.status.value if hasattr(thought.status, 'value') else str(thought.status),
                "created_at": thought.created_at,
                "updated_at": thought.updated_at,
                "processing_history": [
                    {
                        "service": corr.service_name,
                        "action": corr.action_type,
                        "status": corr.status.value if hasattr(corr.status, 'value') else str(corr.status),
                        "timestamp": corr.created_at,
                        "duration_ms": corr.duration_ms
                    }
                    for corr in correlations
                ]
            }
            
            # Add decision details if available
            if thought.decision_context:
                thought_details['decision'] = {
                    "selected_action": thought.decision_context.get('selected_action'),
                    "reasoning": thought.decision_context.get('reasoning'),
                    "alternatives_considered": thought.decision_context.get('alternatives', [])
                }
            
            return web.json_response(thought_details)
            
        except Exception as e:
            logger.error(f"Error getting thought details: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)