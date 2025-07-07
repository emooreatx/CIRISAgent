#!/usr/bin/env python3
"""Test script to examine memory timestamps directly."""

import requests
from datetime import datetime, timezone, timedelta

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

# Query ALL memories without time filter to see raw timestamps
print("Querying all memories to examine timestamps...")
query_response = requests.post(
    "http://localhost:8080/v1/memory/query",
    headers=headers,
    json={
        "type": "observation",  # Pick a specific type (lowercase)
        "limit": 20
    }
)

if query_response.status_code == 200:
    memories = query_response.json()["data"]
    print(f"\nFound {len(memories)} memories of type OBSERVATION")
    
    # Analyze timestamps
    timestamps = []
    for memory in memories:
        attrs = memory.get("attributes", {})
        created_at = attrs.get("created_at") or attrs.get("timestamp")
        
        print(f"\nMemory ID: {memory['id'][:40]}...")
        print(f"  Type: {memory.get('type')}")
        print(f"  Created at: {created_at}")
        print(f"  Attributes keys: {list(attrs.keys())[:10]}")
        
        if created_at:
            try:
                # Parse timestamp
                if isinstance(created_at, str):
                    dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    timestamps.append(dt)
                    print(f"  Parsed as: {dt}")
                    print(f"  Hour bucket: {dt.replace(minute=0, second=0, microsecond=0)}")
            except Exception as e:
                print(f"  Failed to parse: {e}")
    
    if timestamps:
        # Show time distribution
        print(f"\n\nTimestamp Analysis:")
        print(f"  Earliest: {min(timestamps)}")
        print(f"  Latest: {max(timestamps)}")
        print(f"  Time span: {max(timestamps) - min(timestamps)}")
        
        # Count by hour
        hour_buckets = {}
        for ts in timestamps:
            bucket = ts.replace(minute=0, second=0, microsecond=0)
            hour_buckets[bucket] = hour_buckets.get(bucket, 0) + 1
        
        print(f"\n  Hour distribution:")
        for bucket in sorted(hour_buckets.keys()):
            print(f"    {bucket}: {hour_buckets[bucket]} memories")
else:
    print(f"Query failed: {query_response.status_code} - {query_response.text}")

# Also try querying with a different node type
print("\n\n" + "="*60)
print("Trying CONCEPT nodes...")
query_response = requests.post(
    "http://localhost:8080/v1/memory/query",
    headers=headers,
    json={
        "type": "concept",
        "limit": 10
    }
)

if query_response.status_code == 200:
    memories = query_response.json()["data"]
    print(f"\nFound {len(memories)} CONCEPT memories")
    for i, memory in enumerate(memories[:5]):
        attrs = memory.get("attributes", {})
        created_at = attrs.get("created_at") or attrs.get("timestamp")
        print(f"{i+1}. {memory['id'][:30]}... created_at={created_at}")