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
from typing import Optional

import click

from ciris_engine.main import create_runtime, load_config
from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.processor.task_manager import TaskManager
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus
from ciris_engine.utils.shutdown_manager import get_shutdown_manager

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


async def _execute_handler(runtime, handler: str, params: Optional[str]) -> None:
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


async def _run_runtime(runtime, timeout: Optional[int], num_rounds: Optional[int] = None) -> None:
    """Run the runtime with optional timeout and graceful shutdown."""
    timeout_task = None
    shutdown_manager = get_shutdown_manager()
    
    try:
        if timeout:
            # Create a timeout task that will trigger global shutdown
            async def timeout_handler():
                await asyncio.sleep(timeout)
                logger.info(f"Timeout of {timeout} seconds reached, initiating graceful shutdown...")
                shutdown_manager.request_shutdown(f"Runtime timeout after {timeout} seconds")
            
            timeout_task = asyncio.create_task(timeout_handler())
            
        # Run the runtime (this will handle global shutdown internally)
        await runtime.run(num_rounds=num_rounds)
            
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, requesting shutdown...")
        shutdown_manager.request_shutdown("Keyboard interrupt received")
    except Exception as e:
        logger.error(f"Runtime error: {e}", exc_info=True)
        shutdown_manager.request_shutdown(f"Runtime error: {e}")
    finally:
        # Cancel the timeout task if it's still running
        if timeout_task and not timeout_task.done():
            timeout_task.cancel()
            try:
                await timeout_task
            except asyncio.CancelledError:
                pass
        
        # Always ensure proper shutdown if it hasn't been called yet
        try:
            await runtime.shutdown()
        except Exception as e:
            logger.error(f"Error during final shutdown: {e}", exc_info=True)


@click.command()
@click.option("--mode", type=click.Choice(["auto", "discord", "cli", "api"]), default="auto", help="Runtime mode")
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", type=click.Path(exists=True), help="Path to app config")
@click.option("--task", multiple=True, help="Task description to add before starting")
@click.option("--timeout", type=int, help="Maximum runtime duration in seconds")
@click.option("--handler", help="Direct handler to execute and exit")
@click.option("--params", help="JSON parameters for handler execution")
@click.option("--host", default="0.0.0.0", help="API host")
@click.option("--port", default=8080, type=int, help="API port")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
@click.option("--no-interactive/--interactive", default=False, help="Disable interactive CLI input (start agent automatically)")
@click.option("--mock-llm/--no-mock-llm", default=False, help="Use the mock LLM service for offline testing")
@click.option("--num-rounds", type=int, help="Maximum number of processing rounds (default: infinite)")
def main(
    mode: str,
    profile: str,
    config: Optional[str],
    task: tuple[str],
    timeout: Optional[int],
    handler: Optional[str],
    params: Optional[str],
    host: str,
    port: int,
    debug: bool,
    no_interactive: bool,
    mock_llm: bool,
    num_rounds: Optional[int],
) -> None:
    """Unified CIRIS agent entry point."""
    setup_basic_logging(level=logging.DEBUG if debug else logging.INFO)

    async def _async_main():
        if not os.getenv("OPENAI_API_KEY"):
            click.echo(
                "OPENAI_API_KEY not set. The agent requires an OpenAI-compatible LLM. "
                "For a local model set OPENAI_API_BASE, OPENAI_MODEL_NAME and provide any OPENAI_API_KEY."
            )

        app_config = await load_config(config)

        selected_mode = mode
        if mode == "auto":
            selected_mode = "discord" if os.getenv("DISCORD_BOT_TOKEN") else "cli"

        if selected_mode == "discord" and not os.getenv("DISCORD_BOT_TOKEN"):
            click.echo("DISCORD_BOT_TOKEN not set, falling back to CLI mode")
            selected_mode = "cli"

        interactive = not no_interactive if selected_mode == "cli" else True

        if mock_llm:
            from tests.adapters.mock_llm import MockLLMService  # type: ignore
            import ciris_engine.runtime.ciris_runtime as runtime_module
            runtime_module.OpenAICompatibleLLM = MockLLMService  # patch

        runtime = create_runtime(
            selected_mode,
            profile,
            app_config,
            interactive=interactive,
            host=host,
            port=port,
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

