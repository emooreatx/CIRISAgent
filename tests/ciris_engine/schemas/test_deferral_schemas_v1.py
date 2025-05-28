from ciris_engine.schemas.deferral_schemas_v1 import DeferralReason, DeferralPackage

def test_deferral_reason_enum():
    assert DeferralReason.GUARDRAIL_FAILURE == "guardrail_failure"
    assert DeferralReason.UNKNOWN == "unknown"

def test_deferral_package_minimal():
    pkg = DeferralPackage(
        thought_id="t1",
        task_id="task1",
        deferral_reason=DeferralReason.SYSTEM_ERROR,
        reason_description="desc",
        thought_content="content"
    )
    assert pkg.thought_id == "t1"
    assert pkg.deferral_reason == DeferralReason.SYSTEM_ERROR
    assert pkg.ponder_history == []

def test_deferral_package_full():
    pkg = DeferralPackage(
        thought_id="t2",
        task_id="task2",
        deferral_reason=DeferralReason.ETHICAL_CONCERN,
        reason_description="desc2",
        thought_content="content2",
        task_description="desc task",
        ethical_assessment={"ok": True},
        csdma_assessment={"score": 1},
        dsdma_assessment={"score": 2},
        user_profiles={"user": "u"},
        system_snapshot={"sys": 1},
        ponder_history=["p1", "p2"]
    )
    assert pkg.task_description == "desc task"
    assert pkg.ponder_history == ["p1", "p2"]
