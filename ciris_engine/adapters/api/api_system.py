"""API system endpoints for comprehensive telemetry and system control."""
import logging
from aiohttp import web
from typing import Any

logger = logging.getLogger(__name__)

class APISystemRoutes:
    def __init__(self, telemetry_collector: Any) -> None:
        self.telemetry_collector = telemetry_collector

    def register(self, app: web.Application) -> None:
        # Telemetry endpoints
        app.router.add_get('/v1/system/telemetry', self._handle_telemetry_snapshot)
        app.router.add_get('/v1/system/adapters', self._handle_adapters)
        app.router.add_get('/v1/system/services', self._handle_services)
        app.router.add_get('/v1/system/processor/state', self._handle_processor_state)
        app.router.add_get('/v1/system/configuration', self._handle_configuration)
        app.router.add_get('/v1/system/health', self._handle_health)
        
        # Processor control endpoints
        app.router.add_post('/v1/system/processor/step', self._handle_single_step)
        app.router.add_post('/v1/system/processor/pause', self._handle_pause_processing)
        app.router.add_post('/v1/system/processor/resume', self._handle_resume_processing)
        app.router.add_get('/v1/system/processor/queue', self._handle_processing_queue)
        
        # Metrics endpoints
        app.router.add_post('/v1/system/metrics', self._handle_record_metric)
        app.router.add_get('/v1/system/metrics/{metric_name}/history', self._handle_metrics_history)

    async def _handle_telemetry_snapshot(self, request: web.Request) -> web.Response:
        """Get complete telemetry snapshot"""
        try:
            snapshot = await self.telemetry_collector.get_telemetry_snapshot()
            return web.json_response(snapshot.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error getting telemetry snapshot: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_adapters(self, request: web.Request) -> web.Response:
        """Get adapter information"""
        try:
            adapters = await self.telemetry_collector.get_adapters_info()
            return web.json_response([adapter.model_dump(mode="json") for adapter in adapters], status=200)
        except Exception as e:
            logger.error(f"Error getting adapters info: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_services(self, request: web.Request) -> web.Response:
        """Get services information"""
        try:
            services = await self.telemetry_collector.get_services_info()
            return web.json_response([service.model_dump(mode="json") for service in services], status=200)
        except Exception as e:
            logger.error(f"Error getting services info: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_processor_state(self, request: web.Request) -> web.Response:
        """Get processor state information"""
        try:
            processor_state = await self.telemetry_collector.get_processor_state()
            return web.json_response(processor_state.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error getting processor state: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_configuration(self, request: web.Request) -> web.Response:
        """Get configuration snapshot"""
        try:
            config = await self.telemetry_collector.get_configuration_snapshot()
            return web.json_response(config.model_dump(mode="json"), status=200)
        except Exception as e:
            logger.error(f"Error getting configuration: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_health(self, request: web.Request) -> web.Response:
        """Get system health status"""
        try:
            health = await self.telemetry_collector.get_health_status()
            return web.json_response(health, status=200)
        except Exception as e:
            logger.error(f"Error getting health status: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_single_step(self, request: web.Request) -> web.Response:
        """Execute a single processing step"""
        try:
            result = await self.telemetry_collector.single_step()
            return web.json_response(result, status=200)
        except Exception as e:
            logger.error(f"Error executing single step: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_pause_processing(self, request: web.Request) -> web.Response:
        """Pause processor"""
        try:
            success = await self.telemetry_collector.pause_processing()
            return web.json_response({"success": success}, status=200)
        except Exception as e:
            logger.error(f"Error pausing processing: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_resume_processing(self, request: web.Request) -> web.Response:
        """Resume processor"""
        try:
            success = await self.telemetry_collector.resume_processing()
            return web.json_response({"success": success}, status=200)
        except Exception as e:
            logger.error(f"Error resuming processing: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_processing_queue(self, request: web.Request) -> web.Response:
        """Get processing queue status"""
        try:
            queue_status = await self.telemetry_collector.get_processing_queue_status()
            return web.json_response(queue_status, status=200)
        except Exception as e:
            logger.error(f"Error getting queue status: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_record_metric(self, request: web.Request) -> web.Response:
        """Record a custom metric"""
        try:
            data = await request.json()
            metric_name = data.get("metric_name")
            value = data.get("value")
            tags = data.get("tags")
            
            if not metric_name or value is None:
                return web.json_response({"error": "Missing metric_name or value"}, status=400)
            
            await self.telemetry_collector.record_metric(metric_name, value, tags)
            return web.json_response({"status": "recorded"}, status=200)
        except Exception as e:
            logger.error(f"Error recording metric: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_metrics_history(self, request: web.Request) -> web.Response:
        """Get metrics history for a specific metric"""
        try:
            metric_name = request.match_info.get('metric_name')
            
            # Validate hours parameter
            try:
                hours = int(request.query.get('hours', 24))
            except ValueError:
                return web.json_response({"error": "Invalid hours parameter - must be a valid integer"}, status=400)
            
            history = await self.telemetry_collector.get_metrics_history(metric_name, hours)
            return web.json_response({"metric_name": metric_name, "history": history}, status=200)
        except Exception as e:
            logger.error(f"Error getting metrics history: {e}")
            return web.json_response({"error": str(e)}, status=500)