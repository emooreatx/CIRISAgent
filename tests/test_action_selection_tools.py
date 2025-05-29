import pytest
from unittest.mock import patch, Mock
from ciris_engine.dma.action_selection_pdma import ActionSelectionPDMAEvaluator
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from openai import AsyncOpenAI

@pytest.mark.asyncio
async def test_tools_listed_in_prompt(monkeypatch):
    # Patch ToolHandler and its _tool_registry
    fake_tools = {'discord_ban': Mock(), 'discord_kick': Mock(), 'discord_mute': Mock()}
    class FakeToolRegistry:
        _tools = fake_tools
    class FakeToolHandler:
        _tool_registry = FakeToolRegistry()
    monkeypatch.setattr('ciris_engine.action_handlers.tool_handler.ToolHandler', FakeToolHandler)

    # Patch ENGINE_OVERVIEW_TEMPLATE to a known value
    monkeypatch.setattr('ciris_engine.dma.action_selection_pdma.ENGINE_OVERVIEW_TEMPLATE', 'ENGINE_OVERVIEW')

    # Minimal triaged_inputs with TOOL permitted
    triaged_inputs = {
        'original_thought': Mock(content='Test tool usage', ponder_notes=None, thought_id='t1', thought_type='query'),
        'ethical_pdma_result': Mock(alignment_check={}, decision='ok'),
        'csdma_result': Mock(plausibility_score=1.0, flags=[], reasoning=''),
        'current_ponder_count': 0,
        'max_ponder_rounds': 3,
        'permitted_actions': [HandlerActionType.TOOL],
    }
    # Patch format_user_profiles and format_system_snapshot to empty
    monkeypatch.setattr('ciris_engine.formatters.format_user_profiles', lambda x: '')
    monkeypatch.setattr('ciris_engine.formatters.format_system_snapshot', lambda x: '')

    evaluator = ActionSelectionPDMAEvaluator(aclient=AsyncOpenAI())
    prompt = evaluator._prepare_main_user_content(triaged_inputs)
    # Check that all fake tool names appear in the prompt
    for tool_name in fake_tools:
        assert tool_name in prompt, f"Tool '{tool_name}' not listed in prompt: {prompt}"
