import pytest
from ciris_engine.schemas import foundational_schemas_v1 as fs
from pydantic import ValidationError

# Test CaseInsensitiveEnum
class DummyEnum(fs.CaseInsensitiveEnum):
    FOO = "foo"
    BAR = "bar"

def test_case_insensitive_enum():
    assert DummyEnum("foo") == DummyEnum.FOO
    assert DummyEnum("FOO") == DummyEnum.FOO
    assert DummyEnum("Bar") == DummyEnum.BAR
    assert DummyEnum("bar") == DummyEnum.BAR
    with pytest.raises(ValueError):
        DummyEnum("baz")

# Test HandlerActionType
@pytest.mark.parametrize("val,expected", [
    ("observe", fs.HandlerActionType.OBSERVE),
    ("SPEAK", fs.HandlerActionType.SPEAK),
    ("tool", fs.HandlerActionType.TOOL),
    ("reject", fs.HandlerActionType.REJECT),
    ("PONDER", fs.HandlerActionType.PONDER),
    ("defer", fs.HandlerActionType.DEFER),
    ("memorize", fs.HandlerActionType.MEMORIZE),
    ("recall", fs.HandlerActionType.RECALL),
    ("forget", fs.HandlerActionType.FORGET),
    ("task_complete", fs.HandlerActionType.TASK_COMPLETE),
])
def test_handler_action_type(val, expected):
    assert fs.HandlerActionType(val) == expected

# Test TaskStatus and ThoughtStatus enums
@pytest.mark.parametrize("enum_cls, val, expected", [
    (fs.TaskStatus, "pending", fs.TaskStatus.PENDING),
    (fs.TaskStatus, "ACTIVE", fs.TaskStatus.ACTIVE),
    (fs.ThoughtStatus, "processing", fs.ThoughtStatus.PROCESSING),
    (fs.ThoughtStatus, "FAILED", fs.ThoughtStatus.FAILED),
])
def test_status_enums(enum_cls, val, expected):
    assert enum_cls(val) == expected

# Test ObservationSourceType
@pytest.mark.parametrize("val,expected", [
    ("chat_message", fs.ObservationSourceType.CHAT_MESSAGE),
    ("feedback_package", fs.ObservationSourceType.FEEDBACK_PACKAGE),
    ("user_request", fs.ObservationSourceType.USER_REQUEST),
])
def test_observation_source_type(val, expected):
    assert fs.ObservationSourceType(val) == expected

# Test IncomingMessage model

def test_incoming_message_valid():
    msg = fs.DiscordMessage(
        message_id="1",
        author_id="u1",
        author_name="Alice",
        content="Hello",
        channel_id="c1",
        reference_message_id=None,
        timestamp="2023-01-01T00:00:00Z",
        is_bot=False,
        is_dm=True,
    )
    assert msg.author_name == "Alice"
    assert msg.is_dm is True

def test_incoming_message_alias():
    msg = fs.IncomingMessage(
        message_id="2",
        author_id="u2",
        author_name="Bob",
        content="Hi",
        channel_id="c2",
    )
    assert msg.destination_id == "c2"

def test_incoming_message_required_fields():
    with pytest.raises(ValidationError):
        fs.IncomingMessage(author_id="u1", author_name="Bob", content="Hi")


def test_fetched_message_alias_and_optional_fields():
    msg = fs.FetchedMessage(id="123", content="hi")
    assert msg.message_id == "123"
    assert msg.author_id is None


@pytest.mark.parametrize("enum_cls, val, expected", [
    (fs.SchemaVersion, "1.0", fs.SchemaVersion.V1_0),
])
def test_other_enums(enum_cls, val, expected):
    assert enum_cls(val) == expected
