"""API log streaming endpoints for CIRISAgent."""
import logging
from aiohttp import web
from pathlib import Path
import os
from typing import Any

logger = logging.getLogger(__name__)

class APILogsRoutes:
    def __init__(self, bus_manager: Any = None) -> None:
        self.bus_manager = bus_manager
        
    def register(self, app: web.Application) -> None:
        app.router.add_get('/v1/logs/{filename}', self._handle_logs)

    async def _handle_logs(self, request: web.Request) -> web.Response:
        filename = request.match_info.get('filename', '')
        tail = int(request.query.get('tail', 100))
        log_dir = Path('logs')
        log_path = log_dir / filename
        if not log_path.exists() or not log_path.is_file():
            return web.Response(status=404, text=f"Log file not found: {filename}")
        try:
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
            logger.error(f"Error reading log file {filename}: {e}")
            return web.Response(status=500, text=f"Error reading log: {e}")
