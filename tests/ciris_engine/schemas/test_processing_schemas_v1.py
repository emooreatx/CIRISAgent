from ciris_engine.schemas.processing_schemas_v1 import DMAResults, ThoughtContext, GuardrailResult
from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

def test_dma_results_defaults():
    res = DMAResults()
    assert res.ethical_pdma is None
    assert res.csdma is None
    assert res.dsdma is None
    assert res.errors == []

def test_thought_context_minimal():
    ctx = ThoughtContext(system_snapshot={}, user_profiles={}, task_history=[])
    assert ctx.system_snapshot == {}
    assert ctx.user_profiles == {}
    assert ctx.task_history == []
    assert ctx.identity_context is None

def test_guardrail_result_minimal():
    action = ActionSelectionResult(selected_action=HandlerActionType.OBSERVE, action_parameters={}, rationale="r")
    res = GuardrailResult(original_action=action, final_action=action)
    assert res.original_action == action
    assert res.final_action == action
    assert res.overridden is False
    assert res.override_reason is None
