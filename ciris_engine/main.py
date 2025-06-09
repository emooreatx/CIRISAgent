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
# Old runtime imports removed
from typing import Tuple # Ensure Tuple is imported

# APIRuntime, APIAdapter, APIObserver, MultiServiceActionSink, AuditService imports might be unused now or handled differently.
# For now, let's keep them commented out or remove if truly unused after refactor.
# from ciris_engine.adapters.api import APIAdapter, APIObserver
# from ciris_engine.sinks.multi_service_sink import MultiServiceActionSink
# from ciris_engine.adapters.local_audit_log import AuditService # Assuming AuditService is now part of core services or adapters


# create_runtime function is removed


async def run_with_shutdown_handler(runtime: CIRISRuntime, num_rounds: Optional[int] = None) -> None:
    """Run the runtime and handle shutdown signals gracefully."""
    # Simplified shutdown handling, CIRISRuntime now manages internal shutdown logic
    # and signal handling is often managed by the environment or a higher-level orchestrator.
    # However, for standalone CLI execution, basic signal handling is still useful.
    loop = asyncio.get_running_loop()
    shutdown_requested_event = asyncio.Event()

    def signal_handler() -> None:
        if not shutdown_requested_event.is_set():
            logging.info("Shutdown signal received. Requesting runtime shutdown...")
            runtime.request_shutdown("Signal received by main.py handler")
            shutdown_requested_event.set() # Prevent multiple calls to request_shutdown from signals
        else:
            logging.info("Shutdown already in progress.")

    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, signal_handler)
        except NotImplementedError:
            # Some environments (like Windows default loop) might not support add_signal_handler
            logging.warning(f"Signal handler for {sig} could not be set. Manual shutdown might be required.")
            pass # Continue without signal handlers if not supported

    try:
        await runtime.run(num_rounds=num_rounds)
    except Exception as e:
        logging.critical(f"Runtime execution failed: {e}", exc_info=True)
        # Ensure shutdown is requested if a top-level error occurs in runtime.run() itself
        if not runtime._shutdown_event.is_set(): # Accessing protected member for check
             runtime.request_shutdown(f"Runtime error: {e}")
        await runtime.shutdown() # Attempt graceful shutdown
    finally:
        logging.info("Runtime execution finished or was interrupted.")
        # Ensure signal handlers are removed to avoid issues if the loop is reused
        for sig in (signal.SIGINT, signal.SIGTERM):
            try:
                loop.remove_signal_handler(sig)
            except (NotImplementedError, ValueError): # ValueError if not set
                pass


async def load_config(config_path: Optional[str]) -> AppConfig:
    """Load application configuration from a path."""
    return await load_config_from_file_async(Path(config_path) if config_path else None)


async def async_main(
    modes_list: Tuple[str, ...], # Changed from mode: str
    profile: str,
    config_file_path: Optional[str], # Changed from config: Optional[str]
    host: str, # Was api_host in original plan, aligning to param name
    port: int, # Was api_port in original plan, aligning to param name
    no_interactive: bool, # Was cli_interactive (inverted) in original plan
    debug: bool,
    discord_bot_token: Optional[str], # New parameter
) -> None:
    """Unified CIRIS Engine entry point async implementation."""
    setup_basic_logging(level=logging.DEBUG if debug else logging.INFO)

    app_config = await load_config(config_file_path) # Use renamed var

    adapter_specific_kwargs = {
        "host": host, # For API adapter
        "port": port, # For API adapter
        "interactive": not no_interactive, # For CLI adapter
        "discord_bot_token": discord_bot_token, # For Discord adapter
        "discord_monitored_channel_id": os.environ.get("DISCORD_CHANNEL_ID"), # For Discord adapter monitoring
        # Add other adapter-specific configs here as needed
    }

    runtime = CIRISRuntime(
        modes=list(modes_list), # Pass the list of modes
        profile_name=profile,
        app_config=app_config,
        startup_channel_id=getattr(app_config, 'startup_channel_id', 'default_startup'),
        **adapter_specific_kwargs
    )
    # num_rounds can be passed here if it becomes a parameter of async_main or main
    await run_with_shutdown_handler(runtime)


@click.command()
@click.option("--modes", "modes_list", multiple=True, required=True, help="One or more adapter modes to run (e.g., cli, api, discord).")
@click.option("--profile", default="default", help="Agent profile to use.")
@click.option("--config", "config_file_path", type=click.Path(exists=True, dir_okay=False), help="Path to the application configuration YAML file.")
@click.option("--host", "api_host", default=os.environ.get("API_HOST", "0.0.0.0"), show_default=True, help="Host for the API adapter.")
@click.option("--port", "api_port", default=int(os.environ.get("API_PORT", 8080)), show_default=True, type=int, help="Port for the API adapter.")
@click.option("--no-interactive/--interactive", "cli_interactive", default=True, show_default=True, help="Enable/disable interactive mode for CLI adapter.")
@click.option("--discord-token", "discord_bot_token", default=os.environ.get("DISCORD_BOT_TOKEN"), help="Discord bot token. Can also be set via DISCORD_BOT_TOKEN env var.")
@click.option("--debug/--no-debug", default=False, show_default=True, help="Enable debug logging.")
def main(
    modes_list: Tuple[str, ...],
    profile: str,
    config_file_path: Optional[str],
    api_host: str,
    api_port: int,
    cli_interactive: bool,
    discord_bot_token: Optional[str],
    debug: bool,
) -> Optional[asyncio.Task]:
    """Unified CIRIS Engine entry point.

    When invoked in an environment with an active event loop, the async
    implementation is scheduled as a task and returned so callers can await it
    (useful for tests). Otherwise the coroutine is executed via
    :func:`asyncio.run` for CLI usage.
    """
    actual_no_interactive = not cli_interactive

    coro = async_main(
        modes_list=modes_list,
        profile=profile,
        config_file_path=config_file_path,
        host=api_host,
        port=api_port,
        no_interactive=actual_no_interactive,
        debug=debug,
        discord_bot_token=discord_bot_token,
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

