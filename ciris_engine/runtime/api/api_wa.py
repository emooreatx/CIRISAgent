"""API WA (Wise Authority) endpoints for CIRISAgent, using the multi_service_sink for backend logic."""
import logging
from aiohttp import web
from typing import Any

logger = logging.getLogger(__name__)

class APIWARoutes:
    def __init__(self, multi_service_sink: Any) -> None:
        self.multi_service_sink = multi_service_sink

    def register(self, app: web.Application) -> None:
        app.router.add_post('/v1/guidance', self._handle_guidance)
        app.router.add_post('/v1/defer', self._handle_defer)
        app.router.add_get('/v1/wa/deferrals', self._handle_wa_deferrals)
        app.router.add_get('/v1/wa/deferrals/{deferral_id}', self._handle_wa_deferral_detail)
        app.router.add_post('/v1/wa/feedback', self._handle_wa_feedback)

    async def _handle_guidance(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        try:
            guidance = await self.multi_service_sink.fetch_guidance(data)
            return web.json_response({"guidance": guidance})
        except Exception as e:
            logger.error(f"Error fetching guidance: {e}")
            return web.json_response({"guidance": None, "error": str(e)}, status=500)

    async def _handle_defer(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            thought_id = data.get("thought_id")
            reason = data.get("reason", "")
            await self.multi_service_sink.send_deferral(thought_id or "unknown", reason)
            return web.json_response({"result": "deferred"})
        except Exception as e:
            logger.error(f"Error deferring: {e}")
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_wa_deferrals(self, request: web.Request) -> web.Response:
        try:
            deferrals = await self.multi_service_sink.get_deferrals()
            return web.json_response(deferrals)
        except Exception as e:
            logger.error(f"Error getting deferrals: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_wa_deferral_detail(self, request: web.Request) -> web.Response:
        deferral_id = request.match_info.get('deferral_id')
        try:
            detail = await self.multi_service_sink.get_deferral_detail(deferral_id)
            return web.json_response(detail)
        except Exception as e:
            logger.error(f"Error getting deferral detail: {e}")
            return web.json_response({"id": deferral_id, "error": str(e)}, status=500)

    async def _handle_wa_feedback(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            result = await self.multi_service_sink.submit_feedback(data)
            return web.json_response({"result": result or "ok"})
        except Exception as e:
            logger.error(f"Error submitting feedback: {e}")
            return web.json_response({"error": str(e)}, status=500)
