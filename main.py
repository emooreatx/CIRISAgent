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


def _create_thought() -> Thought:
    now = datetime.now(timezone.utc).isoformat()
    return Thought(
        thought_id=str(uuid.uuid4()),
        source_task_id=str(uuid.uuid4()),
        thought_type="manual",
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
    if timeout:
        # Use asyncio.wait_for for timeout handling  
        try:
            await asyncio.wait_for(runtime.run(num_rounds=num_rounds), timeout=timeout)
        except asyncio.TimeoutError:
            logger.info(f"Timeout of {timeout} seconds reached, shutting down...")
            runtime.request_shutdown(f"Runtime timeout after {timeout} seconds")
            await runtime.shutdown()
    else:
        # Run without timeout
        await runtime.run(num_rounds=num_rounds)


@click.command()
@click.option("--modes", "modes_list", multiple=True, default=["auto"], help="One or more adapter modes to run (e.g., cli, api, discord).")
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", "config_file_path", type=click.Path(exists=True), help="Path to app config")
@click.option("--task", multiple=True, help="Task description to add before starting")
@click.option("--timeout", type=int, help="Maximum runtime duration in seconds")
@click.option("--handler", help="Direct handler to execute and exit")
@click.option("--params", help="JSON parameters for handler execution")
@click.option("--host", "api_host", default="0.0.0.0", help="API host")
@click.option("--port", "api_port", default=8080, type=int, help="API port")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--no-interactive/--interactive", "cli_interactive", default=True, help="Enable/disable interactive CLI input")
@click.option("--discord-token", "discord_bot_token", default=os.environ.get("DISCORD_BOT_TOKEN"), help="Discord bot token")
@click.option("--mock-llm/--no-mock-llm", default=False, help="Use the mock LLM service for offline testing")
@click.option("--num-rounds", type=int, help="Maximum number of processing rounds (default: infinite)")
def main(
    modes_list: tuple[str, ...],
    profile: str,
    config_file_path: Optional[str],
    task: tuple[str],
    timeout: Optional[int],
    handler: Optional[str],
    params: Optional[str],
    api_host: str,
    api_port: int,
    debug: bool,
    cli_interactive: bool,
    discord_bot_token: Optional[str],
    mock_llm: bool,
    num_rounds: Optional[int],
) -> None:
    """Unified CIRIS agent entry point."""
    setup_basic_logging(level=logging.DEBUG if debug else logging.INFO)

    async def _async_main():
        from ciris_engine.config.env_utils import get_env_var

        if not get_env_var("OPENAI_API_KEY"):
            click.echo(
                "OPENAI_API_KEY not set. The agent requires an OpenAI-compatible LLM. "
                "For a local model set OPENAI_API_BASE, OPENAI_MODEL_NAME and provide any OPENAI_API_KEY."
            )

        app_config = await load_config(config_file_path)

        # Handle mode auto-detection
        selected_modes = list(modes_list)
        if "auto" in selected_modes:
            selected_modes.remove("auto")
            auto_mode = "discord" if discord_bot_token or get_env_var("DISCORD_BOT_TOKEN") else "cli"
            selected_modes.append(auto_mode)

        if "discord" in selected_modes and not (discord_bot_token or get_env_var("DISCORD_BOT_TOKEN")):
            click.echo("DISCORD_BOT_TOKEN not set, falling back to CLI mode")
            selected_modes = ["cli" if m == "discord" else m for m in selected_modes]

        if mock_llm:
            from tests.adapters.mock_llm import MockLLMService  # type: ignore
            import ciris_engine.runtime.ciris_runtime as runtime_module
            runtime_module.OpenAICompatibleLLM = MockLLMService  # patch
            app_config.mock_llm = True  # Set the flag in config for other components
        
        # Set startup_channel_id
        startup_channel_id = getattr(app_config, 'startup_channel_id', None)
        if hasattr(app_config, 'discord_channel_id'):
            startup_channel_id = app_config.discord_channel_id
        
        # Set channel_id based on mode
        if "api" in selected_modes:
            app_config.api_channel_id = f"{api_host}:{api_port}"
            if not startup_channel_id:
                startup_channel_id = app_config.api_channel_id
        elif "cli" in selected_modes:
            # Use user@hostname for CLI channel_id
            import getpass
            import socket
            try:
                username = getpass.getuser()
                hostname = socket.gethostname()
                app_config.cli_channel_id = f"{username}@{hostname}"
            except Exception:
                # Fallback to generic if we can't get user/hostname
                app_config.cli_channel_id = "cli_terminal"
            if not startup_channel_id:
                startup_channel_id = app_config.cli_channel_id

        # Create runtime using new CIRISRuntime directly
        runtime = CIRISRuntime(
            modes=selected_modes,
            profile_name=profile,
            app_config=app_config,
            startup_channel_id=startup_channel_id,
            interactive=cli_interactive,
            host=api_host,
            port=api_port,
            discord_bot_token=discord_bot_token,
        )
        await runtime.initialize()

        # Preload tasks
        if task:
            tm = TaskManager()
            for desc in task:
                tm.create_task(desc, context={"channel_id": runtime.startup_channel_id})

        if handler:
            await _execute_handler(runtime, handler, params)
            await runtime.shutdown()
            return

        # Use CLI num_rounds if provided, otherwise fall back to config
        effective_num_rounds = num_rounds
        if effective_num_rounds is None and hasattr(app_config, 'workflow') and hasattr(app_config.workflow, 'num_rounds'):
            effective_num_rounds = app_config.workflow.num_rounds

        await _run_runtime(runtime, timeout, effective_num_rounds)

    asyncio.run(_async_main())


if __name__ == "__main__":
    main()