#!/usr/bin/env python3
"""Test memory query functionality with wildcards, type filters, and text search."""

import asyncio
import json
import requests
from datetime import datetime, timezone

# Configuration
API_URL = "http://localhost:8080/v1"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"

# Test data
TEST_NODES = [
    {
        "id": "concept_ai_ethics",
        "type": "concept",
        "scope": "local",
        "attributes": {
            "title": "AI Ethics",
            "description": "Ethical considerations in artificial intelligence",
            "tags": ["ethics", "ai", "philosophy"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "test_script"
        }
    },
    {
        "id": "fact_machine_learning",
        "type": "concept",  # Using concept since FACT is not a valid type
        "scope": "local", 
        "attributes": {
            "title": "Machine Learning Basics",
            "content": "Machine learning is a subset of artificial intelligence",
            "confidence": 0.95,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "created_by": "test_script"
        }
    },
    {
        "id": "observation_user_behavior",
        "type": "observation",
        "scope": "environment",  # Using environment instead of INTERACTION
        "attributes": {
            "subject": "User interaction patterns",
            "details": "Users prefer concise responses",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "created_by": "test_script"
        }
    }
]

def login():
    """Login and get auth token."""
    response = requests.post(
        f"{API_URL}/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    )
    response.raise_for_status()
    return response.json()["access_token"]

def store_test_nodes(token):
    """Store test nodes in memory."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("Storing test nodes...")
    for node in TEST_NODES:
        response = requests.post(
            f"{API_URL}/memory/store",
            headers=headers,
            json={"node": node}
        )
        if response.status_code == 200:
            print(f"✓ Stored node: {node['id']}")
        else:
            print(f"✗ Failed to store {node['id']}: {response.text}")

def test_wildcard_queries(token):
    """Test wildcard queries."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Testing Wildcard Queries ===")
    
    # Test 1: Get all nodes with wildcard
    print("\n1. Testing wildcard query (node_id='*')...")
    response = requests.post(
        f"{API_URL}/memory/query",
        headers=headers,
        json={"node_id": "*", "limit": 10}
    )
    
    if response.status_code == 200:
        nodes = response.json()["data"]
        print(f"✓ Found {len(nodes)} nodes with wildcard query")
        for node in nodes[:3]:  # Show first 3
            print(f"  - {node['id']} ({node['type']})")
    else:
        print(f"✗ Wildcard query failed: {response.text}")

def test_type_queries(token):
    """Test type-based queries."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Testing Type-based Queries ===")
    
    # Test 1: Query by type only
    print("\n1. Testing type filter (type='concept')...")
    response = requests.post(
        f"{API_URL}/memory/query",
        headers=headers,
        json={"type": "concept", "limit": 10}
    )
    
    if response.status_code == 200:
        nodes = response.json()["data"]
        print(f"✓ Found {len(nodes)} concept nodes")
        for node in nodes:
            print(f"  - {node['id']}: {node.get('attributes', {}).get('title', 'No title')}")
    else:
        print(f"✗ Type query failed: {response.text}")
    
    # Test 2: Query by type with scope
    print("\n2. Testing type + scope filter (type='observation', scope='environment')...")
    response = requests.post(
        f"{API_URL}/memory/query",
        headers=headers,
        json={"type": "observation", "scope": "environment", "limit": 10}
    )
    
    if response.status_code == 200:
        nodes = response.json()["data"]
        print(f"✓ Found {len(nodes)} observation nodes in environment scope")
        for node in nodes:
            print(f"  - {node['id']}: {node.get('attributes', {}).get('subject', 'No subject')}")
    else:
        print(f"✗ Type+scope query failed: {response.text}")

def test_text_search(token):
    """Test text search queries."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Testing Text Search ===")
    
    # Test 1: Search for "ethics"
    print("\n1. Testing text search (query='ethics')...")
    response = requests.post(
        f"{API_URL}/memory/query",
        headers=headers,
        json={"query": "ethics", "limit": 10}
    )
    
    if response.status_code == 200:
        nodes = response.json()["data"]
        print(f"✓ Found {len(nodes)} nodes containing 'ethics'")
        for node in nodes:
            attrs = node.get('attributes', {})
            print(f"  - {node['id']}: {attrs.get('title') or attrs.get('description', 'No description')}")
    else:
        print(f"✗ Text search failed: {response.text}")
    
    # Test 2: Search with type filter
    print("\n2. Testing text search with type filter (query='artificial', type='concept')...")
    response = requests.post(
        f"{API_URL}/memory/query",
        headers=headers,
        json={"query": "artificial", "type": "concept", "limit": 10}
    )
    
    if response.status_code == 200:
        nodes = response.json()["data"]
        print(f"✓ Found {len(nodes)} concept nodes containing 'artificial'")
        for node in nodes:
            print(f"  - {node['id']}: {node.get('attributes', {}).get('content', 'No content')}")
    else:
        print(f"✗ Text search with type failed: {response.text}")

def test_timeline_view(token):
    """Test timeline endpoint."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Testing Timeline View ===")
    
    response = requests.get(
        f"{API_URL}/memory/timeline?hours=24&bucket_size=hour",
        headers=headers
    )
    
    if response.status_code == 200:
        data = response.json()["data"]
        print(f"✓ Timeline query successful")
        print(f"  - Total memories: {data['total']}")
        print(f"  - Time buckets: {len(data['buckets'])}")
        print(f"  - Recent memories: {len(data['memories'])}")
    else:
        print(f"✗ Timeline query failed: {response.text}")

def test_direct_recall(token):
    """Test direct node recall."""
    headers = {"Authorization": f"Bearer {token}"}
    
    print("\n=== Testing Direct Recall ===")
    
    node_id = "concept_ai_ethics"
    response = requests.get(
        f"{API_URL}/memory/{node_id}",
        headers=headers
    )
    
    if response.status_code == 200:
        node = response.json()["data"]
        print(f"✓ Direct recall successful for {node_id}")
        print(f"  - Type: {node['type']}")
        print(f"  - Title: {node.get('attributes', {}).get('title', 'No title')}")
        print(f"  - Tags: {node.get('attributes', {}).get('tags', [])}")
    else:
        print(f"✗ Direct recall failed: {response.text}")

def main():
    """Run all memory query tests."""
    print("Memory Query Test Suite")
    print("=" * 50)
    
    # Login
    print("Logging in...")
    token = login()
    print(f"✓ Login successful")
    
    # Store test nodes
    store_test_nodes(token)
    
    # Wait a moment for nodes to be indexed
    import time
    time.sleep(1)
    
    # Run tests
    test_wildcard_queries(token)
    test_type_queries(token)
    test_text_search(token)
    test_timeline_view(token)
    test_direct_recall(token)
    
    print("\n" + "=" * 50)
    print("Test suite completed!")

if __name__ == "__main__":
    main()