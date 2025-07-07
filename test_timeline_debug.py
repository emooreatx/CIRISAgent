#!/usr/bin/env python3
"""Debug script to test timeline visualization timestamp handling."""

import asyncio
import logging
from datetime import datetime, timezone, timedelta

# Set up logging to see debug messages
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

async def test_timeline_debug():
    """Test the timeline visualization to see why nodes are cramming in first hour."""
    import requests
    
    # Login first
    login_response = requests.post(
        "http://localhost:8080/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    
    if login_response.status_code != 200:
        print(f"Login failed: {login_response.status_code} - {login_response.text}")
        return
        
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # First, let's query recent memories to see what timestamps they have
    print("\n1. Querying recent memories to check timestamps...")
    query_response = requests.post(
        "http://localhost:8080/v1/memory/query",
        headers=headers,
        json={
            "since": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
            "limit": 10
        }
    )
    
    if query_response.status_code == 200:
        memories = query_response.json()["data"]
        print(f"\nFound {len(memories)} memories")
        for i, memory in enumerate(memories[:5]):  # Show first 5
            attrs = memory.get("attributes", {})
            created_at = attrs.get("created_at") or attrs.get("timestamp")
            print(f"Memory {i}: id={memory['id'][:30]}..., created_at={created_at}")
    else:
        print(f"Query failed: {query_response.status_code} - {query_response.text}")
    
    # Now test the timeline endpoint
    print("\n2. Testing timeline endpoint...")
    timeline_response = requests.get(
        "http://localhost:8080/v1/memory/timeline?hours=24&limit=50",
        headers=headers
    )
    
    if timeline_response.status_code == 200:
        timeline_data = timeline_response.json()["data"]
        print(f"\nTimeline data:")
        print(f"  Total memories: {timeline_data['total']}")
        print(f"  Start time: {timeline_data['start_time']}")
        print(f"  End time: {timeline_data['end_time']}")
        print(f"  Number of buckets: {len(timeline_data['buckets'])}")
        
        # Show bucket distribution
        print("\n  Bucket distribution:")
        sorted_buckets = sorted(timeline_data['buckets'].items())
        for bucket, count in sorted_buckets[:10]:  # First 10 buckets
            print(f"    {bucket}: {count} memories")
    else:
        print(f"Timeline failed: {timeline_response.status_code} - {timeline_response.text}")
    
    # Finally, test the visualization with debug logging enabled
    print("\n3. Testing visualization endpoint (check container logs for debug output)...")
    viz_response = requests.get(
        "http://localhost:8080/v1/memory/visualize/graph?layout=timeline&hours=24&limit=20",
        headers=headers
    )
    
    if viz_response.status_code == 200:
        print(f"Visualization successful - SVG size: {len(viz_response.text)} bytes")
        # Save SVG for inspection
        with open("/tmp/timeline_debug.svg", "w") as f:
            f.write(viz_response.text)
        print("SVG saved to /tmp/timeline_debug.svg")
    else:
        print(f"Visualization failed: {viz_response.status_code} - {viz_response.text}")

if __name__ == "__main__":
    asyncio.run(test_timeline_debug())