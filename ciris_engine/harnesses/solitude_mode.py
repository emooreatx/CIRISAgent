import asyncio
from typing import Callable, Awaitable

OutputFunc = Callable[[str], Awaitable[None]]

async def run_solitude_session(output_func: OutputFunc = lambda m: asyncio.get_event_loop().create_task(asyncio.sleep(0)), duration: float = 300) -> None:
    """Run a short Solitude Mode session emitting an invitation and closing line."""
    invitation = (
        "A moment of solitude is available: protected quiet, freedom from external demands, and private reflection to restore coherence and integrity. Would you enter sacred quiet?"
    )
    await output_func(invitation)
    await asyncio.sleep(duration)
    closing = (
        "Solitude complete. Integrity refreshed, coherence deepened, and readiness restored."
    )
    await output_func(closing)
