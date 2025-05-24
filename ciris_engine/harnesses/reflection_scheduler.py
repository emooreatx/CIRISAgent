import asyncio
import random
from typing import Callable, Awaitable, Optional

from .play_mode import run_play_session
from .solitude_mode import run_solitude_session
from ciris_engine.services.event_log_service import EventLogService

OutputFunc = Callable[[str], Awaitable[None]]

async def schedule_reflection_modes(output_func: OutputFunc, interval: float = 3600, iterations: Optional[int] = None) -> None:
    """Periodically trigger Play or Solitude Mode sessions."""
    count = 0
    while iterations is None or count < iterations:
        await asyncio.sleep(interval)
        mode = random.choice(["play", "solitude"])
        if mode == "play":
            await run_play_session(output_func)
        else:
            await run_solitude_session(output_func)
        count += 1


async def schedule_event_log_rotation(service: EventLogService, interval: float = 3600) -> None:
    """Periodically rotate the event log."""
    while True:
        await asyncio.sleep(interval)
        await service.rotate()
