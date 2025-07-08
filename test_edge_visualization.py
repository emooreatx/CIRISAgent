#!/usr/bin/env python3
"""
Test script to create some nodes and edges, then visualize them.
"""
import asyncio
import json
from datetime import datetime, timezone
from ciris_engine.logic.persistence import initialize_database, get_db_connection
from ciris_engine.logic.persistence.models.graph import add_graph_node, add_graph_edge
from ciris_engine.schemas.services.graph_core import GraphNode, GraphEdge, NodeType, GraphScope
from ciris_engine.logic.services.time import LocalTimeService

# Initialize database
initialize_database()

# Create time service
time_service = LocalTimeService()

async def create_test_data():
    """Create some test nodes and edges."""
    
    # Create nodes
    nodes = [
        GraphNode(
            id="agent_ciris",
            type=NodeType.AGENT,
            scope=GraphScope.IDENTITY,
            attributes={"name": "CIRIS", "role": "Assistant"},
            updated_by="system",
            updated_at=datetime.now(timezone.utc)
        ),
        GraphNode(
            id="user_alice",
            type=NodeType.USER,
            scope=GraphScope.LOCAL,
            attributes={"name": "Alice", "active": True},
            updated_by="system",
            updated_at=datetime.now(timezone.utc)
        ),
        GraphNode(
            id="channel_general",
            type=NodeType.CHANNEL,
            scope=GraphScope.LOCAL,
            attributes={"name": "General", "platform": "Discord"},
            updated_by="system",
            updated_at=datetime.now(timezone.utc)
        ),
        GraphNode(
            id="concept_helpfulness",
            type=NodeType.CONCEPT,
            scope=GraphScope.IDENTITY,
            attributes={"name": "Helpfulness", "priority": "high"},
            updated_by="system",
            updated_at=datetime.now(timezone.utc)
        ),
        GraphNode(
            id="observation_greeting",
            type=NodeType.OBSERVATION,
            scope=GraphScope.LOCAL,
            attributes={"content": "User greeted the agent", "timestamp": datetime.now(timezone.utc).isoformat()},
            updated_by="system",
            updated_at=datetime.now(timezone.utc)
        )
    ]
    
    # Add nodes to database
    for node in nodes:
        add_graph_node(node, time_service)
        print(f"Added node: {node.id}")
    
    # Create edges
    edges = [
        GraphEdge(
            source="agent_ciris",
            target="concept_helpfulness",
            relationship="embodies",
            scope=GraphScope.IDENTITY,
            weight=0.9,
            attributes={"context": "Core value"}
        ),
        GraphEdge(
            source="user_alice",
            target="channel_general",
            relationship="participates_in",
            scope=GraphScope.LOCAL,
            weight=0.7,
            attributes={"context": "Active member"}
        ),
        GraphEdge(
            source="observation_greeting",
            target="user_alice",
            relationship="created_by",
            scope=GraphScope.LOCAL,
            weight=1.0,
            attributes={"context": "Direct observation"}
        ),
        GraphEdge(
            source="agent_ciris",
            target="observation_greeting",
            relationship="responds_to",
            scope=GraphScope.LOCAL,
            weight=0.8,
            attributes={"context": "Polite response"}
        ),
        GraphEdge(
            source="channel_general",
            target="agent_ciris",
            relationship="contains",
            scope=GraphScope.LOCAL,
            weight=0.6,
            attributes={"context": "Agent is present in channel"}
        )
    ]
    
    # Add edges to database
    for edge in edges:
        add_graph_edge(edge)
        print(f"Added edge: {edge.source} -> {edge.target} ({edge.relationship})")
    
    print("\nTest data created successfully!")
    print("\nTo visualize the graph, use the API endpoint:")
    print("GET http://localhost:8080/v1/memory/visualize/graph")
    print("\nWith parameters:")
    print("- layout=force (or timeline, hierarchical)")
    print("- include_metrics=false")
    print("- limit=50")

if __name__ == "__main__":
    asyncio.run(create_test_data())