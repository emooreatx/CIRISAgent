from ciris_engine.schemas.graph_schemas_v1 import GraphScope, NodeType, GraphNode, GraphEdge

def test_graph_scope_enum():
    assert GraphScope.LOCAL == "local"
    assert GraphScope.ENVIRONMENT == "environment"

def test_node_type_enum():
    assert NodeType.AGENT == "agent"
    assert NodeType.CONCEPT == "concept"

def test_graph_node_minimal():
    node = GraphNode(id="n1", type=NodeType.AGENT, scope=GraphScope.LOCAL)
    assert node.id == "n1"
    assert node.type == NodeType.AGENT
    assert node.scope == GraphScope.LOCAL
    assert node.version == 1
    assert isinstance(node.attributes, dict)

def test_graph_edge_minimal():
    edge = GraphEdge(source="n1", target="n2", relationship="knows", scope=GraphScope.LOCAL)
    assert edge.source == "n1"
    assert edge.target == "n2"
    assert edge.relationship == "knows"
    assert edge.scope == GraphScope.LOCAL
    assert edge.weight == 1.0
    assert isinstance(edge.attributes, dict)
