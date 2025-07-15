"""
Comprehensive tests for the node registry functionality.

Tests cover:
- Node type registration and lookup
- Automatic registration via decorator
- Serialization/deserialization through registry
- Error handling for invalid nodes
- Registry state management
- Performance with many node types
"""
import pytest
from typing import Type, Dict, Any, Optional, List
from datetime import datetime, timezone
from pydantic import Field, BaseModel

from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.services.graph_typed_nodes import (
    TypedGraphNode,
    NodeTypeRegistry,
    register_node_type,
)


class TestNodeRegistryCore:
    """Test core node registry functionality."""

    def setup_method(self):
        """Clear registry before each test."""
        # Save current registry state
        self.saved_registry = NodeTypeRegistry._registry.copy()
        NodeTypeRegistry._registry.clear()

    def teardown_method(self):
        """Restore registry after each test."""
        NodeTypeRegistry._registry = self.saved_registry

    def test_register_simple_node(self):
        """Test registering a simple node type."""
        @register_node_type("SIMPLE_TEST")
        class SimpleNode(TypedGraphNode):
            test_field: str = Field(default="test")
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or "simple",
                    type="SIMPLE_TEST",
                    scope=self.scope,
                    attributes={"test_field": self.test_field}
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'SimpleNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    test_field=attrs.get("test_field", "test")
                )
        
        # Verify registration
        assert NodeTypeRegistry.get("SIMPLE_TEST") is not None
        assert NodeTypeRegistry.get("SIMPLE_TEST").__name__ == "SimpleNode"

    def test_register_multiple_nodes(self):
        """Test registering multiple node types."""
        node_types = ["TYPE_A", "TYPE_B", "TYPE_C"]
        registered_classes = []
        
        for node_type in node_types:
            # Create class dynamically
            class_name = f"Node{node_type}"
            
            def make_to_graph_node(nt):
                def to_graph_node(self) -> GraphNode:
                    return GraphNode(
                        id=self.id or nt.lower(),
                        type=nt,
                        scope=self.scope,
                        attributes={}
                    )
                return to_graph_node
            
            def make_from_graph_node(nt):
                @classmethod
                def from_graph_node(cls, node: GraphNode):
                    return cls(id=node.id, type=node.type, scope=node.scope)
                return from_graph_node
            
            # Create class
            node_class = type(class_name, (TypedGraphNode,), {
                'to_graph_node': make_to_graph_node(node_type),
                'from_graph_node': make_from_graph_node(node_type),
            })
            
            # Register it
            NodeTypeRegistry.register(node_type, node_class)
            registered_classes.append(node_class)
        
        # Verify all registered
        for node_type in node_types:
            assert NodeTypeRegistry.get(node_type) is not None

    def test_duplicate_registration_error(self):
        """Test that duplicate registration raises error."""
        # Register first time
        @register_node_type("DUPLICATE")
        class FirstNode(TypedGraphNode):
            def to_graph_node(self) -> GraphNode:
                return GraphNode(id="first", type="DUPLICATE", scope=GraphScope.LOCAL, attributes={})
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'FirstNode':
                return cls()
        
        # Try to register again
        with pytest.raises(ValueError) as exc_info:
            @register_node_type("DUPLICATE")
            class SecondNode(TypedGraphNode):
                def to_graph_node(self) -> GraphNode:
                    return GraphNode(id="second", type="DUPLICATE", scope=GraphScope.LOCAL, attributes={})
                
                @classmethod
                def from_graph_node(cls, node: GraphNode) -> 'SecondNode':
                    return cls()
        
        assert "already registered" in str(exc_info.value)

    def test_get_unregistered_type(self):
        """Test getting an unregistered type returns None."""
        result = NodeTypeRegistry.get("UNREGISTERED_TYPE")
        assert result is None

    def test_manual_registration(self):
        """Test manual registration without decorator."""
        class ManualNode(TypedGraphNode):
            manual_field: int = Field(default=42)
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or "manual",
                    type="MANUAL",
                    scope=self.scope,
                    attributes={"manual_field": self.manual_field}
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'ManualNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    manual_field=attrs.get("manual_field", 42)
                )
        
        # Register manually
        NodeTypeRegistry.register("MANUAL", ManualNode)
        
        # Verify
        assert NodeTypeRegistry.get("MANUAL") == ManualNode

    def test_registration_validation(self):
        """Test that registration validates required methods."""
        # Class without to_graph_node
        class BadNode1:
            @classmethod
            def from_graph_node(cls, node: GraphNode):
                pass
        
        with pytest.raises(ValueError) as exc_info:
            NodeTypeRegistry.register("BAD1", BadNode1)  # type: ignore
        assert "must implement to_graph_node" in str(exc_info.value)
        
        # Class without from_graph_node
        class BadNode2:
            def to_graph_node(self) -> GraphNode:
                pass
        
        with pytest.raises(ValueError) as exc_info:
            NodeTypeRegistry.register("BAD2", BadNode2)  # type: ignore
        assert "must implement from_graph_node" in str(exc_info.value)


class TestNodeDeserialization:
    """Test node deserialization through registry."""

    def setup_method(self):
        """Setup test nodes."""
        self.saved_registry = NodeTypeRegistry._registry.copy()
        NodeTypeRegistry._registry.clear()
        
        # Register test nodes
        @register_node_type("USER")
        class UserNode(TypedGraphNode):
            username: str
            email: str
            created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or f"user_{self.username}",
                    type="USER",
                    scope=self.scope,
                    attributes={
                        "username": self.username,
                        "email": self.email,
                        "created_at": self.created_at.isoformat(),
                        "node_class": "UserNode"
                    }
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'UserNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes,  # Pass through the attributes
                    username=attrs.get("username", ""),
                    email=attrs.get("email", ""),
                    created_at=cls._deserialize_datetime(attrs.get("created_at"))
                )
        
        @register_node_type("METRIC")
        class MetricNode(TypedGraphNode):
            metric_name: str
            value: float
            tags: List[str] = Field(default_factory=list)
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or f"metric_{self.metric_name}",
                    type="METRIC",
                    scope=self.scope,
                    attributes={
                        "metric_name": self.metric_name,
                        "value": self.value,
                        "tags": self.tags,
                        "node_class": "MetricNode"
                    }
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'MetricNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes,  # Pass through the attributes
                    metric_name=attrs.get("metric_name", ""),
                    value=attrs.get("value", 0.0),
                    tags=attrs.get("tags", [])
                )

    def teardown_method(self):
        """Restore registry."""
        NodeTypeRegistry._registry = self.saved_registry

    def test_deserialize_registered_node(self):
        """Test deserializing a registered node type."""
        # Create a generic GraphNode with valid NodeType
        graph_node = GraphNode(
            id="user_123",
            type=NodeType.USER,  # Use enum value
            scope=GraphScope.LOCAL,
            attributes={
                "username": "testuser",
                "email": "test@example.com",
                "created_at": "2025-01-01T12:00:00+00:00",
                "node_class": "UserNode"
            }
        )
        
        # Deserialize through registry
        result = NodeTypeRegistry.deserialize(graph_node)
        
        # Should get back a UserNode
        assert result.__class__.__name__ == "UserNode"
        assert hasattr(result, 'username')
        assert result.username == "testuser"  # type: ignore
        assert result.email == "test@example.com"  # type: ignore

    def test_deserialize_unregistered_node(self):
        """Test deserializing an unregistered node type."""
        # Create a GraphNode with valid but unregistered type
        graph_node = GraphNode(
            id="unknown_123",
            type=NodeType.CONCEPT,  # Valid type but not registered for deserialization
            scope=GraphScope.LOCAL,
            attributes={"some_data": "value"}
        )
        
        # Deserialize
        result = NodeTypeRegistry.deserialize(graph_node)
        
        # Should return the original GraphNode
        assert result is graph_node
        assert isinstance(result, GraphNode)
        assert not hasattr(result, 'some_data')

    def test_deserialize_without_node_class_hint(self):
        """Test deserializing without node_class attribute."""
        # GraphNode without node_class hint
        graph_node = GraphNode(
            id="metric_123",
            type=NodeType.TSDB_DATA,  # Valid type for metrics
            scope=GraphScope.LOCAL,
            attributes={
                "metric_name": "cpu.usage",
                "value": 75.5,
                "tags": ["host:server1"]
                # No node_class attribute
            }
        )
        
        # Deserialize
        result = NodeTypeRegistry.deserialize(graph_node)
        
        # Should still return GraphNode (no node_class hint)
        assert isinstance(result, GraphNode)

    def test_deserialize_with_error_handling(self):
        """Test deserialization handles errors gracefully."""
        # Register a node with OBSERVATION type that will fail deserialization
        @register_node_type(NodeType.OBSERVATION)
        class FailingNode(TypedGraphNode):
            required_field: str  # No default
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or "fail",
                    type=NodeType.OBSERVATION,
                    scope=self.scope,
                    attributes={"node_class": "FailingNode"}
                    # Missing required_field
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'FailingNode':
                # This will fail due to missing required_field
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes
                    # Missing required_field
                )
        
        # Create node that will fail
        graph_node = GraphNode(
            id="fail_123",
            type=NodeType.OBSERVATION,  # Same type as registered
            scope=GraphScope.LOCAL,
            attributes={"node_class": "FailingNode"}
        )
        
        # Deserialize - should fall back to GraphNode
        result = NodeTypeRegistry.deserialize(graph_node)
        
        # Should return original GraphNode due to error
        assert result is graph_node
        assert isinstance(result, GraphNode)


class TestComplexNodeTypes:
    """Test registration and deserialization of complex node types."""

    def setup_method(self):
        """Setup complex test nodes."""
        self.saved_registry = NodeTypeRegistry._registry.copy()
        NodeTypeRegistry._registry.clear()

    def teardown_method(self):
        """Restore registry."""
        NodeTypeRegistry._registry = self.saved_registry

    def test_nested_data_structures(self):
        """Test nodes with nested data structures."""
        @register_node_type(NodeType.OBSERVATION)
        class NestedNode(TypedGraphNode):
            data: Dict[str, Any]
            metadata: Optional[BaseModel] = None
            
            def to_graph_node(self) -> GraphNode:
                attrs = {
                    "data": self.data,
                    "node_class": "NestedNode"
                }
                if self.metadata:
                    attrs["metadata"] = self.metadata.model_dump()
                
                return GraphNode(
                    id=self.id or "nested",
                    type=NodeType.OBSERVATION,  # Use valid type
                    scope=self.scope,
                    attributes=attrs
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'NestedNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes,
                    data=attrs.get("data", {}),
                    metadata=None  # Simplified for test
                )
        
        # Create node with nested data
        node = NestedNode(
            id="nested_test",
            type=NodeType.OBSERVATION,
            scope=GraphScope.LOCAL,
            attributes={},
            data={
                "level1": {
                    "level2": {
                        "values": [1, 2, 3],
                        "flag": True
                    }
                }
            }
        )
        
        # Serialize and deserialize
        graph_node = node.to_graph_node()
        restored = NodeTypeRegistry.deserialize(graph_node)
        
        assert isinstance(restored, NestedNode)
        assert restored.data["level1"]["level2"]["values"] == [1, 2, 3]  # type: ignore

    def test_inheritance_hierarchy(self):
        """Test nodes with inheritance."""
        # Base node type
        class BaseEventNode(TypedGraphNode):
            event_type: str
            timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
            
            def get_base_attrs(self) -> Dict[str, Any]:
                return {
                    "event_type": self.event_type,
                    "timestamp": self.timestamp.isoformat()
                }
        
        # Derived node type
        @register_node_type(NodeType.OBSERVATION)
        class UserEventNode(BaseEventNode):
            user_id: str
            action: str
            
            def to_graph_node(self) -> GraphNode:
                attrs = self.get_base_attrs()
                attrs.update({
                    "user_id": self.user_id,
                    "action": self.action,
                    "node_class": "UserEventNode"
                })
                
                return GraphNode(
                    id=self.id or f"event_{self.user_id}_{self.timestamp.timestamp()}",
                    type=NodeType.OBSERVATION,
                    scope=self.scope,
                    attributes=attrs
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'UserEventNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes,
                    event_type=attrs.get("event_type", ""),
                    timestamp=cls._deserialize_datetime(attrs.get("timestamp")),
                    user_id=attrs.get("user_id", ""),
                    action=attrs.get("action", "")
                )
        
        # Test serialization
        event = UserEventNode(
            id="event_test",
            type=NodeType.OBSERVATION,
            scope=GraphScope.LOCAL,
            attributes={},
            event_type="user_action",
            user_id="user123",
            action="login"
        )
        
        graph_node = event.to_graph_node()
        restored = NodeTypeRegistry.deserialize(graph_node)
        
        assert isinstance(restored, UserEventNode)
        assert restored.user_id == "user123"  # type: ignore
        assert restored.action == "login"  # type: ignore


class TestRegistryPerformance:
    """Test registry performance with many node types."""

    def setup_method(self):
        """Save registry state."""
        self.saved_registry = NodeTypeRegistry._registry.copy()

    def teardown_method(self):
        """Restore registry."""
        NodeTypeRegistry._registry = self.saved_registry

    def test_registry_with_many_types(self):
        """Test registry performance with many registered types."""
        # Register many node types
        num_types = 100
        
        for i in range(num_types):
            node_type = f"TYPE_{i:04d}"
            
            # Create class dynamically
            def make_class(nt, idx):
                class DynamicNode(TypedGraphNode):
                    index: int = Field(default=idx)
                    
                    def to_graph_node(self) -> GraphNode:
                        return GraphNode(
                            id=self.id or f"node_{self.index}",
                            type=nt,
                            scope=self.scope,
                            attributes={"index": self.index, "node_class": f"Dynamic{idx}"}
                        )
                    
                    @classmethod
                    def from_graph_node(cls, node: GraphNode) -> 'DynamicNode':
                        attrs = node.attributes if isinstance(node.attributes, dict) else {}
                        return cls(
                            id=node.id,
                            type=node.type,
                            scope=node.scope,
                            index=attrs.get("index", idx)
                        )
                
                return DynamicNode
            
            node_class = make_class(node_type, i)
            NodeTypeRegistry.register(node_type, node_class)
        
        # Test lookup performance
        import time
        
        # Warm up
        for i in range(10):
            NodeTypeRegistry.get(f"TYPE_{i:04d}")
        
        # Time lookups
        start_time = time.time()
        for _ in range(1000):
            for i in range(0, num_types, 10):
                NodeTypeRegistry.get(f"TYPE_{i:04d}")
        
        elapsed = time.time() - start_time
        
        # Should be fast (dict lookups)
        assert elapsed < 0.1  # 100ms for 10,000 lookups

    def test_deserialization_performance(self):
        """Test deserialization performance."""
        # Register a test node
        @register_node_type(NodeType.OBSERVATION)
        class PerfTestNode(TypedGraphNode):
            counter: int = Field(default=0)
            data: Dict[str, Any] = Field(default_factory=dict)
            
            def to_graph_node(self) -> GraphNode:
                return GraphNode(
                    id=self.id or f"perf_{self.counter}",
                    type=NodeType.OBSERVATION, 
                    scope=self.scope,
                    attributes={
                        "counter": self.counter,
                        "data": self.data,
                        "node_class": "PerfTestNode"
                    }
                )
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'PerfTestNode':
                attrs = node.attributes if isinstance(node.attributes, dict) else {}
                return cls(
                    id=node.id,
                    type=node.type,
                    scope=node.scope,
                    attributes=node.attributes,
                    counter=attrs.get("counter", 0),
                    data=attrs.get("data", {})
                )
        
        # Create many nodes
        graph_nodes = []
        for i in range(100):
            node = PerfTestNode(
                id=f"perf_{i}",
                type=NodeType.OBSERVATION,
                scope=GraphScope.LOCAL,
                attributes={},
                counter=i,
                data={"value": i * 2}
            )
            graph_nodes.append(node.to_graph_node())
        
        # Time deserialization
        import time
        start_time = time.time()
        
        for _ in range(10):
            for graph_node in graph_nodes:
                result = NodeTypeRegistry.deserialize(graph_node)
                assert hasattr(result, 'counter')
        
        elapsed = time.time() - start_time
        
        # Should be reasonably fast
        assert elapsed < 1.0  # 1 second for 1000 deserializations


class TestRegistryEdgeCases:
    """Test edge cases and error conditions."""

    def setup_method(self):
        """Save registry state."""
        self.saved_registry = NodeTypeRegistry._registry.copy()
        NodeTypeRegistry._registry.clear()

    def teardown_method(self):
        """Restore registry."""
        NodeTypeRegistry._registry = self.saved_registry

    def test_empty_registry(self):
        """Test behavior with empty registry."""
        # Clear registry
        NodeTypeRegistry._registry.clear()
        
        # All lookups should return None
        assert NodeTypeRegistry.get("ANY_TYPE") is None
        
        # Deserialization should return original
        graph_node = GraphNode(
            id="test",
            type=NodeType.CONCEPT,
            scope=GraphScope.LOCAL,
            attributes={}
        )
        
        result = NodeTypeRegistry.deserialize(graph_node)
        assert result is graph_node

    def test_register_with_special_characters(self):
        """Test registration with special characters in type name."""
        special_types = [
            "TYPE-WITH-DASHES",
            "TYPE_WITH_UNDERSCORES", 
            "TYPE.WITH.DOTS",
            "TYPE:WITH:COLONS",
            "TYPE/WITH/SLASHES"
        ]
        
        for special_type in special_types:
            @register_node_type(special_type)
            class SpecialNode(TypedGraphNode):
                def to_graph_node(self) -> GraphNode:
                    return GraphNode(
                        id="special",
                        type=special_type,
                        scope=GraphScope.LOCAL,
                        attributes={}
                    )
                
                @classmethod
                def from_graph_node(cls, node: GraphNode) -> 'SpecialNode':
                    return cls()
            
            # Should be registered
            assert NodeTypeRegistry.get(special_type) is not None

    def test_case_sensitivity(self):
        """Test that registry is case-sensitive."""
        @register_node_type("lowercase")
        class LowerNode(TypedGraphNode):
            def to_graph_node(self) -> GraphNode:
                return GraphNode(id="lower", type="lowercase", scope=GraphScope.LOCAL, attributes={})
            
            @classmethod 
            def from_graph_node(cls, node: GraphNode) -> 'LowerNode':
                return cls()
        
        @register_node_type("UPPERCASE")
        class UpperNode(TypedGraphNode):
            def to_graph_node(self) -> GraphNode:
                return GraphNode(id="upper", type="UPPERCASE", scope=GraphScope.LOCAL, attributes={})
            
            @classmethod
            def from_graph_node(cls, node: GraphNode) -> 'UpperNode':
                return cls()
        
        # Different types
        assert NodeTypeRegistry.get("lowercase") != NodeTypeRegistry.get("UPPERCASE")
        assert NodeTypeRegistry.get("Lowercase") is None  # Case matters