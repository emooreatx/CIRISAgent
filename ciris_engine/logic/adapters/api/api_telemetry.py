"""API telemetry endpoints - system monitoring and observability."""
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any
from aiohttp import web

from ciris_engine.schemas.runtime.enums import ServiceType as RuntimeServiceType

logger = logging.getLogger(__name__)

class APITelemetryRoutes:
    """Routes for system telemetry and monitoring - reads from graph memory."""
    
    def __init__(self, service_registry: Any, bus_manager: Any, runtime: Any) -> None:
        self.service_registry = service_registry
        self.bus_manager = bus_manager
        self.runtime = runtime
        self.time_service = None
        self.memory_bus = bus_manager.memory if bus_manager else None
        if runtime:
            try:
                time_services = runtime.get_services_by_type(RuntimeServiceType.TIME)
                if time_services:
                    self.time_service = time_services[0]
            except Exception:
                pass
    
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
        """Get comprehensive telemetry overview from graph memory."""
        try:
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Query recent telemetry nodes from graph memory
            from ciris_engine.schemas.services.operations import MemoryQuery
            from ciris_engine.schemas.services.graph_core import NodeType, GraphScope
            
            query = MemoryQuery(
                type=NodeType.TELEMETRY,
                scope=GraphScope.LOCAL,
                limit=100,
                include_edges=False,
                depth=1
            )
            
            nodes = await self.memory_bus.recall(query, handler_name="api.telemetry")
            
            # Group metrics by name
            metrics_summary = {}
            for node in nodes:
                if isinstance(node, dict):
                    attrs = node.get("attributes", {})
                else:
                    attrs = node.attributes if hasattr(node, "attributes") else {}
                
                metric_name = attrs.get("metric_name", "unknown")
                if metric_name not in metrics_summary:
                    metrics_summary[metric_name] = {
                        "count": 0,
                        "latest_timestamp": None,
                        "adapter_ids": set()
                    }
                
                metrics_summary[metric_name]["count"] += 1
                timestamp = attrs.get("timestamp")
                if timestamp and (not metrics_summary[metric_name]["latest_timestamp"] or 
                                timestamp > metrics_summary[metric_name]["latest_timestamp"]):
                    metrics_summary[metric_name]["latest_timestamp"] = timestamp
                
                adapter_id = attrs.get("adapter_id")
                if adapter_id:
                    metrics_summary[metric_name]["adapter_ids"].add(adapter_id)
            
            # Convert sets to lists for JSON serialization
            for metric in metrics_summary.values():
                metric["adapter_ids"] = list(metric["adapter_ids"])
            
            return web.json_response({
                "status": "active",
                "metrics_summary": metrics_summary,
                "total_telemetry_nodes": len(nodes),
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting telemetry overview: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_metrics(self, request: web.Request) -> web.Response:
        """Get current metrics from graph memory."""
        try:
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Use timeseries recall for recent metrics
            hours = float(request.query.get('hours', 1))  # Default to last hour
            
            datapoints = await self.memory_bus.recall_timeseries(
                scope="local",
                hours=int(hours),
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="api.telemetry"
            )
            
            # Group metrics by name
            current_metrics = {}
            for dp in datapoints:
                metric_name = dp.metric_name
                if metric_name not in current_metrics:
                    current_metrics[metric_name] = {
                        "latest_value": dp.value,
                        "latest_timestamp": dp.timestamp,
                        "values": [],
                        "count": 0
                    }
                
                current_metrics[metric_name]["values"].append({
                    "value": dp.value,
                    "timestamp": dp.timestamp,
                    "tags": dp.tags
                })
                current_metrics[metric_name]["count"] += 1
                
                # Update latest if newer
                if dp.timestamp > current_metrics[metric_name]["latest_timestamp"]:
                    current_metrics[metric_name]["latest_value"] = dp.value
                    current_metrics[metric_name]["latest_timestamp"] = dp.timestamp
            
            return web.json_response({
                "metrics": current_metrics,
                "period_hours": hours,
                "total_datapoints": len(datapoints),
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting metrics: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_metric_details(self, request: web.Request) -> web.Response:
        """Get detailed history for a specific metric."""
        try:
            metric_name = request.match_info['metric_name']
            hours = int(request.query.get('hours', 24))
            
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Query timeseries data for specific metric
            datapoints = await self.memory_bus.recall_timeseries(
                scope="local",
                hours=hours,
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="api.telemetry"
            )
            
            # Filter for specific metric name
            metric_history = []
            for dp in datapoints:
                if dp.metric_name == metric_name:
                    metric_history.append({
                        "timestamp": dp.timestamp,
                        "value": dp.value,
                        "tags": dp.tags or {}
                    })
            
            # Sort by timestamp
            metric_history.sort(key=lambda x: x["timestamp"])
            
            # Calculate statistics
            if metric_history:
                values = [h["value"] for h in metric_history]
                stats = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values)
                }
            else:
                stats = {"min": 0, "max": 0, "avg": 0, "count": 0}
            
            return web.json_response({
                "metric_name": metric_name,
                "history": metric_history,
                "hours": hours,
                "stats": stats,
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
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
            
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Create telemetry node for external metric
            from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
            timestamp = self.time_service.now() if self.time_service else datetime.now(timezone.utc)
            
            node = GraphNode(
                id=f"telemetry_{timestamp.isoformat()}_{metric_name}",
                type=NodeType.TELEMETRY,
                scope=GraphScope.LOCAL,
                attributes={
                    "metric_name": metric_name,
                    "value": value,
                    "source": "external_api",
                    "timestamp": timestamp.isoformat(),
                    "created_at": timestamp,
                    "updated_at": timestamp,
                    "created_by": "api_telemetry",
                    "tags": tags
                },
                version=1,
                updated_by="api_telemetry",
                updated_at=timestamp
            )
            
            # Store in graph memory
            result = await self.memory_bus.memorize(
                node=node,
                handler_name="api.telemetry",
                metadata={"source": "external_metric"}
            )
            
            success = result.status.value == "OK" if hasattr(result, 'status') else True
            
            return web.json_response({
                "status": "recorded" if success else "failed",
                "metric_name": metric_name,
                "value": value,
                "tags": tags,
                "node_id": node.id if success else None,
                "timestamp": timestamp.isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error recording metric: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_resource_usage(self, request: web.Request) -> web.Response:
        """Get current resource usage."""
        try:
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Query recent resource metrics from timeseries
            datapoints = await self.memory_bus.recall_timeseries(
                scope="local",
                hours=1,  # Last hour
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="api.telemetry"
            )
            
            # Aggregate resource metrics
            resources = {
                "tokens_used": 0,
                "water_ml": 0.0,
                "carbon_g": 0.0,
                "energy_kwh": 0.0,
                "cpu_percent": 0.0,
                "memory_mb": 0.0,
                "disk_gb": 0.0
            }
            
            # Track latest values for each metric
            latest_values = {}
            
            for dp in datapoints:
                metric_name = dp.metric_name
                
                # Map metric names to resource types
                if "tokens" in metric_name:
                    latest_values["tokens_used"] = dp.value
                elif "water" in metric_name:
                    latest_values["water_ml"] = dp.value
                elif "carbon" in metric_name:
                    latest_values["carbon_g"] = dp.value
                elif "energy" in metric_name:
                    latest_values["energy_kwh"] = dp.value
                elif "cpu" in metric_name:
                    latest_values["cpu_percent"] = dp.value
                elif "memory" in metric_name and "mb" in metric_name.lower():
                    latest_values["memory_mb"] = dp.value
                elif "disk" in metric_name and "gb" in metric_name.lower():
                    latest_values["disk_gb"] = dp.value
            
            # Update resources with latest values
            resources.update(latest_values)
            
            return web.json_response({
                "resources": resources,
                "period": "last_hour",
                "datapoints_processed": len(datapoints),
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting resource usage: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)
    
    async def _handle_resource_history(self, request: web.Request) -> web.Response:
        """Get resource usage history."""
        try:
            hours = int(request.query.get('hours', 24))
            resource_type = request.query.get('type', 'all')
            
            if not self.memory_bus:
                return web.json_response({"error": "Memory bus not available"}, status=503)
            
            # Query timeseries data
            datapoints = await self.memory_bus.recall_timeseries(
                scope="local",
                hours=hours,
                correlation_types=["METRIC_DATAPOINT"],
                handler_name="api.telemetry"
            )
            
            # Define metric filters based on resource type
            metric_filters = {
                'cpu': lambda m: 'cpu' in m.lower(),
                'memory': lambda m: 'memory' in m.lower(),
                'disk': lambda m: 'disk' in m.lower(),
                'environmental': lambda m: any(x in m.lower() for x in ['water', 'carbon', 'energy']),
                'all': lambda m: True
            }
            
            filter_fn = metric_filters.get(resource_type, metric_filters['all'])
            
            # Group history by metric name
            history = {}
            for dp in datapoints:
                if filter_fn(dp.metric_name):
                    if dp.metric_name not in history:
                        history[dp.metric_name] = []
                    
                    history[dp.metric_name].append({
                        "timestamp": dp.timestamp,
                        "value": dp.value,
                        "tags": dp.tags or {}
                    })
            
            # Sort each metric's history by timestamp
            for metric_name in history:
                history[metric_name].sort(key=lambda x: x["timestamp"])
            
            # Calculate summary statistics
            summary = {}
            for metric_name, values in history.items():
                if values:
                    vals = [v["value"] for v in values]
                    summary[metric_name] = {
                        "count": len(vals),
                        "min": min(vals),
                        "max": max(vals),
                        "avg": sum(vals) / len(vals),
                        "latest": vals[-1]
                    }
            
            return web.json_response({
                "resource_type": resource_type,
                "history": history,
                "hours": hours,
                "summary": summary,
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
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
            services_health: Dict[str, dict] = {}
            
            from ciris_engine.schemas.runtime.enums import ServiceType
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
            total_services = sum(int(v['total']) for v in services_health.values())
            healthy_services = sum(int(v['healthy']) for v in services_health.values())
            
            return web.json_response({
                "services": services_health,
                "summary": {
                    "total_services": total_services,
                    "healthy_services": healthy_services,
                    "health_percentage": (healthy_services / total_services * 100) if total_services > 0 else 0
                },
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
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
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
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
                event_types: Dict[str, int] = {}
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
                "timestamp": self.time_service.now().isoformat() if self.time_service else datetime.now(timezone.utc).isoformat()
            })
            
        except Exception as e:
            logger.error(f"Error getting audit stats: {e}", exc_info=True)
            return web.json_response({"error": str(e)}, status=500)