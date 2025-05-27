import pytest
from pydantic import ValidationError
from ciris_engine.schemas.graph_schemas_v1 import (
    GraphNode,
    GraphEdge,
    NodeType,
    GraphScope,
)


def test_graph_node_defaults():
    node = GraphNode(id="n", type=NodeType.USER, scope=GraphScope.LOCAL)
    assert node.version == 1
    assert node.attributes == {}



def test_edge_requires_basic_fields():
    edge = GraphEdge(source="a", target="b", relationship="knows", scope=GraphScope.LOCAL)
    assert edge.weight == 1.0


def test_validated_by_requires_non_pending_state():
    with pytest.raises(ValidationError):
        GraphEdge(
            source="a",
            target="b",
            label="produces",
            scope=GraphScope.LOCAL,
            validated_by=["alice"],
        )

