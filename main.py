# Load environment variables from .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv is optional; skip if not installed
import os

import asyncio
import json
import logging
import signal
import sys
import uuid
from datetime import datetime, timezone
from typing import Optional, List

import click

from ciris_engine.utils.runtime_utils import load_config, run_with_shutdown_handler
from ciris_engine.runtime.ciris_runtime import CIRISRuntime
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.processor.task_manager import TaskManager
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus

logger = logging.getLogger(__name__)


def setup_signal_handlers(runtime: CIRISRuntime) -> None:
    """Setup signal handlers for graceful shutdown."""
    shutdown_initiated = {"value": False}  # Use dict to allow modification in nested function
    
    def signal_handler(signum, frame):
        if shutdown_initiated["value"]:
            logger.warning(f"Signal {signum} received again, forcing immediate exit")
            sys.exit(1)
        
        shutdown_initiated["value"] = True
        logger.info(f"Received signal {signum}, requesting graceful shutdown...")
        
        try:
            runtime.request_shutdown(f"Signal {signum}")
        except Exception as e:
            logger.error(f"Error during shutdown request: {e}")
            sys.exit(1)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)


def setup_global_exception_handler() -> None:
    """Setup global exception handler to catch all uncaught exceptions."""
    def handle_exception(exc_type, exc_value, exc_traceback):
        if issubclass(exc_type, KeyboardInterrupt):
            # Let KeyboardInterrupt be handled by signal handlers
            sys.__excepthook__(exc_type, exc_value, exc_traceback)
            return
        
        logger.error("UNCAUGHT EXCEPTION:", exc_info=(exc_type, exc_value, exc_traceback))
        logger.error("This should never happen - please report this bug!")

    sys.excepthook = handle_exception


def _create_thought() -> Thought:
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="standard",
        status=ThoughtStatus.PENDING,
        created_at=now,
        updated_at=now,
        content="manual invocation",
        context={},
    )


async def _execute_handler(runtime: CIRISRuntime, handler: str, params: Optional[str]) -> None:
    handler_type = HandlerActionType[handler.upper()]
    dispatcher = runtime.agent_processor.action_dispatcher
    handler_instance = dispatcher.handlers.get(handler_type)
    if not handler_instance:
        raise ValueError(f"Handler {handler} not registered")
    payload = json.loads(params) if params else {}
    result = ActionSelectionResult(
        selected_action=handler_type,
        action_parameters=payload,
        rationale="manual trigger",
    )
    thought = _create_thought()
    await handler_instance.handle(result, thought, {"channel_id": runtime.startup_channel_id})


async def _run_runtime(runtime: CIRISRuntime, timeout: Optional[int], num_rounds: Optional[int] = None) -> None:
    """Run the runtime with optional timeout and graceful shutdown."""
    logger.info(f"[DEBUG] _run_runtime called with timeout={timeout}, num_rounds={num_rounds}")
    try:
        if timeout:
            # Use asyncio.wait_for for timeout handling  
            logger.info(f"[DEBUG] Setting up timeout for {timeout} seconds")
            try:
                await asyncio.wait_for(runtime.run(num_rounds=num_rounds), timeout=timeout)
            except asyncio.TimeoutError:
                logger.info(f"Timeout of {timeout} seconds reached, shutting down...")
                # The runtime.run() call has likely already completed its own shutdown
                # Just ensure we exit cleanly without redundant shutdown calls
                try:
                    if hasattr(runtime, 'is_running') and runtime.is_running:
                        runtime.request_shutdown(f"Runtime timeout after {timeout} seconds")
                        await runtime.shutdown()
                    else:
                        logger.info("Runtime already stopped, no additional shutdown needed")
                except Exception as e:
                    logger.warning(f"Error during timeout shutdown: {e}")
        else:
            # Run without timeout
            logger.info(f"[DEBUG] Running without timeout")
            await runtime.run(num_rounds=num_rounds)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down gracefully...")
        runtime.request_shutdown("User interrupt")
        await runtime.shutdown()
    except Exception as e:
        logger.error(f"FATAL ERROR: Unhandled exception in runtime: {e}", exc_info=True)
        try:
            runtime.request_shutdown(f"Fatal error: {e}")
            await runtime.shutdown()
        except Exception as shutdown_error:
            logger.error(f"Error during emergency shutdown: {shutdown_error}", exc_info=True)
        raise  # Re-raise to ensure non-zero exit code


@click.command()
@click.option("--adapter", "modes_list", multiple=True, default=["auto"], help="One or more adapters to run. Specify multiple times for multiple adapters (e.g., --adapter cli --adapter api --adapter discord).")
@click.option("--modes", "legacy_modes", help="Legacy comma-separated list of modes (deprecated, use --adapter instead).")
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", "config_file_path", type=click.Path(exists=True), help="Path to app config")
@click.option("--task", multiple=True, help="Task description to add before starting")
@click.option("--timeout", type=int, help="Maximum runtime duration in seconds")
@click.option("--handler", help="Direct handler to execute and exit")
@click.option("--params", help="JSON parameters for handler execution")
@click.option("--host", "api_host", default=None, help="API host (default: 0.0.0.0)")
@click.option("--port", "api_port", default=None, type=int, help="API port (default: 8080)")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--no-interactive/--interactive", "cli_interactive", default=True, help="Enable/disable interactive CLI input")
@click.option("--discord-token", "discord_bot_token", default=os.environ.get("DISCORD_BOT_TOKEN"), help="Discord bot token")
@click.option("--mock-llm/--no-mock-llm", default=False, help="Use the mock LLM service for offline testing")
@click.option("--num-rounds", type=int, help="Maximum number of processing rounds (default: infinite)")
def main(
    modes_list: tuple[str, ...],
    legacy_modes: Optional[str],
    profile: str,
    config_file_path: Optional[str],
    task: tuple[str],
    timeout: Optional[int],
    handler: Optional[str],
    params: Optional[str],
    api_host: Optional[str],
    api_port: Optional[int],
    debug: bool,
    cli_interactive: bool,
    discord_bot_token: Optional[str],
    mock_llm: bool,
    num_rounds: Optional[int],
) -> None:
    """Unified CIRIS agent entry point."""
    setup_basic_logging(level=logging.DEBUG if debug else logging.INFO)

    async def _async_main() -> None:
        from ciris_engine.config.env_utils import get_env_var

        if not mock_llm and not get_env_var("OPENAI_API_KEY"):
            click.echo(
                "OPENAI_API_KEY not set. The agent requires an OpenAI-compatible LLM. "
                "For a local model set OPENAI_API_BASE, OPENAI_MODEL_NAME and provide any OPENAI_API_KEY."
            )

        # Handle backward compatibility for --modes
        final_modes_list = list(modes_list)
        if legacy_modes:
            click.echo("Warning: --modes is deprecated. Use --adapter instead (e.g., --adapter cli --adapter api).", err=True)
            # Split comma-separated modes and add to the list
            legacy_mode_list = [mode.strip() for mode in legacy_modes.split(",")]
            final_modes_list.extend(legacy_mode_list)
        
        # Handle mode auto-detection and support multiple instances of same adapter type
        selected_modes = []
        for mode in final_modes_list:
            if "auto" == mode:
                auto_mode = "discord" if discord_bot_token or get_env_var("DISCORD_BOT_TOKEN") else "cli"
                selected_modes.append(auto_mode)
            elif ":" in mode:
                # Support instance-specific modes like "discord:instance1" or "api:port8081"
                selected_modes.append(mode)
            else:
                selected_modes.append(mode)

        # Validate Discord modes have tokens available
        validated_modes = []
        for mode in selected_modes:
            if mode.startswith("discord"):
                base_mode, instance_id = (mode.split(":", 1) + [None])[:2]
                # Check for instance-specific token or fallback to general token
                token_vars = []
                if instance_id:
                    token_vars.extend([f"DISCORD_{instance_id.upper()}_BOT_TOKEN", f"DISCORD_BOT_TOKEN_{instance_id.upper()}"])
                token_vars.append("DISCORD_BOT_TOKEN")
                
                has_token = discord_bot_token or any(get_env_var(var) for var in token_vars)
                if not has_token:
                    click.echo(f"No Discord bot token found for {mode}, falling back to CLI mode")
                    validated_modes.append("cli")
                else:
                    validated_modes.append(mode)
            else:
                validated_modes.append(mode)
        
        selected_modes = validated_modes

        # Load config
        app_config = await load_config(config_file_path)

        if mock_llm:
            from ciris_engine.services.mock_llm import MockLLMService  # type: ignore
            import ciris_engine.runtime.ciris_runtime as runtime_module
            import ciris_engine.services.llm_service as llm_service_module
            import ciris_engine.adapters as adapters_module
            runtime_module.OpenAICompatibleClient = MockLLMService  # patch
            llm_service_module.OpenAICompatibleClient = MockLLMService  # patch
            if hasattr(adapters_module, 'OpenAICompatibleClient'):
                adapters_module.OpenAICompatibleClient = MockLLMService  # patch
            app_config.mock_llm = True  # Set the flag in config for other components

        
        # Create adapter configurations for each mode and determine startup channel
        adapter_configs = {}
        startup_channel_id = getattr(app_config, 'startup_channel_id', None)
        if hasattr(app_config, 'discord_channel_id'):
            startup_channel_id = app_config.discord_channel_id
        
        for mode in selected_modes:
            if mode.startswith("api"):
                base_mode, instance_id = (mode.split(":", 1) + [None])[:2]
                from ciris_engine.adapters.api.config import APIAdapterConfig
                
                api_config = APIAdapterConfig()
                if api_host:
                    api_config.host = api_host
                if api_port:
                    api_config.port = api_port
                
                # Load environment variables with instance-specific support
                if instance_id:
                    api_config.load_env_vars_with_instance(instance_id)
                else:
                    api_config.load_env_vars()
                
                adapter_configs[mode] = api_config
                api_channel_id = api_config.get_home_channel_id(api_config.host, api_config.port)
                if not startup_channel_id:
                    startup_channel_id = api_channel_id
                    
            elif mode.startswith("discord"):
                base_mode, instance_id = (mode.split(":", 1) + [None])[:2]
                from ciris_engine.adapters.discord.config import DiscordAdapterConfig
                
                discord_config = DiscordAdapterConfig()
                if discord_bot_token:
                    discord_config.bot_token = discord_bot_token
                
                # Load environment variables with instance-specific support
                if instance_id:
                    discord_config.load_env_vars_with_instance(instance_id)
                else:
                    discord_config.load_env_vars()
                
                adapter_configs[mode] = discord_config
                discord_channel_id = discord_config.get_home_channel_id()
                if discord_channel_id and not startup_channel_id:
                    startup_channel_id = discord_channel_id
                    
            elif mode.startswith("cli"):
                base_mode, instance_id = (mode.split(":", 1) + [None])[:2]
                from ciris_engine.adapters.cli.config import CLIAdapterConfig
                
                cli_config = CLIAdapterConfig()
                
                # Load environment variables first, then override with CLI args
                if instance_id:
                    cli_config.load_env_vars_with_instance(instance_id)
                else:
                    cli_config.load_env_vars()
                
                # CLI arguments take precedence over environment variables
                if not cli_interactive:
                    cli_config.interactive = False
                
                adapter_configs[mode] = cli_config
                cli_channel_id = cli_config.get_home_channel_id()
                if not startup_channel_id:
                    startup_channel_id = cli_channel_id

        # Setup global exception handling
        setup_global_exception_handler()
        
        # Create runtime using new CIRISRuntime directly with adapter configs
        runtime = CIRISRuntime(
            modes=selected_modes,
            profile_name=profile,
            app_config=app_config,
            startup_channel_id=startup_channel_id,
            adapter_configs=adapter_configs,
            interactive=cli_interactive,
            host=api_host,
            port=api_port,
            discord_bot_token=discord_bot_token,
        )
        await runtime.initialize()
        
        # Setup signal handlers for graceful shutdown
        setup_signal_handlers(runtime)

        # Store preload tasks to be loaded after WORK state transition
        preload_tasks = list(task) if task else []
        runtime.set_preload_tasks(preload_tasks)

        if handler:
            await _execute_handler(runtime, handler, params)
            await runtime.shutdown()
            return

        # Use CLI num_rounds if provided, otherwise fall back to config
        effective_num_rounds = num_rounds
        if effective_num_rounds is None and hasattr(app_config, 'workflow') and hasattr(app_config.workflow, 'num_rounds'):
            effective_num_rounds = app_config.workflow.num_rounds

        await _run_runtime(runtime, timeout, effective_num_rounds)

    try:
        asyncio.run(_async_main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user, exiting...")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error in main: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()