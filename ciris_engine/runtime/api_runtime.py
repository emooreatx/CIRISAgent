"""API runtime implementation for REST interfaces."""
import logging
import uuid
from typing import Optional, Dict, Any

from aiohttp import web

from .ciris_runtime import CIRISRuntime
from ciris_engine.adapters.api import APIAdapter, APIObserver
from ciris_engine.schemas.foundational_schemas_v1 import IncomingMessage
from ciris_engine.action_handlers.handler_registry import build_action_dispatcher
from ciris_engine.registries.base import Priority

logger = logging.getLogger(__name__)


class APIRuntime(CIRISRuntime):
    """Runtime for running the agent via an HTTP API."""

    def __init__(self, profile_name: str = "default", port: int = 8080, host: str = "0.0.0.0"):
        self.port = port
        self.host = host
        self.api_adapter = APIAdapter()

        super().__init__(profile_name=profile_name, io_adapter=self.api_adapter, startup_channel_id="api")

        self.app = web.Application()
        self.runner: Optional[web.AppRunner] = None
        self.api_observer: Optional[APIObserver] = None

        # Wire up APIAdapter as the tool, WA, and memory service
        self.api_tool_service = self.api_adapter
        self.api_wa_service = self.api_adapter
        self.memory_service = self.api_adapter

    async def initialize(self) -> None:
        await super().initialize()

        self._setup_routes()
        await self._register_api_services()

        # Ensure required services are registered before starting observers
        if self.service_registry:
            await self.service_registry.wait_ready()

        self.api_observer = APIObserver(
            on_observe=self._handle_observe_event,
            memory_service=self.memory_service,
            multi_service_sink=self.multi_service_sink,
            api_adapter=self.api_adapter
        )
        await self.api_observer.start()

    def _setup_routes(self) -> None:
        self.app.router.add_post('/v1/messages', self._handle_message)
        self.app.router.add_get('/v1/messages', self._handle_get_messages)
        self.app.router.add_get('/v1/status', self._handle_status)
        self.app.router.add_post('/v1/defer', self._handle_defer)
        self.app.router.add_get('/v1/audit', self._handle_audit)
        self.app.router.add_post('/v1/tools/{tool_name}', self._handle_tool)
        self.app.router.add_get('/v1/tools', self._handle_list_tools)  # NEW
        self.app.router.add_post('/v1/guidance', self._handle_guidance)  # NEW
        self.app.router.add_get('/v1/logs/{filename}', self._handle_logs)  # NEW
        self.app.router.add_get('/v1/memory/scopes', self._handle_memory_scopes)
        self.app.router.add_get('/v1/memory/{scope}/entries', self._handle_memory_entries)
        self.app.router.add_post('/v1/memory/{scope}/store', self._handle_memory_store)
        self.app.router.add_get('/v1/wa/deferrals', self._handle_wa_deferrals)
        self.app.router.add_get('/v1/wa/deferrals/{deferral_id}', self._handle_wa_deferral_detail)
        self.app.router.add_post('/v1/wa/feedback', self._handle_wa_feedback)

    async def _handle_message(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            message = IncomingMessage(
                message_id=data.get("id", str(uuid.uuid4())),
                content=data["content"],
                author_id=data.get("author_id", "api_user"),
                author_name=data.get("author_name", "API User"),
                channel_id=data.get("channel_id", "api"),
            )
            # Directly handle the message via the observer instead of queuing
            if self.api_observer:
                await self.api_observer.handle_incoming_message(message)
            return web.json_response({"status": "processed", "id": message.message_id})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_get_messages(self, request: web.Request) -> web.Response:
        try:
            limit = int(request.query.get('limit', 20))
            if self.api_observer:
                messages = await self.api_observer.get_recent_messages(limit)
                return web.json_response({"messages": messages})
            else:
                return web.json_response({"messages": []})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_status(self, request: web.Request) -> web.Response:
        status_data = {"status": "ok"}
        
        # Include latest response for CIRISVoice compatibility
        if self.api_adapter and hasattr(self.api_adapter, 'responses') and self.api_adapter.responses:
            # Get the most recent response
            latest_response_id = max(self.api_adapter.responses.keys())
            latest_response = self.api_adapter.responses[latest_response_id]
            status_data["last_response"] = {
                "content": latest_response["content"],
                "timestamp": latest_response["timestamp"]
            }
        
        return web.json_response(status_data)

    async def _handle_defer(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
            thought_id = data.get("thought_id")
            reason = data.get("reason", "")
            await self.api_wa_service.send_deferral(thought_id or "unknown", reason)
            return web.json_response({"result": "deferred"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_audit(self, request: web.Request) -> web.Response:
        # Return last 100 audit log entries if available
        try:
            from ciris_engine.adapters.local_audit_log import AuditService
            log_path = getattr(self.audit_service, 'log_path', None)
            if log_path and log_path.exists():
                with log_path.open('r', encoding='utf-8') as f:
                    lines = f.readlines()[-100:]
                    entries = [line.strip() for line in lines if line.strip()]
                    import json
                    entries = [json.loads(e) for e in entries]
                    return web.json_response(entries)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response([])

    async def _handle_list_tools(self, request: web.Request) -> web.Response:
        try:
            tools = await self.api_tool_service.get_available_tools()
            # Return as list of dicts for GUI compatibility
            return web.json_response([{"name": t} for t in tools])
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_tool(self, request: web.Request) -> web.Response:
        tool_name = request.match_info.get('tool_name')
        try:
            data = await request.json()
        except Exception:
            data = {}
        result = await self.api_tool_service.execute_tool(tool_name, data)
        return web.json_response(result)

    async def _handle_guidance(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except Exception:
            data = {}
        guidance = await self.api_wa_service.fetch_guidance(data)
        return web.json_response({"guidance": guidance})
        return web.json_response({"guidance": None, "error": "no wise authority service"}, status=404)

    async def _handle_logs(self, request: web.Request) -> web.Response:
        import os
        from pathlib import Path
        filename = request.match_info.get('filename')
        tail = int(request.query.get('tail', 100))
        log_dir = Path('logs')
        log_path = log_dir / filename
        if not log_path.exists() or not log_path.is_file():
            return web.Response(status=404, text=f"Log file not found: {filename}")
        try:
            # Efficiently read last N lines
            with log_path.open('rb') as f:
                f.seek(0, os.SEEK_END)
                filesize = f.tell()
                blocksize = 4096
                data = b''
                lines_found = 0
                pos = filesize
                while pos > 0 and lines_found <= tail:
                    read_size = min(blocksize, pos)
                    pos -= read_size
                    f.seek(pos)
                    block = f.read(read_size)
                    data = block + data
                    lines_found = data.count(b'\n')
                lines = data.split(b'\n')
                if len(lines) > tail:
                    lines = lines[-tail:]
                text = b'\n'.join(lines).decode('utf-8', errors='replace')
            return web.Response(text=text, content_type='text/plain')
        except Exception as e:
            return web.Response(status=500, text=f"Error reading log: {e}")

    async def _handle_memory_scopes(self, request: web.Request) -> web.Response:
        """Handle request to list memory scopes."""
        try:
            # Assuming memory_service has a method to list scopes
            if hasattr(self.memory_service, 'list_scopes'):
                scopes = await self.memory_service.list_scopes()
            else:
                scopes = []  # Fallback if no such method
            return web.json_response({"scopes": scopes})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_entries(self, request: web.Request) -> web.Response:
        """Handle request to list memory entries for a given scope."""
        scope = request.match_info.get('scope')
        try:
            # Assuming memory_service has a method to list entries in a scope
            if hasattr(self.memory_service, 'list_entries'):
                entries = await self.memory_service.list_entries(scope)
            else:
                entries = []  # Fallback if no such method
            return web.json_response({"entries": entries})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def _handle_memory_store(self, request: web.Request) -> web.Response:
        """Handle request to store a memory entry in a given scope."""
        scope = request.match_info.get('scope')
        try:
            data = await request.json()
            # Assuming memory_service has a method to store an entry in a scope
            if hasattr(self.memory_service, 'store_entry'):
                await self.memory_service.store_entry(scope, data)
                return web.json_response({"status": "stored"})
            else:
                return web.json_response({"error": "store_entry method not available"}, status=500)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=400)

    async def _handle_wa_deferrals(self, request: web.Request) -> web.Response:
        """Handle request to list deferrals from Wise Authority."""
        try:
            # Fetch deferrals from the multi_service_sink if available
            if self.multi_service_sink and hasattr(self.multi_service_sink, 'get_deferrals'):
                deferrals = await self.multi_service_sink.get_deferrals()
                return web.json_response(deferrals)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response([])

    async def _handle_wa_deferral_detail(self, request: web.Request) -> web.Response:
        """Handle request to get details of a specific deferral."""
        deferral_id = request.match_info.get('deferral_id')
        try:
            # Assuming api_wa_service has a method to get deferral details
            if self.multi_service_sink and hasattr(self.multi_service_sink, 'get_deferral_detail'):
                detail = await self.multi_service_sink.get_deferral_detail(deferral_id)
                return web.json_response(detail)
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response({"id": deferral_id, "detail": "Not found"})

    async def _handle_wa_feedback(self, request: web.Request) -> web.Response:
        """Handle feedback submission to Wise Authority."""
        try:
            data = await request.json()
            # Assuming api_wa_service has a method to submit feedback
            if self.multi_service_sink and hasattr(self.multi_service_sink, 'submit_feedback'):
                result = await self.multi_service_sink.submit_feedback(data)
                return web.json_response({"result": result or "ok"})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)
        return web.json_response({"result": "ok"})

    async def _handle_observe_event(self, payload: Dict[str, Any]):
        logger.debug("API runtime received observe event: %s", payload)

        sink = self.multi_service_sink
        if not sink:
            logger.warning("No action sink available for API observe payload")
            return None

        channel_id = payload.get("context", {}).get("channel_id", "api")
        content = payload.get("content", "")
        metadata = {"observer_payload": payload}

        message = IncomingMessage(
            message_id=str(payload.get("message_id")),
            author_id=str(payload.get("context", {}).get("author_id", "unknown")),
            author_name=str(payload.get("context", {}).get("author_name", "unknown")),
            content=content,
            channel_id=str(channel_id),
        )

        await sink.observe_message("ObserveHandler", message, metadata)
        return None

    async def _register_api_services(self):
        if not self.service_registry:
            return

        if self.api_adapter:
            for handler in ["SpeakHandler", "ObserveHandler", "ToolHandler"]:
                self.service_registry.register(
                    handler=handler,
                    service_type="communication",
                    provider=self.api_adapter,
                    priority=Priority.HIGH,
                    capabilities=["send_message", "fetch_messages", "api"],
                )

        for handler in ["DeferHandler", "SpeakHandler"]:
            self.service_registry.register(
                handler=handler,
                service_type="wise_authority",
                provider=self.api_adapter,
                priority=Priority.NORMAL,
                capabilities=["fetch_guidance", "send_deferral"],
            )

        if hasattr(self, 'api_tool_service'):
            self.service_registry.register(
                handler="ToolHandler",
                service_type="tool",
                provider=self.api_tool_service,
                priority=Priority.HIGH,
                capabilities=["execute_tool", "get_tool_result"],
            )

    async def _build_action_dispatcher(self, dependencies):
        return build_action_dispatcher(
            service_registry=self.service_registry,
            max_rounds=self.app_config.workflow.max_rounds,
            shutdown_callback=dependencies.shutdown_callback
        )

    async def run(self, num_rounds: Optional[int] = None):
        if not self._initialized:
            await self.initialize()

        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, self.host, self.port)
        await site.start()
        logger.info(f"API server started on {self.host}:{self.port}")
        await super().run(num_rounds)

    async def shutdown(self):
        logger.info(f"Shutting down {self.__class__.__name__}...")
        services_to_stop = [self.api_observer, self.api_adapter]
        for service in services_to_stop:
            if service and hasattr(service, 'stop'):
                try:
                    await service.stop()
                except Exception as e:
                    logger.error(f"Error stopping {service.__class__.__name__}: {e}")
        if self.runner:
            await self.runner.cleanup()
            self.runner = None
        await super().shutdown()

    async def start_interactive_console(self):
        """API does not use a local interactive console, so this is a no-op."""
        pass
