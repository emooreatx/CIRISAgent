import pytest
import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.processor.work_processor import WorkProcessor
from ciris_engine.processor.main_processor import AgentProcessor
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.foundational_schemas_v1 import ThoughtStatus


def make_thought():
    return Thought(
        thought_id="th1",
        source_task_id="task1",
        thought_type="test",
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=1,
        content="content",
        context={},
        ponder_count=0,
        ponder_notes=None,
        parent_thought_id=None,
        final_action={},
        priority=1,
    )


@pytest.mark.asyncio
async def test_work_processor_injects_discord_service(monkeypatch):
    proc = WorkProcessor(app_config=AppConfig(), thought_processor=AsyncMock(), action_dispatcher=AsyncMock(), services={})
    proc.discord_service = "DS"
    thought = make_thought()
    item = ProcessingQueueItem.from_thought(thought)
    result = MagicMock(selected_action="OBSERVE")
    monkeypatch.setattr("ciris_engine.processor.work_processor.persistence.get_thought_by_id", lambda x: thought)
    monkeypatch.setattr("ciris_engine.processor.work_processor.persistence.get_task_by_id", lambda x: None)
    dispatch_action = AsyncMock()
    proc.dispatch_action = dispatch_action
    await proc._dispatch_thought_result(item, result)
    assert dispatch_action.call_args.args[2]["discord_service"] == "DS"


@pytest.mark.asyncio
async def test_agent_processor_injects_discord_service(monkeypatch):
    app_config = AppConfig()
    dispatcher = AsyncMock()
    processor = AgentProcessor(
        app_config=app_config,
        thought_processor=AsyncMock(),
        action_dispatcher=dispatcher,
        services={},
        startup_channel_id=None,
    )
    processor.discord_service = "DS"
    thought = make_thought()
    item = ProcessingQueueItem.from_thought(thought)
    monkeypatch.setattr("ciris_engine.processor.main_processor.persistence.get_task_by_id", lambda x: None)
    sub_proc = MagicMock()
    sub_proc.process_thought_item = AsyncMock(return_value=MagicMock())
    processor.state_processors[processor.state_manager.get_state()] = sub_proc
    dispatcher.dispatch = AsyncMock()
    await processor._process_single_thought(thought)
    assert dispatcher.dispatch.call_args.kwargs["dispatch_context"]["discord_service"] == "DS"

