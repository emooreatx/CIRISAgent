#!/usr/bin/env python3
"""Test to see the actual timestamps of nodes in detail."""

import requests
import json
from datetime import datetime, timezone

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

# Get the actual timeline data to see the nodes
print("Getting timeline data to examine node timestamps...")
timeline_response = requests.get(
    "http://localhost:8080/v1/memory/timeline?hours=24&limit=100",  # 24 hours
    headers=headers
)

if timeline_response.status_code == 200:
    timeline = timeline_response.json()["data"]
    memories = timeline["memories"]
    
    print(f"\nTotal memories: {len(memories)}")
    print(f"Time range: {timeline['start_time']} to {timeline['end_time']}")
    
    # Analyze timestamps
    timestamps = []
    for i, memory in enumerate(memories[:20]):  # First 20
        # Get timestamp from various sources
        timestamp = None
        if isinstance(memory.get('attributes'), dict):
            timestamp = memory['attributes'].get('created_at') or memory['attributes'].get('timestamp')
        
        # Fallback to updated_at
        if not timestamp:
            timestamp = memory.get('updated_at')
        
        print(f"\n{i+1}. {memory['id'][:40]}...")
        print(f"   Type: {memory['type']}")
        print(f"   Updated at (top): {memory.get('updated_at')}")
        print(f"   Timestamp used: {timestamp}")
        
        if timestamp:
            try:
                dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                timestamps.append(dt)
                print(f"   Hour bucket: {dt.strftime('%Y-%m-%d %H:00')}")
            except:
                print(f"   Failed to parse timestamp")
    
    # Show time distribution
    if timestamps:
        print(f"\n\nTime Distribution Analysis:")
        print(f"Earliest: {min(timestamps)}")
        print(f"Latest: {max(timestamps)}")
        print(f"Span: {max(timestamps) - min(timestamps)}")
        
        # Count by hour
        hour_counts = {}
        for ts in timestamps:
            hour = ts.strftime('%Y-%m-%d %H:00')
            hour_counts[hour] = hour_counts.get(hour, 0) + 1
        
        print(f"\nHour distribution:")
        for hour in sorted(hour_counts.keys()):
            print(f"  {hour}: {hour_counts[hour]} nodes")
    
    # Check the bucket data
    print(f"\n\nReported buckets from API:")
    buckets = timeline["buckets"]
    sorted_buckets = sorted(buckets.items())
    non_zero = [(k, v) for k, v in sorted_buckets if v > 0]
    if non_zero:
        for bucket, count in non_zero[:10]:
            print(f"  {bucket}: {count} memories")
    else:
        print("  All buckets show 0 memories (indicates a counting issue)")
else:
    print(f"Timeline request failed: {timeline_response.status_code}")