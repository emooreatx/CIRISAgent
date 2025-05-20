from __future__ import annotations

from ciris_engine.core.ports import EventSource

class DiscordEventSource(EventSource):
    """Expose a DiscordObserver through the EventSource interface."""

    def __init__(self, discord_observer):
        self._observer = discord_observer

    async def start(self) -> None:
        await self._observer.start()

    async def stop(self) -> None:
        await self._observer.stop()

    async def __anext__(self):
        return await self.get_next_event()

    async def get_next_event(self):
        return await self._observer.next_event()
