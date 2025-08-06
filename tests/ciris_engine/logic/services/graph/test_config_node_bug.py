"""Test that specifically reproduces the ConfigNode bug with GraphNodeAttributes."""

from datetime import datetime, timezone

import pytest

from ciris_engine.schemas.services.graph_core import GraphNode, GraphNodeAttributes, GraphScope, NodeType
from ciris_engine.schemas.services.nodes import ConfigNode


def test_config_node_from_graph_node_with_graphnodeattributes():
    """Test that reproduces the bug where ConfigNode.from_graph_node fails with GraphNodeAttributes.

    The bug: When node.attributes is a GraphNodeAttributes object (not dict),
    the code sets attrs to {} and then tries to access attrs["key"], causing KeyError.
    """
    # Create a GraphNode with GraphNodeAttributes object (not dict)
    # This happens when nodes are retrieved from certain code paths
    graph_node = GraphNode(
        id="config_test_key_123",
        type=NodeType.CONFIG,
        scope=GraphScope.LOCAL,
        attributes=GraphNodeAttributes(
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
            created_by="test_user",
            tags=["config:test"],
        ),
        version=1,
        updated_by="test_user",
        updated_at=datetime.now(timezone.utc),
    )

    # This should fail with the bug
    with pytest.raises(KeyError, match="key"):
        ConfigNode.from_graph_node(graph_node)


def test_config_node_from_graph_node_with_dict():
    """Test that ConfigNode.from_graph_node works with dict attributes."""
    # This is what works currently
    now = datetime.now(timezone.utc)
    graph_node = GraphNode(
        id="config_test_key_123",
        type=NodeType.CONFIG,
        scope=GraphScope.LOCAL,
        attributes={
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "created_by": "test_user",
            "tags": ["config:test"],
            "key": "test.key",
            "value": {"string_value": "test_value"},
            "node_class": "ConfigNode",
        },
        version=1,
        updated_by="test_user",
        updated_at=now,
    )

    # This should work
    config_node = ConfigNode.from_graph_node(graph_node)
    assert config_node.key == "test.key"
    assert config_node.value.value == "test_value"


if __name__ == "__main__":
    print("Testing ConfigNode bug...")
    try:
        test_config_node_from_graph_node_with_graphnodeattributes()
        print("FAIL: Expected KeyError but didn't get one")
    except KeyError as e:
        print(f"SUCCESS: Got expected KeyError: {e}")

    print("\nTesting working case...")
    test_config_node_from_graph_node_with_dict()
    print("SUCCESS: Dict attributes work fine")
