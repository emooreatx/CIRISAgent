"""API telemetry endpoints - system monitoring and observability."""
import logging
from datetime import datetime, timezone
from typing import Any, Optional, Dict, List
from aiohttp import web

from ciris_engine.schemas.telemetry_schemas_v1 import MetricType

logger = logging.getLogger(__name__)


class APITelemetryRoutes:
    """Routes for system telemetry and monitoring."""
    
    def __init__(self, telemetry_collector: Any, service_registry: Any, bus_manager: Any) -> None:
        self.telemetry_collector = telemetry_collector
        self.service_registry = service_registry
        self.bus_manager = bus_manager
    
    def register(self, app: web.Application) -> None:
        """Register telemetry routes."""
        # System monitoring
        app.router.add_get('/v1/telemetry/overview', self._handle_telemetry_overview)
        app.router.add_get('/v1/telemetry/metrics', self._handle_metrics)
        app.router.add_get('/v1/telemetry/metrics/{metric_name}', self._handle_metric_details)
        app.router.add_post('/v1/telemetry/metrics', self._handle_record_metric)
        
        # Resource monitoring
        app.router.add_get('/v1/telemetry/resources', self._handle_resource_usage)
        app.router.add_get('/v1/telemetry/resources/history', self._handle_resource_history)
        
        # Service health
        app.router.add_get('/v1/telemetry/services', self._handle_service_health)
        app.router.add_get('/v1/telemetry/services/{service_type}', self._handle_service_type_health)
        
        # Audit trail
        app.router.add_get('/v1/telemetry/audit', self._handle_audit_trail)
        app.router.add_get('/v1/telemetry/audit/stats', self._handle_audit_stats)
    
    async def _handle_telemetry_overview(self, request: web.Request) -> web.Response:
        """Get comprehensive telemetry overview."""
        try:
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Get full telemetry snapshot
            snapshot = await self.telemetry_collector.get_telemetry_snapshot()
            
            return web.json_response(snapshot.model_dump(mode='json'))
            
        except Exception as e:
            logger.error(f"Error getting telemetry overview: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Get current metrics."""
        try:
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Get metric type filter
            metric_type = request.query.get('type')
            
            # Get current metrics
            metrics = await self.telemetry_collector.get_current_metrics()
            
            # Filter by type if requested
            if metric_type:
                filtered_metrics = {}
                for key, value in metrics.items():
                    if key.startswith(metric_type):
                        filtered_metrics[key] = value
                metrics = filtered_metrics
            
            return web.json_response({
                "metrics": metrics,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "count": len(metrics)
            })
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_metric_details(self, request: web.Request) -> web.Response:
        """Get detailed history for a specific metric."""
        try:
            metric_name = request.match_info['metric_name']
            hours = int(request.query.get('hours', 24))
            
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Get metric history
            history = []
            if hasattr(self.telemetry_collector, 'get_metric_history'):
                history = await self.telemetry_collector.get_metric_history(metric_name, hours)
            
            return web.json_response({
                "metric_name": metric_name,
                "history": history,
                "hours": hours,
                "count": len(history)
            })
            
        except Exception as e:
            logger.error(f"Error getting metric details: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_record_metric(self, request: web.Request) -> web.Response:
        """Record a custom metric."""
        try:
            data = await request.json()
            
            metric_name = data.get('metric_name')
            value = data.get('value')
            tags = data.get('tags', {})
            
            if not metric_name or value is None:
                return web.json_response(
                    {"error": "metric_name and value are required"},
                    status=400
                )
            
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Record the metric
            if hasattr(self.telemetry_collector, 'record_metric'):
                await self.telemetry_collector.record_metric(
                    metric_name=metric_name,
                    value=value,
                    metric_type=MetricType.GAUGE,
                    tags=tags
                )
            
            return web.json_response({
                "status": "recorded",
                "metric_name": metric_name,
                "value": value,
                "tags": tags,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error recording metric: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_resource_usage(self, request: web.Request) -> web.Response:
        """Get current resource usage."""
        try:
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Get resource metrics
            resources = {}
            if hasattr(self.telemetry_collector, 'get_resource_usage'):
                resources = await self.telemetry_collector.get_resource_usage()
            else:
                # Try to get from current metrics
                metrics = await self.telemetry_collector.get_current_metrics()
                resources = {
                    "cpu_percent": metrics.get("system.cpu.percent", 0),
                    "memory_mb": metrics.get("system.memory.mb", 0),
                    "memory_percent": metrics.get("system.memory.percent", 0),
                    "disk_usage_percent": metrics.get("system.disk.percent", 0),
                    "open_files": metrics.get("system.files.open", 0),
                    "thread_count": metrics.get("system.threads", 0)
                }
            
            # Add environmental metrics if available
            resources.update({
                "tokens_used": metrics.get("llm.tokens.total", 0) if 'metrics' in locals() else 0,
                "water_ml": metrics.get("environmental.water_ml", 0) if 'metrics' in locals() else 0,
                "carbon_g": metrics.get("environmental.carbon_g", 0) if 'metrics' in locals() else 0,
                "energy_kwh": metrics.get("environmental.energy_kwh", 0) if 'metrics' in locals() else 0
            })
            
            return web.json_response({
                "resources": resources,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_resource_history(self, request: web.Request) -> web.Response:
        """Get resource usage history."""
        try:
            hours = int(request.query.get('hours', 24))
            resource_type = request.query.get('type', 'all')
            
            if not self.telemetry_collector:
                return web.json_response({"error": "Telemetry collector not available"}, status=503)
            
            # Get resource history
            history = {}
            metric_prefixes = {
                'cpu': 'system.cpu',
                'memory': 'system.memory',
                'disk': 'system.disk',
                'environmental': 'environmental',
                'all': 'system'
            }
            
            prefix = metric_prefixes.get(resource_type, 'system')
            
            if hasattr(self.telemetry_collector, 'get_metrics_by_prefix'):
                history = await self.telemetry_collector.get_metrics_by_prefix(prefix, hours)
            
            return web.json_response({
                "resource_type": resource_type,
                "history": history,
                "hours": hours
            })
            
        except Exception as e:
            logger.error(f"Error getting resource history: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_service_health(self, request: web.Request) -> web.Response:
        """Get health status of all services."""
        try:
            if not self.service_registry:
                return web.json_response({"error": "Service registry not available"}, status=503)
            
            # Get all services grouped by type
            services_health = {}
            
            from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
            for service_type in ServiceType:
                providers = self.service_registry.get_services_by_type(service_type)
                
                service_list = []
                for provider in providers:
                    # Get provider info
                    provider_info = {
                        "name": provider.__class__.__name__,
                        "instance_id": str(id(provider)),
                        "healthy": True,  # Default
                        "circuit_breaker": "closed"  # Default
                    }
                    
                    # Check health if method available
                    if hasattr(provider, 'is_healthy'):
                        try:
                            if asyncio.iscoroutinefunction(provider.is_healthy):
                                provider_info['healthy'] = await provider.is_healthy()
                            else:
                                provider_info['healthy'] = provider.is_healthy()
                        except Exception:
                            provider_info['healthy'] = False
                    
                    # Get circuit breaker state if available
                    if hasattr(self.service_registry, 'get_circuit_breaker_state'):
                        cb_state = self.service_registry.get_circuit_breaker_state(provider)
                        if cb_state:
                            provider_info['circuit_breaker'] = cb_state
                    
                    # Get capabilities
                    if hasattr(provider, 'get_capabilities'):
                        try:
                            caps = await provider.get_capabilities()
                            provider_info['capabilities'] = caps
                        except Exception:
                            provider_info['capabilities'] = []
                    
                    service_list.append(provider_info)
                
                if service_list:
                    services_health[service_type.value] = {
                        "providers": service_list,
                        "total": len(service_list),
                        "healthy": sum(1 for s in service_list if s['healthy'])
                    }
            
            # Overall health assessment
            total_services = sum(len(v['providers']) for v in services_health.values())
            healthy_services = sum(v['healthy'] for v in services_health.values())
            
            return web.json_response({
                "services": services_health,
                "summary": {
                    "total_services": total_services,
                    "healthy_services": healthy_services,
                    "health_percentage": (healthy_services / total_services * 100) if total_services > 0 else 0
                },
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting service health: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_service_type_health(self, request: web.Request) -> web.Response:
        """Get detailed health for a specific service type."""
        try:
            service_type = request.match_info['service_type']
            
            if not self.service_registry:
                return web.json_response({"error": "Service registry not available"}, status=503)
            
            # Convert string to ServiceType enum
            from ciris_engine.schemas.foundational_schemas_v1 import ServiceType
            try:
                service_enum = ServiceType(service_type.upper())
            except ValueError:
                return web.json_response(
                    {"error": f"Invalid service type: {service_type}"},
                    status=400
                )
            
            # Get providers for this service type
            providers = self.service_registry.get_services_by_type(service_enum)
            
            detailed_health = []
            for provider in providers:
                provider_details = {
                    "name": provider.__class__.__name__,
                    "instance_id": str(id(provider)),
                    "module": provider.__class__.__module__,
                    "healthy": True,
                    "circuit_breaker": "closed",
                    "metrics": {}
                }
                
                # Detailed health check
                if hasattr(provider, 'get_health_details'):
                    try:
                        health_details = await provider.get_health_details()
                        provider_details.update(health_details)
                    except Exception as e:
                        provider_details['healthy'] = False
                        provider_details['error'] = str(e)
                elif hasattr(provider, 'is_healthy'):
                    try:
                        provider_details['healthy'] = await provider.is_healthy()
                    except Exception:
                        provider_details['healthy'] = False
                
                # Get metrics if available
                if hasattr(provider, 'get_metrics'):
                    try:
                        provider_details['metrics'] = await provider.get_metrics()
                    except Exception:
                        pass
                
                detailed_health.append(provider_details)
            
            return web.json_response({
                "service_type": service_type,
                "providers": detailed_health,
                "count": len(detailed_health),
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting service type health: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_audit_trail(self, request: web.Request) -> web.Response:
        """Get audit trail entries."""
        try:
            limit = int(request.query.get('limit', 100))
            event_type = request.query.get('type')
            start_time = request.query.get('start_time')
            
            # Get audit service from bus manager
            audit_entries = []
            if self.bus_manager and hasattr(self.bus_manager, 'get_audit_entries'):
                filters = {}
                if event_type:
                    filters['event_type'] = event_type
                if start_time:
                    filters['start_time'] = start_time
                    
                audit_entries = await self.bus_manager.get_audit_entries(
                    limit=limit,
                    **filters
                )
            
            return web.json_response({
                "entries": audit_entries,
                "count": len(audit_entries),
                "filters": {
                    "event_type": event_type,
                    "start_time": start_time
                }
            })
            
        except Exception as e:
            logger.error(f"Error getting audit trail: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_audit_stats(self, request: web.Request) -> web.Response:
        """Get audit statistics."""
        try:
            hours = int(request.query.get('hours', 24))
            
            # Get audit stats
            stats = {}
            if self.bus_manager and hasattr(self.bus_manager, 'get_audit_stats'):
                stats = await self.bus_manager.get_audit_stats(hours=hours)
            else:
                # Basic stats from audit entries
                audit_entries = []
                if hasattr(self.bus_manager, 'get_audit_entries'):
                    audit_entries = await self.bus_manager.get_audit_entries(limit=1000)
                
                # Calculate basic stats
                event_types = {}
                for entry in audit_entries:
                    event_type = entry.get('event_type', 'unknown')
                    event_types[event_type] = event_types.get(event_type, 0) + 1
                
                stats = {
                    "total_events": len(audit_entries),
                    "event_types": event_types,
                    "hours": hours
                }
            
            return web.json_response({
                "stats": stats,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting audit stats: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)