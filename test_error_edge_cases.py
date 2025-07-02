#!/usr/bin/env python3
"""Test additional error edge cases."""

import requests
import json
from datetime import datetime

def test_malformed_json(base_url="http://localhost:8081"):
    """Test various malformed JSON scenarios."""
    print("\n=== Testing Malformed JSON ===")
    
    # First login
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    response = requests.post(f"{base_url}/v1/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    # Test 1: Missing required field (message)
    print("\n1. Missing 'message' field:")
    try:
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            json={"channel_id": "test"},
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 2: Missing channel_id
    print("\n2. Missing 'channel_id' field:")
    try:
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            json={"message": "test"},
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 3: Wrong data types
    print("\n3. Wrong data types (message as number):")
    try:
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            json={"message": 12345, "channel_id": "test"},
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test 4: Invalid JSON
    print("\n4. Invalid JSON (raw text):")
    try:
        response = requests.post(
            f"{base_url}/v1/agent/interact",
            headers=headers,
            data="this is not json",
            timeout=5
        )
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
    except Exception as e:
        print(f"   Error: {e}")

def test_special_characters(base_url="http://localhost:8082"):
    """Test handling of special characters."""
    print("\n=== Testing Special Characters ===")
    
    # Login first
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    response = requests.post(f"{base_url}/v1/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    test_cases = [
        ("Unicode", "$speak 你好世界 🌍 émojis"),
        ("Newlines", "$speak line1\nline2\nline3"),
        ("Quotes", '$speak "quoted text" and \'single quotes\''),
        ("Special chars", "$speak <>&;|`"),
        ("Null bytes", "$speak test\x00null"),
        ("Escape sequences", "$speak test\\nescaped\\ttabs"),
    ]
    
    for name, message in test_cases:
        print(f"\n{name}: {repr(message)}")
        try:
            response = requests.post(
                f"{base_url}/v1/agent/interact",
                headers=headers,
                json={"message": message, "channel_id": "test_special"},
                timeout=5
            )
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()["data"]
                print(f"   Response: {data['response'][:100]}...")
            else:
                print(f"   Error: {response.text}")
        except Exception as e:
            print(f"   Exception: {e}")

def test_concurrent_errors(base_url="http://localhost:8081"):
    """Test handling of concurrent error requests."""
    print("\n=== Testing Concurrent Errors ===")
    
    import concurrent.futures
    import time
    
    # Login first
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    response = requests.post(f"{base_url}/v1/auth/login", json=login_data)
    token = response.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    
    def send_error_request(i):
        """Send an error-inducing request."""
        try:
            # Mix of different error types
            if i % 3 == 0:
                # Invalid command
                data = {"message": f"$invalid_cmd_{i}", "channel_id": f"test_{i}"}
            elif i % 3 == 1:
                # Missing field
                data = {"message": f"test_{i}"}
            else:
                # Wrong type
                data = {"message": None, "channel_id": f"test_{i}"}
            
            start = time.time()
            response = requests.post(
                f"{base_url}/v1/agent/interact",
                headers=headers,
                json=data,
                timeout=10
            )
            duration = time.time() - start
            return (i, response.status_code, duration)
        except Exception as e:
            return (i, "error", str(e))
    
    # Send 10 concurrent error requests
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(send_error_request, i) for i in range(10)]
        results = [f.result() for f in concurrent.futures.as_completed(futures)]
    
    print("\nConcurrent request results:")
    for i, status, duration in sorted(results):
        print(f"   Request {i}: Status={status}, Duration={duration:.2f}s" if isinstance(duration, float) else f"   Request {i}: {status} - {duration}")
    
    # Test recovery after concurrent errors
    print("\nTesting recovery after concurrent errors:")
    response = requests.post(
        f"{base_url}/v1/agent/interact",
        headers=headers,
        json={"message": "$speak System recovered", "channel_id": "recovery_test"},
        timeout=10
    )
    print(f"   Recovery status: {response.status_code}")
    if response.status_code == 200:
        print(f"   Recovery successful: {response.json()['data']['response'][:50]}...")

def main():
    """Run edge case tests."""
    print("CIRIS Error Handling Edge Cases")
    print("=" * 60)
    
    test_malformed_json()
    test_special_characters()
    test_concurrent_errors()
    
    print("\n" + "="*60)
    print("EDGE CASE TEST SUMMARY")
    print("="*60)

if __name__ == "__main__":
    main()