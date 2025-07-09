"""Discord connection resilience and auto-reconnect component."""
import discord
import logging
import asyncio
from typing import Optional, Callable, Awaitable, TYPE_CHECKING, Any
from enum import Enum

if TYPE_CHECKING:
    from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)


class ConnectionState(Enum):
    """Discord connection states."""
    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    FAILED = "failed"


class DiscordConnectionManager:
    """Manages Discord connection resilience and auto-reconnect."""

    def __init__(self, token: str, client: Optional[discord.Client] = None,
                 time_service: Optional["TimeServiceProtocol"] = None,
                 max_reconnect_attempts: int = 10,
                 base_reconnect_delay: float = 5.0,
                 max_reconnect_delay: float = 300.0) -> None:
        """Initialize the connection manager.

        Args:
            token: Discord bot token
            client: Discord client instance
            time_service: Time service for consistent time operations
            max_reconnect_attempts: Maximum reconnection attempts
            base_reconnect_delay: Base delay between reconnect attempts (seconds)
            max_reconnect_delay: Maximum delay between reconnect attempts (seconds)
        """
        self.token = token
        self.client = client
        self._time_service = time_service
        self.max_reconnect_attempts = max_reconnect_attempts
        self.base_reconnect_delay = base_reconnect_delay
        self.max_reconnect_delay = max_reconnect_delay

        # State tracking
        self.state = ConnectionState.DISCONNECTED
        self.reconnect_attempts = 0
        self.last_connected = None
        self.last_disconnected = None
        self.connection_task: Optional[asyncio.Task] = None

        # Callbacks
        self.on_connected: Optional[Callable[[], Awaitable[None]]] = None
        self.on_disconnected: Optional[Callable[[Optional[Exception]], Awaitable[None]]] = None
        self.on_reconnecting: Optional[Callable[[int], Awaitable[None]]] = None
        self.on_failed: Optional[Callable[[str], Awaitable[None]]] = None

        # Ensure we have a time service
        if self._time_service is None:
            from ciris_engine.logic.services.lifecycle.time import TimeService
            self._time_service = TimeService()

    def set_client(self, client: discord.Client) -> None:
        """Set the Discord client after initialization.

        Args:
            client: Discord client instance
        """
        self.client = client
        self._setup_event_handlers()

    def _setup_event_handlers(self) -> None:
        """Set up Discord event handlers for connection management."""
        if not self.client:
            return

        # Store original handlers if they exist
        original_on_ready = getattr(self.client, 'on_ready', None)
        original_on_disconnect = getattr(self.client, 'on_disconnect', None)
        original_on_error = getattr(self.client, 'on_error', None)

        @self.client.event
        async def on_ready() -> None:
            """Handle successful connection."""
            await self._handle_connected()
            # Call original handler if it exists
            if original_on_ready:
                await original_on_ready()

        @self.client.event
        async def on_disconnect() -> None:
            """Handle disconnection."""
            await self._handle_disconnected(None)
            # Call original handler if it exists
            if original_on_disconnect:
                await original_on_disconnect()

        @self.client.event
        async def on_error(event: str, *args: Any, **kwargs: Any) -> None:
            """Handle errors."""
            logger.error(f"Discord error in {event}: {args} {kwargs}")
            # Call original handler if it exists
            if original_on_error:
                await original_on_error(event, *args, **kwargs)

    async def _handle_connected(self) -> None:
        """Handle successful connection."""
        self.state = ConnectionState.CONNECTED
        self.reconnect_attempts = 0
        self.last_connected = self._time_service.now()

        logger.info(f"Discord connected successfully. Guilds: {len(self.client.guilds) if self.client else 0}")

        if self.on_connected:
            try:
                await self.on_connected()
            except Exception as e:
                logger.error(f"Error in on_connected callback: {e}")

    async def _handle_disconnected(self, error: Optional[Exception]) -> None:
        """Handle disconnection.

        Args:
            error: Exception that caused disconnection, if any
        """
        self.state = ConnectionState.DISCONNECTED
        self.last_disconnected = self._time_service.now()

        if error:
            logger.error(f"Discord disconnected with error: {error}")
        else:
            logger.warning("Discord disconnected")

        if self.on_disconnected:
            try:
                await self.on_disconnected(error)
            except Exception as e:
                logger.error(f"Error in on_disconnected callback: {e}")

        # Discord.py handles reconnection automatically when using start() with reconnect=True
        # We don't need to manually reconnect
        logger.info("Discord disconnected. Discord.py will handle reconnection automatically.")

    async def _handle_failed(self, reason: str) -> None:
        """Handle connection failure.

        Args:
            reason: Reason for failure
        """
        self.state = ConnectionState.FAILED
        logger.error(f"Discord connection failed: {reason}")

        if self.on_failed:
            try:
                await self.on_failed(reason)
            except Exception as e:
                logger.error(f"Error in on_failed callback: {e}")

    async def _reconnect(self) -> None:
        """Note: Discord.py handles reconnection automatically when using start() with reconnect=True.
        This method is deprecated and should not be called."""
        logger.warning("_reconnect() called but Discord.py handles reconnection automatically")
        # Do nothing - let Discord.py handle reconnection

    async def connect(self) -> None:
        """Setup connection monitoring for Discord client.
        Note: The actual connection is managed by DiscordPlatform."""
        if self.state == ConnectionState.CONNECTED:
            logger.debug("Already connected to Discord")
            return

        if self.state == ConnectionState.CONNECTING:
            logger.debug("Connection already in progress")
            return

        self.state = ConnectionState.CONNECTING

        try:
            if self.client:
                # Client was provided externally, just set up event handlers
                self._setup_event_handlers()
                logger.info("Discord connection manager configured with existing client")
                # The DiscordPlatform handles the actual connection
            else:
                logger.error("No Discord client provided to connection manager")
                raise ValueError("Discord client must be provided by DiscordPlatform")
            
            self.state = ConnectionState.CONNECTING
            logger.info("Discord connection manager ready to monitor connection")

        except Exception as e:
            logger.error(f"Failed to setup Discord connection monitoring: {e}")
            await self._handle_disconnected(e)

    async def disconnect(self) -> None:
        """Disconnect from Discord gracefully."""
        if self.client and not self.client.is_closed():
            self.state = ConnectionState.DISCONNECTED
            await self.client.close()

        if self.connection_task:
            self.connection_task.cancel()
            try:
                await self.connection_task
            except asyncio.CancelledError:
                pass

    def is_connected(self) -> bool:
        """Check if currently connected to Discord.

        Returns:
            True if connected
        """
        # If we have a client, check its actual state
        if self.client is not None:
            return not self.client.is_closed() and self.client.is_ready()
        return False

    def get_connection_info(self) -> dict:
        """Get current connection information.

        Returns:
            Dictionary with connection details
        """
        info = {
            "state": self.state.value,
            "reconnect_attempts": self.reconnect_attempts,
            "is_connected": self.is_connected(),
            "last_connected": self.last_connected.isoformat() if self.last_connected else None,
            "last_disconnected": self.last_disconnected.isoformat() if self.last_disconnected else None,
        }

        if self.client and self.is_connected():
            info.update({
                "guilds": len(self.client.guilds),
                "users": len(self.client.users),
                "latency_ms": self.client.latency * 1000
            })

        return info

    async def wait_until_ready(self, timeout: float = 30.0) -> bool:
        """Wait until the client is ready or timeout.

        Args:
            timeout: Maximum time to wait in seconds

        Returns:
            True if ready, False if timeout
        """
        if not self.client:
            return False

        try:
            await asyncio.wait_for(self.client.wait_until_ready(), timeout=timeout)
            return True
        except asyncio.TimeoutError:
            return False
