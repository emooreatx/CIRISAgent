import requests
import json
import time

def test_recall_with_timing(port):
    """Test RECALL with detailed timing"""
    print(f"\nTesting RECALL on port {port}")
    
    # Login
    login_response = requests.post(
        f"http://localhost:{port}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    token = login_response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Simple recall query
    print("\n1. Testing simple recall query: $recall memories")
    start = time.time()
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers=headers,
        json={"message": "$recall memories", "channel_id": f"api_0.0.0.0_{port}"},
        timeout=35  # Set explicit timeout
    )
    elapsed = time.time() - start
    print(f"   Response time: {elapsed:.2f}s")
    print(f"   Status code: {response.status_code}")
    
    result = response.json()
    if "data" in result and "response" in result["data"]:
        resp = result["data"]["response"]
        print(f"   Response preview: {resp[:200]}...")
        if "processing_time_ms" in result["data"]:
            print(f"   Processing time: {result['data']['processing_time_ms']}ms")
    
    # Test 2: Recall with node ID
    print("\n2. Testing recall with node ID: $recall test_node USER")
    start = time.time()
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers=headers,
        json={"message": "$recall test_node USER", "channel_id": f"api_0.0.0.0_{port}"},
        timeout=35
    )
    elapsed = time.time() - start
    print(f"   Response time: {elapsed:.2f}s")
    print(f"   Status code: {response.status_code}")
    
    result = response.json()
    if "data" in result and "response" in result["data"]:
        resp = result["data"]["response"]
        print(f"   Response preview: {resp[:200]}...")

# Test on container 1
test_recall_with_timing(8081)

# Also test on container 0 for comparison
print("\n" + "="*60)
print("Testing RECALL on container 0 for comparison")
print("="*60)
test_recall_with_timing(8080)
