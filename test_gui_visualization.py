#!/usr/bin/env python3
"""Test the GUI and API visualization features."""

import requests
import webbrowser
import tempfile
import os

# Test API visualization endpoint
print("Testing API visualization endpoint...")

# Login
login_response = requests.post(
    "http://localhost:8080/v1/auth/login",
    json={"username": "admin", "password": "ciris_admin_password"}
)
token = login_response.json()["access_token"]
print(f"✓ Logged in successfully")

# Get visualization
headers = {"Authorization": f"Bearer {token}"}
viz_response = requests.get(
    "http://localhost:8080/v1/memory/visualize/graph",
    headers=headers,
    params={
        "layout": "timeline",
        "hours": 24,
        "limit": 30
    }
)

if viz_response.status_code == 200:
    print(f"✓ Visualization endpoint working!")
    
    # Save to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.svg', delete=False) as f:
        f.write(viz_response.text)
        svg_path = f.name
    
    print(f"✓ SVG saved to: {svg_path}")
    print(f"  Size: {len(viz_response.text)} bytes")
    print(f"  Contains {viz_response.text.count('<circle')} nodes")
else:
    print(f"✗ Visualization failed: {viz_response.status_code}")

print("\n" + "="*50)
print("GUI URLs to test:")
print("="*50)
print("1. Memory Explorer: http://localhost:3000/memory")
print("   - Interactive graph visualization")
print("   - Click nodes to search")
print("   - Filter by scope and type")
print("   - Choose layout: force, timeline, hierarchical")
print("\n2. API Explorer: http://localhost:3000/api-demo")
print("   - Test 'Visualize Memory Graph' endpoint")
print("   - SVG will display inline in results")
print("\nLogin with: admin / ciris_admin_password")