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
        app.router.add_post('/v1/audit/query', self._handle_audit_query)
        app.router.add_post('/v1/audit/log', self._handle_audit_log)

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

    async def _handle_audit_query(self, request: web.Request) -> web.Response:
        """Query audit trail with filters."""
        try:
            data = await request.json()
            from datetime import datetime
            
            # Parse query parameters
            start_time = None
            end_time = None
            if data.get("start_time"):
                start_time = datetime.fromisoformat(data["start_time"].replace("Z", "+00:00"))
            if data.get("end_time"):
                end_time = datetime.fromisoformat(data["end_time"].replace("Z", "+00:00"))
            
            action_types = data.get("action_types")
            thought_id = data.get("thought_id")
            task_id = data.get("task_id")
            limit = data.get("limit", 100)
            
            if hasattr(self.audit_service, 'query_audit_trail'):
                results = await self.audit_service.query_audit_trail(
                    start_time=start_time,
                    end_time=end_time,
                    action_types=action_types,
                    thought_id=thought_id,
                    task_id=task_id,
                    limit=limit
                )
                return web.json_response({"entries": results})
            else:
                # Fallback to basic audit log reading with filtering
                entries = []
                log_path = getattr(self.audit_service, 'log_path', None)
                if log_path and log_path.exists():
                    with log_path.open('r', encoding='utf-8') as f:
                        lines = f.readlines()[-500:]  # Get more lines for filtering
                        for line in lines:
                            try:
                                entry = json.loads(line.strip())
                                # Apply filters
                                if thought_id and entry.get("thought_id") != thought_id:
                                    continue
                                if task_id and entry.get("task_id") != task_id:
                                    continue
                                if action_types and entry.get("action_type") not in action_types:
                                    continue
                                entries.append(entry)
                            except:
                                continue
                return web.json_response({"entries": entries[-limit:]})
        except Exception as e:
            logger.error(f"Error querying audit trail: {e}")
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_audit_log(self, request: web.Request) -> web.Response:
        """Log a custom audit event."""
        try:
            data = await request.json()
            event_type = data.get("event_type", "custom")
            event_data = data.get("event_data", {})
            
            if hasattr(self.audit_service, 'log_event'):
                await self.audit_service.log_event(event_type, event_data)
                return web.json_response({"status": "logged"})
            else:
                return web.json_response({"error": "Audit logging not available"}, status=501)
        except Exception as e:
            logger.error(f"Error logging audit event: {e}")
            return web.json_response({"error": str(e)}, status=500)
