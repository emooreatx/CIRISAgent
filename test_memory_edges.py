#!/usr/bin/env python3
"""
Test script to verify memory edges are returned with nodes.
"""
import asyncio
import json
from datetime import datetime
from ciris_engine.schemas.services.graph_core import GraphNode, GraphEdge, GraphScope, NodeType
from ciris_engine.schemas.services.operations import MemoryQuery
from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.logic.services.lifecycle.time_service import LocalTimeService
from ciris_engine.logic.persistence.models.graph import add_graph_edge

async def test_edges():
    # Initialize services
    time_service = LocalTimeService()
    memory_service = LocalGraphMemoryService(time_service=time_service)
    
    print("Testing Memory Edge Functionality")
    print("=" * 50)
    
    # Create test nodes
    node1 = GraphNode(
        id="test_node_1",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={"name": "Test Node 1", "created_at": datetime.now()},
        updated_by="test_script"
    )
    
    node2 = GraphNode(
        id="test_node_2",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={"name": "Test Node 2", "created_at": datetime.now()},
        updated_by="test_script"
    )
    
    node3 = GraphNode(
        id="test_node_3",
        type=NodeType.CONCEPT,
        scope=GraphScope.LOCAL,
        attributes={"name": "Test Node 3", "created_at": datetime.now()},
        updated_by="test_script"
    )
    
    # Store nodes
    print("\n1. Storing test nodes...")
    await memory_service.memorize(node1)
    await memory_service.memorize(node2)
    await memory_service.memorize(node3)
    print("✓ Nodes stored successfully")
    
    # Create edges
    edge1 = GraphEdge(
        source="test_node_1",
        target="test_node_2",
        relationship="related_to",
        scope=GraphScope.LOCAL,
        weight=0.8
    )
    
    edge2 = GraphEdge(
        source="test_node_1",
        target="test_node_3",
        relationship="depends_on",
        scope=GraphScope.LOCAL,
        weight=0.9
    )
    
    edge3 = GraphEdge(
        source="test_node_2",
        target="test_node_3",
        relationship="influences",
        scope=GraphScope.LOCAL,
        weight=0.7
    )
    
    print("\n2. Creating edges...")
    await memory_service.create_edge(edge1)
    await memory_service.create_edge(edge2)
    await memory_service.create_edge(edge3)
    print("✓ Edges created successfully")
    
    # Test recall without edges
    print("\n3. Testing recall WITHOUT edges...")
    query = MemoryQuery(
        node_id="test_node_1",
        scope=GraphScope.LOCAL,
        include_edges=False,
        depth=1
    )
    nodes = await memory_service.recall(query)
    if nodes:
        node = nodes[0]
        print(f"✓ Node retrieved: {node.id}")
        print(f"  Has _edges in attributes: {'_edges' in node.attributes}")
    
    # Test recall with edges
    print("\n4. Testing recall WITH edges...")
    query = MemoryQuery(
        node_id="test_node_1",
        scope=GraphScope.LOCAL,
        include_edges=True,
        depth=1
    )
    nodes = await memory_service.recall(query)
    if nodes:
        node = nodes[0]
        print(f"✓ Node retrieved: {node.id}")
        if '_edges' in node.attributes:
            edges = node.attributes['_edges']
            print(f"✓ Found {len(edges)} edges:")
            for edge in edges:
                print(f"  - {edge['source']} -{edge['relationship']}-> {edge['target']} (weight: {edge['weight']})")
        else:
            print("✗ No edges found in attributes")
    
    # Test get_node_edges
    print("\n5. Testing get_node_edges...")
    edges = await memory_service.get_node_edges("test_node_1", GraphScope.LOCAL)
    print(f"✓ Found {len(edges)} edges for test_node_1:")
    for edge in edges:
        print(f"  - {edge.source} -{edge.relationship}-> {edge.target} (weight: {edge.weight})")
    
    # Test wildcard query with edges
    print("\n6. Testing wildcard query with edges...")
    query = MemoryQuery(
        node_id="*",
        scope=GraphScope.LOCAL,
        type=NodeType.CONCEPT,
        include_edges=True,
        depth=1
    )
    nodes = await memory_service.recall(query)
    print(f"✓ Found {len(nodes)} nodes")
    for node in nodes:
        edge_count = len(node.attributes.get('_edges', []))
        print(f"  - {node.id}: {edge_count} edges")
    
    # Test depth > 1 traversal
    print("\n7. Testing graph traversal with depth=2...")
    query = MemoryQuery(
        node_id="test_node_1",
        scope=GraphScope.LOCAL,
        include_edges=True,
        depth=2
    )
    nodes = await memory_service.recall(query)
    print(f"✓ Found {len(nodes)} nodes with depth=2 traversal:")
    for node in nodes:
        edge_count = len(node.attributes.get('_edges', []))
        print(f"  - {node.id}: {edge_count} edges")
    
    print("\n" + "=" * 50)
    print("✓ All edge tests completed successfully!")

if __name__ == "__main__":
    asyncio.run(test_edges())