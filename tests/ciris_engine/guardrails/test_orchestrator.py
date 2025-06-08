import pytest
from ciris_engine.guardrails.orchestrator import GuardrailOrchestrator
from ciris_engine.guardrails.registry import GuardrailRegistry
from ciris_engine.schemas.guardrails_schemas_v1 import GuardrailCheckResult, GuardrailStatus
from ciris_engine.schemas.processing_schemas_v1 import GuardrailResult
from ciris_engine.schemas.agent_core_schemas_v1 import Thought
from ciris_engine.schemas.action_params_v1 import SpeakParams, PonderParams
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType, ThoughtStatus, ThoughtType

DEFAULT_THOUGHT_KWARGS = dict(
    thought_id="t1",
    source_task_id="task1",
    thought_type=ThoughtType.STANDARD,
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
)

class PassingGuardrail:
    async def check(self, action, context):
        return GuardrailCheckResult(status=GuardrailStatus.PASSED, passed=True, check_timestamp="0")

class FailingGuardrail:
    async def check(self, action, context):
        return GuardrailCheckResult(status=GuardrailStatus.FAILED, passed=False, reason="bad", check_timestamp="0")

@pytest.mark.asyncio
async def test_orchestrator_no_override_when_passes():
    registry = GuardrailRegistry()
    registry.register_guardrail("pass", PassingGuardrail())
    orchestrator = GuardrailOrchestrator(registry)

    action = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi"),
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    result = await orchestrator.apply_guardrails(action, thought, {})
    assert not result.overridden
    assert result.final_action == action

@pytest.mark.asyncio
async def test_orchestrator_overrides_on_failure():
    registry = GuardrailRegistry()
    registry.register_guardrail("fail", FailingGuardrail())
    orchestrator = GuardrailOrchestrator(registry)

    action = ActionSelectionResult.model_construct(
        selected_action=HandlerActionType.SPEAK,
        action_parameters=SpeakParams(content="hi"),
        rationale="r",
    )
    thought = Thought(**DEFAULT_THOUGHT_KWARGS)

    result = await orchestrator.apply_guardrails(action, thought, {})
    assert result.overridden
    assert result.final_action.selected_action == HandlerActionType.PONDER
    assert result.override_reason == "bad"
    assert "fail" in result.epistemic_data

