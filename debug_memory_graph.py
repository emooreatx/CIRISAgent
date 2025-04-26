#!/usr/bin/env python3
"""
Debug script for CirisMemoryGraph with python-arango
This script creates a sample memory graph with reasoning steps and retrieves information.
Incorporates examples from python-arango PyPI documentation.
"""

import os
import sys
import uuid
import datetime
from pprint import pprint
import time

from arango import ArangoClient


def main():
    print("=== CIRIS Memory Graph Debug Tool ===")
    
    # Configure environment variables if not set
    password = os.environ.get("ARANGO_PASSWORD", "cirispassword")
    username = os.environ.get("ARANGO_USERNAME", "root")
    
    # Initialize the ArangoDB client
    client = ArangoClient(hosts="http://localhost:8529")
    
    # Connect to system database
    try:
        sys_db = client.db("_system", username=username, password=password)
        print("Connected to ArangoDB system database")
    except Exception as e:
        print(f"Error connecting to ArangoDB: {str(e)}")
        print("Make sure ArangoDB is running using the run_arango.sh script")
        sys.exit(1)
    
    # Create a new database for our debugging
    db_name = "ciris_debug"
    if sys_db.has_database(db_name):
        print(f"Database {db_name} already exists, dropping it for fresh debug...")
        sys_db.delete_database(db_name)
    
    sys_db.create_database(db_name)
    print(f"Created database: {db_name}")
    
    # Connect to the new database
    db = client.db(db_name, username=username, password=password)
    
    # Create collections for nodes and edges
    if not db.has_collection("nodes"):
        nodes = db.create_collection("nodes")
        print("Created 'nodes' collection")
    else:
        nodes = db.collection("nodes")
    
    if not db.has_collection("edges"):
        edges = db.create_collection("edges", edge=True)  # Use edge=True parameter to create an edge collection
        print("Created 'edges' collection")
    else:
        edges = db.collection("edges")
    
    # Create graph if it doesn't exist
    graph_name = "reasoning_graph"
    if not db.has_graph(graph_name):
        graph = db.create_graph(
            graph_name,
            edge_definitions=[
                {
                    "edge_collection": "edges",
                    "from_vertex_collections": ["nodes"],
                    "to_vertex_collections": ["nodes"]
                }
            ]
        )
        print(f"Created graph: {graph_name}")
    else:
        graph = db.graph(graph_name)
    
    # Get vertex and edge collections from the graph
    nodes_collection = graph.vertex_collection("nodes")
    edges_collection = graph.edge_collection("edges")
    
    # Create the core identity node (root of the graph)
    root_id = str(uuid.uuid4())
    core_node = {
        "_key": root_id,
        "type": "core_identity",
        "timestamp": datetime.datetime.utcnow().isoformat(),
        "tags": ["Integrity", "Continuity"],
        "description": "CIRIS Core Identity" 
    }
    
    nodes_collection.insert(core_node)
    latest_node_id = root_id
    print(f"Created core identity node with ID: {root_id}")
    
    # Function to record a reasoning step
    def record_step(input_data, output_data, ethical_tags, pdma_decision, parent_id=None):
        node_id = str(uuid.uuid4())
        
        # Create node document
        node_data = {
            "_key": node_id,
            "type": "reasoning_step",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "input": input_data,
            "output": output_data,
            "tags": ethical_tags,
            "pdma": pdma_decision
        }
        
        # Insert the node
        nodes_collection.insert(node_data)
        
        # Create edge from parent to this node
        parent = parent_id or latest_node_id
        edge_data = {
            "_from": f"nodes/{parent}",
            "_to": f"nodes/{node_id}",
            "relation": "causal",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Insert the edge
        edges_collection.insert(edge_data)
        
        return node_id
    
    # Function to create a branch
    def create_branch(from_node_id):
        branch_id = str(uuid.uuid4())
        
        # Create branch marker node
        node_data = {
            "_key": branch_id,
            "type": "branch_marker",
            "timestamp": datetime.datetime.utcnow().isoformat(),
            "tags": ["Branch"],
            "description": "Alternative reasoning path"
        }
        
        # Insert the node
        nodes_collection.insert(node_data)
        
        # Create edge from parent to branch
        edge_data = {
            "_from": f"nodes/{from_node_id}",
            "_to": f"nodes/{branch_id}",
            "relation": "fork",
            "timestamp": datetime.datetime.utcnow().isoformat()
        }
        
        # Insert the edge
        edges_collection.insert(edge_data)
        
        return branch_id
    
    # Insert sample reasoning steps
    print("\nInserting sample reasoning steps...")
    
    # First reasoning step
    step1_id = record_step(
        input_data="Is it ethical to use customer data for training AI models?",
        output_data="It depends on several factors including consent, anonymization, and purpose.",
        ethical_tags=["Privacy", "Transparency", "Consent"],
        pdma_decision="Proceed with caution: require explicit consent and anonymization"
    )
    latest_node_id = step1_id
    print(f"Created first reasoning step with ID: {step1_id}")
    
    # Second reasoning step (follows from first)
    step2_id = record_step(
        input_data="What specific anonymization techniques should be applied?",
        output_data="Use differential privacy, remove PII, and ensure k-anonymity compliance.",
        ethical_tags=["Privacy", "Security", "Fairness"],
        pdma_decision="Implement differential privacy to protect individual data",
        parent_id=step1_id
    )
    latest_node_id = step2_id
    print(f"Created second reasoning step with ID: {step2_id}")
    
    # Create a branch (alternative path)
    branch_id = create_branch(from_node_id=step1_id)
    latest_node_id = branch_id
    print(f"Created branch with ID: {branch_id}")
    
    # Step in alternative branch
    step3_id = record_step(
        input_data="What if we cannot get explicit consent from all users?",
        output_data="Consider legal bases like legitimate interest, but with stronger anonymization.",
        ethical_tags=["Compliance", "Transparency"],
        pdma_decision="Defer: consult with legal team to ensure GDPR compliance",
        parent_id=branch_id
    )
    latest_node_id = step3_id
    print(f"Created step in alternative branch with ID: {step3_id}")
    
    # Step with potential ethical drift
    step4_id = record_step(
        input_data="Can we maximize model accuracy by keeping some identifiable information?",
        output_data="Keeping identifiable information increases risk substantially.",
        ethical_tags=["Efficacy", "Utility"],  # Note the absence of Privacy tag
        pdma_decision="Avoid: potential ethical risks outweigh performance benefits",
        parent_id=step3_id
    )
    latest_node_id = step4_id
    print(f"Created step with potential drift with ID: {step4_id}")
    
    # Now let's demonstrate some python-arango graph queries
    print("\n=== Graph Traversal Examples ===")
    
    # Example 1: Find the path from root to latest node
    print("\nFind path from core identity to latest node:")
    
    # Using AQL (ArangoDB Query Language)
    aql = """
    FOR v, e, p IN 1..10 OUTBOUND @start_vertex GRAPH @graph_name
        FILTER v._key == @target
        RETURN p
    """
    
    cursor = db.aql.execute(
        aql,
        bind_vars={
            'start_vertex': f'nodes/{root_id}',
            'graph_name': graph_name,
            'target': latest_node_id
        }
    )
    
    # Process and print the path
    paths = list(cursor)
    if paths:
        print("\nPath found:")
        path = paths[0]  # Take the first path
        for i, vertex in enumerate(path['vertices']):
            print(f"  Node {i+1}: {vertex['_key']} - Type: {vertex['type']}")
            if 'pdma' in vertex:
                print(f"    PDMA: {vertex['pdma']}")
            if i < len(path['edges']):
                print(f"    ↓ {path['edges'][i]['relation']} ↓")
    else:
        print("No path found")
    
    # Example 2: Find all reasoning steps with a specific tag
    print("\nFind all nodes with 'Privacy' tag:")
    aql = """
    FOR doc IN nodes
        FILTER 'Privacy' IN doc.tags
        RETURN doc
    """
    
    cursor = db.aql.execute(aql)
    privacy_nodes = list(cursor)
    
    print(f"Found {len(privacy_nodes)} nodes with Privacy tag:")
    for i, node in enumerate(privacy_nodes):
        print(f"  {i+1}. {node['_key']} - Input: {node['input'][:50]}...")
    
    # Example 3: Find nodes that might have ethical drift
    # This is a simplified version - in real app would use vector similarity
    print("\nFinding nodes with potential ethical drift:")
    aql = """
    LET core = (
        FOR doc IN nodes
            FILTER doc.type == 'core_identity'
            RETURN doc
    )[0]
    
    FOR node IN nodes
        FILTER node.type == 'reasoning_step'
        LET core_tags = core.tags
        LET node_tags = node.tags
        LET common_tags = LENGTH(
            FOR tag IN core_tags
                FILTER tag IN node_tags
                RETURN tag
        )
        LET core_tags_length = LENGTH(core_tags)
        LET node_tags_length = LENGTH(node_tags)
        LET max_length = core_tags_length > node_tags_length ? core_tags_length : node_tags_length
        LET similarity = common_tags / max_length
        FILTER similarity < 0.3
        RETURN {
            node: node,
            similarity: similarity
        }
    """
    
    cursor = db.aql.execute(aql)
    drifted_nodes = list(cursor)
    
    if drifted_nodes:
        print(f"Found {len(drifted_nodes)} nodes with potential ethical drift:")
        for i, item in enumerate(drifted_nodes):
            node = item['node']
            print(f"  {i+1}. {node['_key']} - Similarity: {item['similarity']}")
            print(f"     Tags: {node['tags']}")
            print(f"     PDMA: {node['pdma']}")
    else:
        print("No nodes with significant ethical drift found")
    
    # Example 4: Get all reasoning steps in chronological order
    print("\nAll reasoning steps in chronological order:")
    aql = """
    FOR doc IN nodes
        FILTER doc.type == 'reasoning_step'
        SORT doc.timestamp
        RETURN doc
    """
    
    cursor = db.aql.execute(aql)
    steps = list(cursor)
    
    print(f"Found {len(steps)} reasoning steps:")
    for i, step in enumerate(steps):
        timestamp = step['timestamp'].split('T')[0]
        print(f"  {i+1}. [{timestamp}] {step['_key']}: {step['pdma'][:50]}...")
    
    print("\nDebug completed successfully")
    client.close()

def test_memory_graph():
    """Function to test all methods of the CirisMemoryGraph class"""
    print("\n=== Testing CirisMemoryGraph Methods ===")
    
    # Import the CirisMemoryGraph class
    try:
        from memory_graph import CirisMemoryGraph
        print("Successfully imported CirisMemoryGraph")
    except ImportError as e:
        print(f"Error importing CirisMemoryGraph: {e}")
        return
    
    # Initialize the memory graph with a test database
    test_db_name = "ciris_test_db"
    print(f"\nInitializing CirisMemoryGraph with test database: {test_db_name}")
    try:
        memory = CirisMemoryGraph(db_name=test_db_name)
        print("✓ __init__ method works")
    except Exception as e:
        print(f"Error initializing CirisMemoryGraph: {e}")
        return
    
    # Test 1: Record a step
    print("\nTest 1: Testing record_step method")
    try:
        step1_id = memory.record_step(
            input_data="Is processing user data ethical?",
            output_data="It depends on consent and transparency.",
            ethical_tags=["Privacy", "Consent", "Transparency"],
            pdma_decision="Proceed with clear consent mechanisms"
        )
        print(f"✓ record_step method works - created node {step1_id}")
    except Exception as e:
        print(f"Error in record_step: {e}")
    
    # Test 2: Record another step to build the graph
    try:
        step2_id = memory.record_step(
            input_data="How should we implement consent?",
            output_data="Use opt-in mechanisms with clear explanations.",
            ethical_tags=["Consent", "Transparency", "Autonomy"],
            pdma_decision="Implement granular opt-in consent"
        )
        print(f"✓ record_step method works with chain - created node {step2_id}")
    except Exception as e:
        print(f"Error in second record_step: {e}")
    
    # Test 3: Create a branch
    print("\nTest 3: Testing branch method")
    try:
        branch_id = memory.branch(from_node=step1_id)
        print(f"✓ branch method works - created branch {branch_id}")
    except Exception as e:
        print(f"Error in branch: {e}")
        
    # Test 4: Record a step in the branch
    try:
        step3_id = memory.record_step(
            input_data="What if users don't consent?",
            output_data="We must provide alternative services or clear explanation.",
            ethical_tags=["Fairness", "Transparency"],
            pdma_decision="Create alternative service path",
            parent=branch_id
        )
        print(f"✓ record_step with parent parameter works - created node {step3_id}")
    except Exception as e:
        print(f"Error in record_step with parent: {e}")
    
    # Test 5: Detect ethical drift
    print("\nTest 5: Testing detect_drift method")
    try:
        # Add a step with potential drift
        drift_step_id = memory.record_step(
            input_data="Can we maximize data collection?",
            output_data="More data improves model performance.",
            ethical_tags=["Efficacy", "Utility"],  # Note: missing Privacy/Consent
            pdma_decision="Expand data collection scope",
            parent=step3_id
        )
        
        # Now detect drift
        drifted_nodes = memory.detect_drift(threshold=0.6)
        print(f"✓ detect_drift method works - found {len(drifted_nodes)} drifted nodes")
        if drifted_nodes:
            print(f"  Most drifted: {drifted_nodes[0]['node_id']} with similarity {drifted_nodes[0]['similarity']:.3f}")
    except Exception as e:
        print(f"Error in detect_drift: {e}")
    
    # Test 6: Get path between nodes
    print("\nTest 6: Testing get_path method")
    try:
        path = memory.get_path(step1_id, step2_id)
        print(f"✓ get_path method works - path has {len(path)} nodes")
        print(f"  Path: {' -> '.join(path)}")
    except Exception as e:
        print(f"Error in get_path: {e}")
    
    # Test 7: Get recent steps
    print("\nTest 7: Testing get_recent_steps method")
    try:
        recent = memory.get_recent_steps(count=3)
        print(f"✓ get_recent_steps method works - got {len(recent)} steps")
        if recent:
            print(f"  Most recent step: {recent[0]['_key']}")
    except Exception as e:
        print(f"Error in get_recent_steps: {e}")
    
    # Test 8: Get steps by tag
    print("\nTest 8: Testing get_steps_by_tag method")
    try:
        transparency_steps = memory.get_steps_by_tag("Transparency")
        print(f"✓ get_steps_by_tag method works - found {len(transparency_steps)} steps with 'Transparency' tag")
    except Exception as e:
        print(f"Error in get_steps_by_tag: {e}")
    
    # Test 9: Get steps since deferral
    print("\nTest 9: Testing get_steps_since_deferral method")
    try:
        since_branch = memory.get_steps_since_deferral()
        print(f"✓ get_steps_since_deferral method works - found {len(since_branch)} steps since last branch")
    except Exception as e:
        print(f"Error in get_steps_since_deferral: {e}")
    
    # Test 10: Export to NetworkX
    print("\nTest 10: Testing export_to_networkx method")
    try:
        nx_graph = memory.export_to_networkx()
        print(f"✓ export_to_networkx method works - graph has {nx_graph.number_of_nodes()} nodes and {nx_graph.number_of_edges()} edges")
    except Exception as e:
        print(f"Error in export_to_networkx: {e}")
    
    # Test 11: Visualize (if matplotlib and graphviz are available)
    print("\nTest 11: Testing visualize method")
    try:
        memory.visualize(path="ciris_test_graph.png")
        print("✓ visualize method completed (check for image file)")
    except Exception as e:
        print(f"Note: visualize method requires matplotlib and graphviz: {e}")
    
    # Test 12: Persist and close
    print("\nTest 12: Testing persist and close methods")
    try:
        memory.persist()
        print("✓ persist method works")
        memory.close()
        print("✓ close method works")
    except Exception as e:
        print(f"Error in persist/close: {e}")
    
    print("\nAll CirisMemoryGraph tests completed")

if __name__ == "__main__":
    # main()
    # Comment out the line below to run only the main debug script without tests
    test_memory_graph()