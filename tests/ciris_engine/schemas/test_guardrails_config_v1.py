from ciris_engine.schemas.guardrails_config_v1 import GuardrailsConfig

def test_guardrails_config_defaults():
    config = GuardrailsConfig()
    assert 0.0 <= config.entropy_threshold <= 1.0
    assert 0.0 <= config.coherence_threshold <= 1.0
    assert config.input_sanitization_method == "bleach"
    assert config.pii_detection_enabled is True
    assert 0.0 <= config.pii_confidence_threshold <= 1.0
