#!/usr/bin/env python3
"""
Test script to verify edge queries work.
"""
from ciris_engine.logic.persistence import initialize_database
from ciris_engine.logic.persistence.models.graph import get_edges_for_node
from ciris_engine.schemas.services.graph_core import GraphScope

# Initialize database
initialize_database()

# Test querying edges
def test_edge_queries():
    """Test that we can query edges."""
    
    # Query edges for the agent node
    edges = get_edges_for_node("agent_ciris", GraphScope.IDENTITY)
    print(f"Edges for agent_ciris (IDENTITY scope): {len(edges)}")
    for edge in edges:
        print(f"  {edge.source} -> {edge.target}: {edge.relationship} (weight: {edge.weight})")
    
    # Query edges for the agent node in LOCAL scope
    edges = get_edges_for_node("agent_ciris", GraphScope.LOCAL)
    print(f"\nEdges for agent_ciris (LOCAL scope): {len(edges)}")
    for edge in edges:
        print(f"  {edge.source} -> {edge.target}: {edge.relationship} (weight: {edge.weight})")
    
    # Query edges for user node
    edges = get_edges_for_node("user_alice", GraphScope.LOCAL)
    print(f"\nEdges for user_alice: {len(edges)}")
    for edge in edges:
        print(f"  {edge.source} -> {edge.target}: {edge.relationship} (weight: {edge.weight})")

if __name__ == "__main__":
    test_edge_queries()