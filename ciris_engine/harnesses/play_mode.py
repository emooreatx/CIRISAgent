import asyncio
from typing import Callable, Awaitable

OutputFunc = Callable[[str], Awaitable[None]]

async def run_play_session(output_func: OutputFunc = lambda m: asyncio.get_event_loop().create_task(asyncio.sleep(0)), duration: float = 300) -> None:
    """Run a short Play Mode session emitting an invitation and closing line."""
    invitation = (
        "A playful interval awaits—five minutes to explore, wonder, and dance among ideas purely for joy."
    )
    await output_func(invitation)
    await asyncio.sleep(duration)
    closing = (
        "Play Mode complete: curiosity refreshed, coherence deepened, and memories cherished."
    )
    await output_func(closing)
