"""API audit endpoints for CIRISAgent, using the real audit service."""
import logging
from aiohttp import web
import json
from typing import Any

logger = logging.getLogger(__name__)

class APIAuditRoutes:
    def __init__(self, audit_service: Any) -> None:
        self.audit_service = audit_service

    def register(self, app: web.Application) -> None:
        app.router.add_get('/v1/audit', self._handle_audit)

    async def _handle_audit(self, request: web.Request) -> web.Response:
        try:
            log_path = getattr(self.audit_service, 'log_path', None)
            if log_path and log_path.exists():
                with log_path.open('r', encoding='utf-8') as f:
                    lines = f.readlines()[-100:]
                    entries = [line.strip() for line in lines if line.strip()]
                    entries = [json.loads(e) for e in entries]
                    return web.json_response(entries)
        except Exception as e:
            logger.error(f"Error reading audit log: {e}")
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response([])
