from ciris_engine.schemas.dma_results_v1 import ActionSelectionResult, EthicalDMAResult, CSDMAResult, DSDMAResult
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType

def test_action_selection_result():
    res = ActionSelectionResult(selected_action=HandlerActionType.OBSERVE, action_parameters={}, rationale="r")
    assert res.selected_action == HandlerActionType.OBSERVE
    assert res.rationale == "r"
    assert res.action_parameters == {}

def test_ethical_dma_result():
    res = EthicalDMAResult(alignment_check={"pass": True}, decision="allow")
    assert res.alignment_check["pass"] is True
    assert res.decision == "allow"

def test_csdma_result():
    res = CSDMAResult(plausibility_score=0.5)
    assert res.plausibility_score == 0.5
    assert res.flags == []

def test_dsdma_result():
    res = DSDMAResult(domain="test", alignment_score=1.0)
    assert res.domain == "test"
    assert res.alignment_score == 1.0
    assert res.flags == []
