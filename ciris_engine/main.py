import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

load_dotenv()

from .utils.logging_config import setup_basic_logging
from .config.config_manager import load_config_from_file_async, AppConfig
from .runtime.ciris_runtime import CIRISRuntime
from .runtime.discord_runtime import DiscordRuntime
from .runtime.cli_runtime import CLIRuntime
from .runtime.api.api_runtime_entrypoint import APIRuntimeEntrypoint

APIRuntime = APIRuntimeEntrypoint
from ciris_engine.adapters.api import APIAdapter, APIObserver
from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
from ciris_engine.adapters.local_audit_log import AuditService


def create_runtime(
    mode: str,
    profile: str,
    config: AppConfig,
    *,
    interactive: bool = True,
    host: str = "0.0.0.0",
    port: int = 8080,
) -> CIRISRuntime:
    """Factory to create a runtime based on the mode."""
    # Set the agent_mode in the config so context propagation works
    config.agent_mode = mode
    
    if mode == "discord":
        from ciris_engine.config.env_utils import get_env_var

        token = get_env_var("DISCORD_BOT_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_BOT_TOKEN must be set for Discord mode")
        return DiscordRuntime(
            token=token,
            profile_name=profile,
            startup_channel_id=config.discord_channel_id,
            app_config=config,
        )
    if mode == "cli":
        return CLIRuntime(profile_name=profile, interactive=interactive, app_config=config)
    if mode == "api":
        # The APIRuntime entrypoint will handle all service creation and registration
        return APIRuntime(
            service_registry=None,  # Let APIRuntimeEntrypoint create it
            multi_service_sink=None,  # Let APIRuntimeEntrypoint create it
            audit_service=None,  # Let APIRuntimeEntrypoint create it
            api_observer=None,  # Let APIRuntimeEntrypoint create it
            api_adapter=None,  # Let APIRuntimeEntrypoint create it
            host=host,
            port=port,
            profile_name=profile,
            app_config=config,
        )
    raise ValueError(f"Unsupported mode: {mode}")





async def run_with_shutdown_handler(runtime: CIRISRuntime) -> None:
    """Run the runtime and handle shutdown signals gracefully."""
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _stop() -> None:
        stop_event.set()

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, _stop)
        except NotImplementedError:
            pass

    run_task = asyncio.create_task(runtime.run())
    await stop_event.wait()
    
    # Signal shutdown via the runtime's method instead of cancelling
    runtime.request_shutdown("Interrupt signal received")
    
    # Wait for the task to complete naturally
    try:
        await run_task
    except asyncio.CancelledError:
        pass


async def load_config(config_path: Optional[str]) -> AppConfig:
    """Load application configuration from a path."""
    return await load_config_from_file_async(Path(config_path) if config_path else None)


async def async_main(
    mode: str,
    profile: str,
    config: Optional[str],
    host: str,
    port: int,
    no_interactive: bool,
    debug: bool,
) -> None:
    """Unified CIRIS Engine entry point async implementation."""
    app_config = await load_config(config)
    runtime = create_runtime(
        mode,
        profile,
        app_config,
        interactive=not no_interactive,
        host=host,
        port=port,
    )
    await run_with_shutdown_handler(runtime)


@click.command()
@click.option("--mode", type=click.Choice(["discord", "cli", "api"]), default="discord")
@click.option("--profile", default="default")
@click.option("--config", type=click.Path(exists=True))
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", default=8080, type=int, help="API port")
@click.option("--no-interactive/--interactive", default=False, help="Disable interactive CLI input")
@click.option("--debug/--no-debug", default=False)
def main(
    mode: str,
    profile: str,
    config: Optional[str],
    host: str,
    port: int,
    no_interactive: bool,
    debug: bool,
) -> Optional[asyncio.Task]:
    """Unified CIRIS Engine entry point.

    When invoked in an environment with an active event loop, the async
    implementation is scheduled as a task and returned so callers can await it
    (useful for tests). Otherwise the coroutine is executed via
    :func:`asyncio.run` for CLI usage.
    """

    coro = async_main(
        mode=mode,
        profile=profile,
        config=config,
        host=host,
        port=port,
        no_interactive=no_interactive,
        debug=debug,
    )

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        asyncio.run(coro)
        return None
    else:
        return loop.create_task(coro)


if __name__ == "__main__":
    main()

