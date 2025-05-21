from ciris_engine.formatters.escalation_guidance import get_escalation_guidance


def test_get_escalation_guidance():
    assert "EARLY" in get_escalation_guidance(0)
    assert "MID" in get_escalation_guidance(3)
    assert "LATE" in get_escalation_guidance(5)
    assert "EXHAUSTED" in get_escalation_guidance(7)
