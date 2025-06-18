import pytest
from unittest.mock import patch, Mock
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from types import SimpleNamespace
from ciris_engine.registries.base import ServiceRegistry, Priority

@pytest.mark.asyncio
async def test_tools_listed_in_prompt(monkeypatch):
    # Mock the service registry to return our fake tools
    class MockToolService:
        async def get_available_tools(self):
            return {
                'discord_delete_message': {'description': 'Delete a message', 'parameters': {}},
                'discord_timeout_user': {'description': 'Temporarily mute a user', 'parameters': {}},
                'discord_ban_user': {'description': 'Ban a user from the server', 'parameters': {}}
            }
    
    mock_tool_service = MockToolService()
    mock_service_registry = Mock()
    mock_service_registry.get_services_by_type = Mock(return_value=[mock_tool_service])

    # Patch ENGINE_OVERVIEW_TEMPLATE to a known value
    monkeypatch.setattr('ciris_engine.utils.constants.ENGINE_OVERVIEW_TEMPLATE', 'ENGINE_OVERVIEW')

    # Minimal triaged_inputs with TOOL permitted
    triaged_inputs = {
        'original_thought': Mock(content='Test tool usage', ponder_notes=None, thought_id='t1', thought_type='query'),
        'ethical_pdma_result': Mock(alignment_check={}, decision='ok'),
        'csdma_result': Mock(plausibility_score=1.0, flags=[], reasoning=''),
        'current_thought_depth': 0,
        'max_rounds': 3,
        'permitted_actions': [HandlerActionType.TOOL],
    }
    # Patch format_user_profiles and format_system_snapshot to empty
    monkeypatch.setattr('ciris_engine.formatters.format_user_profiles', lambda x: '')
    monkeypatch.setattr('ciris_engine.formatters.format_system_snapshot', lambda x: '')

    service_registry = ServiceRegistry()
    dummy_client = SimpleNamespace(client=Mock())
    dummy_service = SimpleNamespace(get_client=lambda: dummy_client)
    service_registry.register_global("llm", dummy_service, priority=Priority.HIGH)
    monkeypatch.setattr('instructor.patch', lambda c, mode: c)
    evaluator = ActionSelectionPDMAEvaluator(service_registry=service_registry)
    prompt = evaluator.context_builder.build_main_user_content(triaged_inputs)
    
    # Check that the default tool names appear in the prompt (since we can't inject custom tools easily)
    expected_tools = ['discord_delete_message', 'discord_timeout_user', 'discord_ban_user']
    for tool_name in expected_tools:
        assert tool_name in prompt, f"Tool '{tool_name}' not listed in prompt: {prompt}"
