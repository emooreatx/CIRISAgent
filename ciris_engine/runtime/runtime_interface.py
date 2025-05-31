from typing import Protocol, Optional, runtime_checkable

@runtime_checkable
class RuntimeInterface(Protocol):
    """Protocol for CIRIS runtimes."""

    async def initialize(self) -> None:
        """Initialize runtime and all services."""
        ...

    async def run(self, max_rounds: Optional[int] = None) -> None:
        """Run the agent processing loop."""
        ...

    async def shutdown(self) -> None:
        """Gracefully shutdown all services."""
        ...
