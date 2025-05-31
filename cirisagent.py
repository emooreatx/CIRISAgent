import asyncio
import json
import logging
import os
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


async def _run_runtime(runtime, timeout: Optional[int]) -> None:
    async def runner():
        await runtime.run()
    if timeout:
        try:
            await asyncio.wait_for(runner(), timeout=timeout)
        except asyncio.TimeoutError:
            logger.info("Timeout reached, shutting down")
    else:
        await runner()


@click.command()
@click.option("--mode", type=click.Choice(["auto", "discord", "cli", "api"]), default="auto", help="Runtime mode")
@click.option("--profile", default="default", help="Agent profile name")
@click.option("--config", type=click.Path(exists=True), help="Path to app config")
@click.option("--task", multiple=True, help="Task description to add before starting")
@click.option("--timeout", type=int, help="Maximum runtime duration in seconds")
@click.option("--handler", help="Direct handler to execute and exit")
@click.option("--params", help="JSON parameters for handler execution")
@click.option("--debug/--no-debug", default=False, help="Enable debug logging")
def main(mode: str, profile: str, config: Optional[str], task: tuple[str], timeout: Optional[int], handler: Optional[str], params: Optional[str], debug: bool) -> None:
    """Unified CIRIS agent entry point."""
    setup_basic_logging(level=logging.DEBUG if debug else logging.INFO)

    async def _async_main():
        app_config = await load_config(config)
        selected_mode = mode
        if mode == "auto":
            selected_mode = "discord" if os.getenv("DISCORD_BOT_TOKEN") else "cli"
        runtime = create_runtime(selected_mode, profile, app_config)
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

        await _run_runtime(runtime, timeout)

    asyncio.run(_async_main())


if __name__ == "__main__":
    main()

