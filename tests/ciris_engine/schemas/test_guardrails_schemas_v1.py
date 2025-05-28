from ciris_engine.schemas.guardrails_schemas_v1 import GuardrailStatus, GuardrailCheckResult
from datetime import datetime, timezone

def test_guardrail_status_enum():
    assert GuardrailStatus.PASSED == "passed"
    assert GuardrailStatus.WARNING == "warning"

def test_guardrail_check_result_minimal():
    now = datetime.now(timezone.utc).isoformat()
    res = GuardrailCheckResult(
        status=GuardrailStatus.PASSED,
        passed=True,
        check_timestamp=now
    )
    assert res.status == GuardrailStatus.PASSED
    assert res.passed is True
    assert res.check_timestamp == now
    assert isinstance(res.epistemic_data, dict)
