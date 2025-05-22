import pytest
from pydantic import ValidationError
from ciris_engine.core.graph_schemas import (
    GraphNode,
    GraphEdge,
    NodeType,
    GraphScope,
    ValidationState,
    EmergencyState,
    ConfidentialityLevel,
)


def test_graph_node_defaults():
    node = GraphNode(id="n", type=NodeType.USER, scope=GraphScope.LOCAL)
    assert node.version == 1
    assert node.validation_state is ValidationState.PENDING
    assert node.confidentiality_level is ConfidentialityLevel.PUBLIC
    assert node.validated_by is None


def test_emergency_requires_timestamp():
    with pytest.raises(ValidationError):
        GraphNode(
            id="n",
            type=NodeType.USER,
            scope=GraphScope.LOCAL,
            emergency_state=EmergencyState.ACTIVE,
        )


def test_validated_by_requires_non_pending_state():
    with pytest.raises(ValidationError):
        GraphEdge(
            source="a",
            target="b",
            label="produces",
            scope=GraphScope.LOCAL,
            validated_by=["alice"],
        )

