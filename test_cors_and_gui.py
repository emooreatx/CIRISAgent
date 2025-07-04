#!/usr/bin/env python3
"""Test CORS and GUI connectivity."""

import requests

# Test from localhost:3000 perspective
print("Testing API endpoints...")

# 1. Test health endpoint (no auth)
try:
    response = requests.get("http://localhost:8080/v1/system/health")
    print(f"Health endpoint: {response.status_code}")
except Exception as e:
    print(f"Health endpoint error: {e}")

# 2. Test CORS preflight
try:
    response = requests.options(
        "http://localhost:8080/v1/memory/visualize/graph",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization,content-type"
        }
    )
    print(f"CORS preflight: {response.status_code}")
    print(f"CORS headers: {dict(response.headers)}")
except Exception as e:
    print(f"CORS error: {e}")

print("\nGUI is running at: http://localhost:3000")
print("Memory Explorer: http://localhost:3000/memory")
print("API Explorer: http://localhost:3000/api-demo")
print("\nIf visualization is not showing:")
print("1. Login with admin/ciris_admin_password")
print("2. Go to Memory page")
print("3. Check browser console for errors (F12)")
print("4. Try clicking the Refresh button")