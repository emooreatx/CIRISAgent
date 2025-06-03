import asyncio
import contextlib
import logging
import os
import signal
from pathlib import Path
from typing import Optional

import click
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from .utils.logging_config import setup_basic_logging
from .config.config_manager import load_config_from_file_async, AppConfig
from .runtime.ciris_runtime import CIRISRuntime
from .runtime.discord_runtime import DiscordRuntime
from .runtime.cli_runtime import CLIRuntime
from .runtime.api.api_runtime_entrypoint import APIRuntimeEntrypoint
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
    if mode == "discord":
        from ciris_engine.config.env_utils import get_env_var

        token = get_env_var("DISCORD_BOT_TOKEN")
        if not token:
            raise RuntimeError("DISCORD_BOT_TOKEN must be set for Discord mode")
        return DiscordRuntime(
            token=token,
            profile_name=profile,
            startup_channel_id=config.discord_channel_id,
        )
    if mode == "cli":
        return CLIRuntime(profile_name=profile, interactive=interactive)
    if mode == "api":
        # Build all dependencies for the API runtime entrypoint
        api_adapter = APIAdapter()
        audit_service = AuditService()
        # Service registry and sink setup
        from ciris_engine.registries.base import ServiceRegistry

        service_registry = ServiceRegistry()
        multi_service_sink = MultiServiceActionSink(service_registry=service_registry)
        # Observer setup
        api_observer = APIObserver(
            on_observe=None,  # Set up as needed
            memory_service=api_adapter,  # Or use a real memory service if desired
            multi_service_sink=multi_service_sink,
            api_adapter=api_adapter,
        )
        # Register services as needed (mimic what the old APIRuntime did)
        # ...register communication/tool/wa/memory services here if needed...
        return APIRuntimeEntrypoint(
            multi_service_sink=multi_service_sink,
            audit_service=audit_service,
            api_observer=api_observer,
            api_adapter=api_adapter,
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
    run_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await run_task


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
    # Note: Logging setup is handled by the root main.py entry point
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
) -> None:
    """Unified CIRIS Engine entry point."""
    asyncio.run(async_main(
        mode=mode,
        profile=profile,
        config=config,
        host=host,
        port=port,
        no_interactive=no_interactive,
        debug=debug,
    ))


if __name__ == "__main__":
    main()

