import pytest
from unittest.mock import AsyncMock, MagicMock

from ciris_engine.action_handlers.discord_observe_handler import handle_discord_observe_event
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

@pytest.mark.asyncio
async def test_handle_discord_observe_event_passive(monkeypatch):
    add_task = MagicMock()
    task_exists = MagicMock(return_value=False)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.add_task', add_task)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.task_exists', task_exists)

    payload = {'message_id': 'm1', 'content': 'hello'}
    result = await handle_discord_observe_event(payload, mode='passive')

    assert result.selected_action == HandlerActionType.OBSERVE
    assert result.action_parameters['task_id'] == 'm1'
    add_task.assert_called_once()

@pytest.mark.asyncio
async def test_handle_discord_observe_event_active(monkeypatch):
    add_task = MagicMock()
    task_exists = MagicMock(return_value=False)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.add_task', add_task)
    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.task_exists', task_exists)

    fake_messages = [
        {'id': 'm1', 'content': 'hi', 'author_id': 'a1'},
        {'id': 'm2', 'content': 'yo', 'author_id': 'a2'}
    ]

    discord_service = AsyncMock()
    discord_service.fetch_messages.return_value = fake_messages
    context = {'discord_service': discord_service, 'default_channel_id': 'c1'}

    class DummyTask(dict):
        def __init__(self, **kwargs):
            super().__init__(**kwargs)

    monkeypatch.setattr('ciris_engine.action_handlers.discord_observe_handler.persistence.Task', DummyTask, raising=False)

    payload = {'channel_id': 'c1'}
    result = await handle_discord_observe_event(payload, mode='active', context=context)

    discord_service.fetch_messages.assert_awaited_with(channel_id='c1', offset=0, limit=20, include_agent=True, agent_id=None)
    assert result.selected_action == HandlerActionType.OBSERVE
    assert result.action_parameters['created_tasks'] == ['m1', 'm2']
    assert add_task.call_count == 2
