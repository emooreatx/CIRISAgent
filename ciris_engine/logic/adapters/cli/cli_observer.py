import asyncio
import logging
import sys
import select
from typing import Awaitable, Callable, Optional, Set, Any, List

from ciris_engine.schemas.runtime.messages import IncomingMessage
from ciris_engine.schemas.services.filters_core import FilterResult
from ciris_engine.logic.buses import BusManager
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.logic.adapters.base_observer import BaseObserver
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

PASSIVE_CONTEXT_LIMIT = 10

class CLIObserver(BaseObserver[IncomingMessage]):
    """
    Observer that converts CLI input events into observation payloads.
    Includes adaptive filtering for message prioritization.
    """

    def __init__(
        self,
        on_observe: Callable[[dict], Awaitable[None]],
        memory_service: Optional[Any] = None,
        agent_id: Optional[str] = None,
        bus_manager: Optional[BusManager] = None,
        filter_service: Optional[Any] = None,
        secrets_service: Optional[SecretsService] = None,
        time_service: Optional[TimeServiceProtocol] = None,
        *,
        interactive: bool = True,
        config: Optional[Any] = None,
    ) -> None:
        super().__init__(
            on_observe,
            bus_manager=bus_manager,
            memory_service=memory_service,
            agent_id=agent_id,
            filter_service=filter_service,
            secrets_service=secrets_service,
            time_service=time_service,
            origin_service="cli",
        )
        self.interactive = interactive
        self.config = config
        self._input_task: Optional[asyncio.Task] = None
        self._stop_event = asyncio.Event()
        self._buffered_input: List[str] = []
        self._input_ready = asyncio.Event()
        self._check_for_piped_input()

    def _check_for_piped_input(self) -> None:
        """Check if there's piped input available and buffer it."""
        try:
            # Check if stdin has data available (non-blocking)
            if sys.stdin.isatty():
                # Interactive terminal - no piped input
                logger.debug("CLI running in interactive mode")
                return

            # Non-interactive - check for piped input
            logger.info("Detected piped input, buffering...")

            # Read all available lines from stdin
            while True:
                # Use select to check if data is available with a short timeout
                ready, _, _ = select.select([sys.stdin], [], [], 0.1)
                if ready:
                    line = sys.stdin.readline()
                    if line:
                        line = line.rstrip('\n')
                        if line:  # Ignore empty lines
                            self._buffered_input.append(line)
                            logger.debug(f"Buffered input: {line}")
                    else:
                        # EOF reached
                        break
                else:
                    # No more data available
                    break

            if self._buffered_input:
                logger.info(f"Buffered {len(self._buffered_input)} input lines")
                # If we have buffered input, we're not interactive
                self.interactive = False

        except Exception as e:
            logger.warning(f"Error checking for piped input: {e}")

    async def start(self) -> None:
        """Start the observer and optional input loop."""
        logger.info("CLIObserver started")

        # Process any buffered input first
        if self._buffered_input:
            logger.info(f"Processing {len(self._buffered_input)} buffered input lines")
            asyncio.create_task(self._process_buffered_input())

        # Start interactive input loop if needed
        if self.interactive and self._input_task is None:
            self._input_task = asyncio.create_task(self._input_loop())

    async def _process_buffered_input(self) -> None:
        """Process buffered input lines with a delay to ensure system is ready."""
        # Wait longer to ensure the system completes wakeup and is in WORK state
        logger.info("Waiting for system to be ready...")
        await asyncio.sleep(5.0)

        for line in self._buffered_input:
            logger.info(f"Processing buffered input: {line}")

            # Get channel ID from config or default to "cli"
            channel_id = "cli"
            if self.config and hasattr(self.config, 'get_home_channel_id'):
                channel_id = self.config.get_home_channel_id()

            msg = IncomingMessage(
                message_id=f"cli_buffered_{asyncio.get_event_loop().time()}",
                content=line,
                author_id="local_user",
                author_name="User",
                channel_id=channel_id,
            )

            await self.handle_incoming_message(msg)

            # Small delay between messages to avoid overwhelming the system
            await asyncio.sleep(0.5)

        logger.info("Finished processing buffered input")

        # If not interactive, signal stop after processing
        if not self.interactive:
            logger.info("Non-interactive mode, signaling stop")
            self._stop_event.set()

    async def stop(self) -> None:
        """Stop the observer and background input loop."""
        if self._input_task:
            self._stop_event.set()
            try:
                await asyncio.wait_for(self._input_task, timeout=1.0)
            except asyncio.TimeoutError:
                logger.warning("Input task did not complete within timeout, cancelling")
                self._input_task.cancel()
                try:
                    await self._input_task
                except asyncio.CancelledError:
                    pass
            self._input_task = None
            self._stop_event.clear()
        logger.info("CLIObserver stopped")

    async def _input_loop(self) -> None:
        """Read lines from stdin and handle them as messages."""
        try:
            while not self._stop_event.is_set():
                try:
                    line = await asyncio.to_thread(input, ">>> ")
                except (EOFError, KeyboardInterrupt):
                    logger.info("Input terminated (EOF or interrupt), stopping input loop")
                    self._stop_event.set()
                    break
                except asyncio.CancelledError:
                    logger.debug("Input loop cancelled")
                    break

                if not line:
                    continue
                if line.lower() in {"exit", "quit", "bye"}:
                    self._stop_event.set()
                    break

                # Get channel ID from config or default to "cli"
                channel_id = "cli"
                if self.config and hasattr(self.config, 'get_home_channel_id'):
                    channel_id = self.config.get_home_channel_id()

                msg = IncomingMessage(
                    message_id=f"cli_{asyncio.get_event_loop().time()}",
                    content=line,
                    author_id="local_user",
                    author_name="User",
                    channel_id=channel_id,
                )
                await self.handle_incoming_message(msg)
        except (EOFError, KeyboardInterrupt):
            logger.info("Input loop terminated (EOF or interrupt)")
            self._stop_event.set()
        except asyncio.CancelledError:
            logger.debug("Input loop task cancelled")
            raise

    async def _get_recall_ids(self, msg: IncomingMessage) -> Set[str]:
        import socket
        return {f"channel/{socket.gethostname()}"}

    def _is_cli_channel(self, channel_id: Optional[str]) -> bool:
        """Check if a channel ID belongs to this CLI observer instance."""
        if not channel_id:
            return False

        if channel_id == "cli":
            return True

        # Check if it starts with "cli_" (buffered input format)
        if channel_id.startswith("cli_"):
            return True

        if self.config and hasattr(self.config, 'get_home_channel_id'):
            config_channel = self.config.get_home_channel_id()
            if config_channel and channel_id == config_channel:
                return True

        import socket
        hostname_channel = socket.gethostname()
        if channel_id == hostname_channel or channel_id == f"channel/{hostname_channel}":
            return True

        import getpass
        user_hostname = f"{getpass.getuser()}@{socket.gethostname()}"
        if channel_id == user_hostname:
            return True

        return False

    async def handle_incoming_message(self, msg: IncomingMessage) -> None:
        if not isinstance(msg, IncomingMessage):
            logger.warning("CLIObserver received non-IncomingMessage")  # type: ignore[unreachable]
            return

        is_agent_message = self.agent_id and msg.author_id == self.agent_id

        processed_msg = await self._process_message_secrets(msg)

        self._history.append(processed_msg)

        if is_agent_message:
            logger.debug("Added agent's own message %s to history (no task created)", msg.message_id)
            return

        filter_result = await self._apply_message_filtering(msg, "cli")
        if not filter_result.should_process:
            logger.debug(f"Message {msg.message_id} filtered out: {filter_result.reasoning}")
            return

        processed_msg._filter_priority = filter_result.priority  # type: ignore[attr-defined]
        processed_msg._filter_context = filter_result.context_hints  # type: ignore[attr-defined]
        processed_msg._filter_reasoning = filter_result.reasoning  # type: ignore[attr-defined]

        if filter_result.priority.value in ['critical', 'high']:
            logger.info(f"Processing {filter_result.priority.value} priority message {msg.message_id}: {filter_result.reasoning}")
            await self._handle_priority_observation(processed_msg, filter_result)
        else:
            await self._handle_passive_observation(processed_msg)

        await self._recall_context(processed_msg)

    async def _handle_priority_observation(self, msg: IncomingMessage, filter_result: FilterResult) -> None:
        """Handle high-priority messages with immediate processing"""
        # The CLI observer should handle any CLI-related channel, not just "cli"
        # This could be "cli", "user@hostname", or any channel ID this CLI instance is responsible for

        if self._is_cli_channel(msg.channel_id) and not self._is_agent_message(msg):
            # Create high-priority observation with enhanced context
            await self._create_priority_observation_result(msg, filter_result)
        else:
            logger.debug("Ignoring priority message from channel %s, author %s for CLI observer", msg.channel_id, msg.author_name)

    async def _handle_passive_observation(self, msg: IncomingMessage) -> None:
        """Handle passive observation routing based on channel ID and author filtering"""

        if self._is_cli_channel(msg.channel_id) and not self._is_agent_message(msg):
            await self._create_passive_observation_result(msg)
        else:
            logger.debug("Ignoring passive message from channel %s, author %s for CLI observer", msg.channel_id, msg.author_name)
