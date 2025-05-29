import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Dict

logger = logging.getLogger(__name__)


class EventLogService:
    """Simple JSONL event logger with basic log rotation."""

    def __init__(self, log_path: str = "guardrail_events.jsonl", max_bytes: int = 1024 * 1024, backups: int = 3) -> None:
        self.log_path = Path(log_path)
        self.max_bytes = max_bytes
        self.backups = backups

    async def start(self) -> None:
        await asyncio.to_thread(self.log_path.touch, exist_ok=True)

    async def stop(self) -> None:
        pass

    async def log_event(self, event: Dict[str, Any]) -> None:
        line = json.dumps(event)
        await asyncio.to_thread(self._append_line, line)

    def _append_line(self, line: str) -> None:
        with self.log_path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    async def rotate(self) -> None:
        if not self.log_path.exists() or self.log_path.stat().st_size <= self.max_bytes:
            return
        for i in range(self.backups, 0, -1):
            old = self.log_path.with_name(f"{self.log_path.stem}.{i}{self.log_path.suffix}")
            if old.exists():
                if i == self.backups:
                    old.unlink()
                else:
                    newer = self.log_path.with_name(f"{self.log_path.stem}.{i+1}{self.log_path.suffix}")
                    old.rename(newer)
        rotated = self.log_path.with_name(f"{self.log_path.stem}.1{self.log_path.suffix}")
        self.log_path.rename(rotated)
        await asyncio.to_thread(rotated.touch, exist_ok=True)
        await asyncio.to_thread(self.log_path.touch, exist_ok=True)
