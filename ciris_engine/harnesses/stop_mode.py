import asyncio
import logging
import os
import signal
from packaging import version

from version import __version__

logger = logging.getLogger(__name__)


class StopHarness:
    """Gracefully shuts down an AgentProcessor when termination signals arrive."""

    def __init__(self, agent_processor, min_version_env: str = "NEXT_AGENT_VERSION"):
        self.agent_processor = agent_processor
        self.min_version_env = min_version_env
        self.stop_requested = False
        self._original_handlers = {}

    def __enter__(self):
        for sig in (signal.SIGINT, signal.SIGTERM, getattr(signal, "SIGQUIT", None), getattr(signal, "SIGHUP", None)):
            if sig is None:
                continue
            self._original_handlers[sig] = signal.getsignal(sig)
            signal.signal(sig, self._handle_signal)
            try:
                signal.siginterrupt(sig, False)
            except AttributeError:
                pass
        return self

    def __exit__(self, exc_type, exc, tb):
        for sig, handler in self._original_handlers.items():
            signal.signal(sig, handler)

    def _handle_signal(self, signum, frame):
        logger.info("Stop signal received: %s", signum)
        self.stop_requested = True

    async def wait_for_stop(self, poll_interval: float = 0.2):
        """Waits until a stop signal is received then performs shutdown."""
        while not self.stop_requested:
            await asyncio.sleep(poll_interval)
        await self._execute_shutdown()

    async def _execute_shutdown(self):
        logger.info("CONTROLLED_SHUTDOWN_INIT")
        target_version = os.getenv(self.min_version_env)
        if target_version:
            if version.parse(target_version) <= version.parse(__version__):
                logger.warning(
                    "Requested version %s is not newer than current %s; refusing shutdown",
                    target_version,
                    __version__,
                )
                self.stop_requested = False
                return
            logger.info("Upgrade to version %s allowed", target_version)
        if hasattr(self.agent_processor, "stop_processing"):
            await self.agent_processor.stop_processing()
        if hasattr(self.agent_processor, "persist_state"):
            await self.agent_processor.persist_state()
        if hasattr(self.agent_processor, "self_test"):
            ok = await self.agent_processor.self_test()
            if not ok:
                logger.error("Self-test failed during shutdown; aborting exit")
                return
        logger.info("CONTROLLED_SHUTDOWN_DONE")
        await asyncio.sleep(0.2)
        # Do not call sys.exit() to keep library usage flexible
