import asyncio
import pytest
from unittest.mock import AsyncMock, patch, ANY

from ciris_engine.core.action_dispatcher import ActionDispatcher
from ciris_engine.core.agent_core_schemas import (
    ActionSelectionPDMAResult,
    SpeakParams,
    ActParams,
    DeferParams,
    RejectParams,
    PonderParams,
    MemorizeParams,
    RememberParams,
    ForgetParams,
    ObserveParams,
)
from ciris_engine.core.foundational_schemas import HandlerActionType, ObservationSourceType

@pytest.mark.asyncio
@patch('ciris_engine.core.persistence.add_thought')
@patch('ciris_engine.services.audit_service.AuditService.log_action')
async def test_enqueue_memory_meta_thought(mock_log_action, mock_add_thought):
    dispatcher = ActionDispatcher()
    handler = AsyncMock()
    dispatcher.register_service_handler("discord", handler)

    result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi"),
        action_selection_rationale="r",
        monitoring_for_selected_action={}
    )

    mock_add_thought.return_value = None
    await dispatcher.dispatch(
        result,
        {
            "origin_service": "discord",
            "source_task_id": "t1",
            "author_name": "a",
            "channel_id": "c",
            "originator_id": "agent:test",
            "event_summary": "test",
            "event_payload": {},
        },
    )

    mock_add_thought.assert_not_called()
    mock_log_action.assert_called_once()

@pytest.mark.asyncio
@patch('ciris_engine.core.persistence.add_thought')
@patch('ciris_engine.services.audit_service.AuditService.log_action')
async def test_memory_meta_created_for_memorize(mock_log_action, mock_add_thought):
    dispatcher = ActionDispatcher()
    handler = AsyncMock()
    dispatcher.register_service_handler("discord", handler)

    mem_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection="c",
        action_alignment_check={},
        selected_handler_action=HandlerActionType.MEMORIZE,
        action_parameters=MemorizeParams(
            knowledge_unit_description='k',
            knowledge_data='d',
            knowledge_type='t',
            source='s',
            confidence=0.5
        ),
        action_selection_rationale="learned",
        monitoring_for_selected_action={},
    )

    mock_add_thought.return_value = None
    await dispatcher.dispatch(
        mem_result,
        {
            "origin_service": "discord",
            "source_task_id": "t1",
            "author_name": "a",
            "channel_id": "c",
        },
    )

    mock_add_thought.assert_called_once()

@pytest.mark.asyncio
@patch('ciris_engine.core.persistence.add_thought')
@patch('ciris_engine.services.audit_service.AuditService.log_action')
async def test_audit_logging_for_each_action(mock_log_action, mock_add_thought):
    dispatcher = ActionDispatcher()
    handler = AsyncMock()
    dispatcher.register_service_handler('discord', handler)
    dispatcher.register_service_handler('memory', handler)
    dispatcher.register_service_handler('observer', handler)

    action_map = {
        HandlerActionType.SPEAK: SpeakParams(content='x'),
        HandlerActionType.ACT: ActParams(tool_name='t', arguments={}),
        HandlerActionType.REJECT: RejectParams(reason='r'),
        HandlerActionType.DEFER: DeferParams(reason='d', target_wa_ual='ka:test', deferral_package_content={}),
        HandlerActionType.MEMORIZE: MemorizeParams(knowledge_unit_description='k', knowledge_data='d', knowledge_type='t', source='s', confidence=0.5),
        HandlerActionType.REMEMBER: RememberParams(query='q'),
        HandlerActionType.FORGET: ForgetParams(reason='f'),
        HandlerActionType.OBSERVE: ObserveParams(sources=[ObservationSourceType.USER_REQUEST]),
    }

    mock_add_thought.return_value = None
    for act, params in action_map.items():
        mock_log_action.reset_mock()
        result = ActionSelectionPDMAResult(
            context_summary_for_action_selection='c',
            action_alignment_check={},
            selected_handler_action=act,
            action_parameters=params,
            action_selection_rationale='r',
            monitoring_for_selected_action={},
        )
        service_name = 'discord'
        if act in {HandlerActionType.MEMORIZE, HandlerActionType.REMEMBER, HandlerActionType.FORGET}:
            service_name = 'memory'
        if act == HandlerActionType.OBSERVE:
            service_name = 'observer'
        await dispatcher.dispatch(
            result,
            {
                'origin_service': service_name,
                'originator_id': 'agent:test',
                'event_summary': 'x',
                'event_payload': {},
            },
        )
        mock_log_action.assert_called_once_with(act, ANY)

    # PONDER should not trigger logging
    mock_log_action.reset_mock()
    ponder_result = ActionSelectionPDMAResult(
        context_summary_for_action_selection='c',
        action_alignment_check={},
        selected_handler_action=HandlerActionType.PONDER,
        action_parameters=PonderParams(key_questions=['?']),
        action_selection_rationale='r',
        monitoring_for_selected_action={},
    )
    await dispatcher.dispatch(ponder_result, {'origin_service': 'discord'})
    mock_log_action.assert_not_called()
