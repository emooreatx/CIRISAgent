#!/usr/bin/env python3
"""Test to see raw node data including all fields."""

import requests
import json

# Login first
login_response = requests.post(
    "http://localhost:8080/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)

if login_response.status_code != 200:
    print(f"Login failed: {login_response.status_code} - {login_response.text}")
    exit(1)
    
token = login_response.json()["access_token"]
headers = {"Authorization": f"Bearer {token}"}

# Query for recent nodes - use type filter to get some nodes
print("Searching for recent concept nodes...")
search_response = requests.post(
    "http://localhost:8080/v1/memory/query",
    headers=headers,
    json={
        "type": "concept",  # Query by type
        "limit": 10
    }
)

if search_response.status_code == 200:
    memories = search_response.json()["data"]
    print(f"\nFound {len(memories)} memories")
    
    for i, memory in enumerate(memories[:5]):
        print(f"\n{'='*60}")
        print(f"Memory {i+1}:")
        print(f"  ID: {memory.get('id')}")
        print(f"  Type: {memory.get('type')}")
        print(f"  Scope: {memory.get('scope')}")
        
        # Check all timestamp fields at top level
        print(f"  created_at (top): {memory.get('created_at')}")
        print(f"  updated_at (top): {memory.get('updated_at')}")
        
        # Check attributes
        attrs = memory.get('attributes', {})
        print(f"  Attributes type: {type(attrs)}")
        if isinstance(attrs, dict):
            print(f"    created_at (attr): {attrs.get('created_at')}")
            print(f"    updated_at (attr): {attrs.get('updated_at')}")
            print(f"    timestamp (attr): {attrs.get('timestamp')}")
            print(f"    All keys: {list(attrs.keys())}")
        
        # Pretty print full node for inspection
        print(f"\n  Full node data:")
        print(json.dumps(memory, indent=4)[:500] + "...")
else:
    print(f"Search failed: {search_response.status_code} - {search_response.text}")