import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ciris_engine.processor.thought_processor import ThoughtProcessor
from ciris_engine.processor.processing_queue import ProcessingQueueItem
from ciris_engine.action_handlers.base_handler import ActionHandlerDependencies
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.guardrails import GuardrailRegistry
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, ThoughtType
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.action_params_v1 import ObserveParams
from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult


def make_thought(th_id="th-observe"):
    return Thought(
        thought_id=th_id,
        source_task_id="task1",
        thought_type=ThoughtType.STANDARD,
        status=ThoughtStatus.PENDING,
        created_at="now",
        updated_at="now",
        round_number=0,
        content="c",
        context={},
    )


def make_processor():
    app_cfg = MagicMock(spec=AppConfig)
    app_cfg.workflow = MagicMock()
    app_cfg.workflow.max_rounds = 1
    app_cfg.agent_mode = "test"
    app_cfg.default_profile = "default"
    app_cfg.agent_profiles = {"default": {}}

    dma_orch = AsyncMock()
    dma_orch.run_initial_dmas = AsyncMock(return_value={})
    dma_orch.run_action_selection = AsyncMock()

    ctx_builder = AsyncMock()
    ctx_builder.build_thought_context = AsyncMock(return_value={})

    registry = GuardrailRegistry()
    guardrail_orch = GuardrailOrchestrator(registry)
    guardrail_orch.apply_guardrails = AsyncMock()

    deps = MagicMock(spec=ActionHandlerDependencies)
    return ThoughtProcessor(dma_orchestrator=dma_orch,
                             context_builder=ctx_builder,
                             guardrail_orchestrator=guardrail_orch,
                             app_config=app_cfg,
                             dependencies=deps)


@pytest.mark.asyncio
async def test_observe_action_returns_observe_result():
    tp = make_processor()
    thought = make_thought()
    item = ProcessingQueueItem.from_thought(thought, "")

    observe_result = ActionSelectionResult(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=ObserveParams(active=False, context={}),
        rationale="r",
    )

    tp.dma_orchestrator.run_action_selection = AsyncMock(return_value=observe_result)
    tp.guardrail_orchestrator.apply_guardrails = AsyncMock(return_value=GuardrailResult(
        original_action=observe_result,
        final_action=observe_result,
    ))

    with patch.object(tp, "_fetch_thought", return_value=thought):
        result = await tp.process_thought(item)

    assert result is not None
    assert result.selected_action == HandlerActionType.OBSERVE


@pytest.mark.asyncio
async def test_guardrail_none_defaults_to_ponder():
    tp = make_processor()
    thought = make_thought("th-ponder")
    item = ProcessingQueueItem.from_thought(thought, "")

    observe_result = ActionSelectionResult(
        selected_action=HandlerActionType.OBSERVE,
        action_parameters=ObserveParams(active=False, context={}),
        rationale="r",
    )

    tp.dma_orchestrator.run_action_selection = AsyncMock(return_value=observe_result)
    tp.guardrail_orchestrator.apply_guardrails = AsyncMock(return_value=None)

    with patch.object(tp, "_fetch_thought", return_value=thought):
        result = await tp.process_thought(item)

    assert result.selected_action == HandlerActionType.PONDER

