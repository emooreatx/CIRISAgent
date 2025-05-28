from ciris_engine.schemas.feedback_schemas_v1 import FeedbackType, FeedbackSource, FeedbackDirective, WiseAuthorityFeedback

def test_feedback_type_enum():
    assert FeedbackType.IDENTITY_UPDATE == "identity_update"
    assert FeedbackType.SYSTEM_DIRECTIVE == "system_directive"

def test_feedback_source_enum():
    assert FeedbackSource.WISE_AUTHORITY == "wise_authority"
    assert FeedbackSource.PEER_AGENT == "peer_agent"

def test_feedback_directive():
    d = FeedbackDirective(action="update", target="foo", data={"x": 1})
    assert d.action == "update"
    assert d.target == "foo"
    assert d.data == {"x": 1}

def test_wa_feedback_minimal():
    fb = WiseAuthorityFeedback(
        feedback_id="f1",
        feedback_type=FeedbackType.IDENTITY_UPDATE,
        feedback_source=FeedbackSource.WISE_AUTHORITY
    )
    assert fb.feedback_id == "f1"
    assert fb.directives == []
