#!/usr/bin/env python3
"""Test error handling and recovery across CIRIS containers."""

import requests
import json
import time
from datetime import datetime

def log_test(test_name, container, result, error=None):
    """Log test results."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    status = "✓ PASS" if not error else "✗ FAIL"
    print(f"[{timestamp}] Container {container} - {test_name}: {status}")
    if result:
        print(f"  Response: {result}")
    if error:
        print(f"  Error: {error}")
    print()

def test_container_1_errors(base_url="http://localhost:8081"):
    """Test Container 1 error scenarios."""
    print("\n" + "="*60)
    print("CONTAINER 1 (Port 8081) - Error Handling Tests")
    print("="*60)
    
    # 1. Login first
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    try:
        response = requests.post(f"{base_url}/v1/auth/login", json=login_data, timeout=5)
        if response.status_code == 200:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            log_test("Login", 1, "Success")
        else:
            log_test("Login", 1, None, f"Status {response.status_code}: {response.text}")
            return
    except Exception as e:
        log_test("Login", 1, None, str(e))
        return
    
    # 2. Send malformed command: $unknown_command test
    try:
        interact_data = {
            "message": "$unknown_command test",
            "channel_id": "api_test_8081"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            headers=headers, 
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.json() if response.status_code == 200 else response.text}"
        log_test("Malformed command ($unknown_command)", 1, result)
    except Exception as e:
        log_test("Malformed command", 1, None, str(e))
    
    # 3. Send empty command: $
    try:
        interact_data = {
            "message": "$",
            "channel_id": "api_test_8081"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            headers=headers, 
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.json() if response.status_code == 200 else response.text}"
        log_test("Empty command ($)", 1, result)
    except Exception as e:
        log_test("Empty command", 1, None, str(e))
    
    # 4. Send very long command
    long_text = " test" * 1000  # 5000 characters
    try:
        interact_data = {
            "message": f"$speak{long_text}",
            "channel_id": "api_test_8081"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            headers=headers, 
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.json() if response.status_code == 200 else response.text}"
        log_test("Very long command (5000 chars)", 1, result[:200] + "..." if len(str(result)) > 200 else result)
    except Exception as e:
        log_test("Very long command", 1, None, str(e))
    
    # 5. Test recovery - send valid command after errors
    try:
        interact_data = {
            "message": "$whoami",
            "channel_id": "api_test_8081"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            headers=headers, 
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.json() if response.status_code == 200 else response.text}"
        log_test("Recovery test ($whoami after errors)", 1, result)
    except Exception as e:
        log_test("Recovery test", 1, None, str(e))

def test_container_2_auth_errors(base_url="http://localhost:8082"):
    """Test Container 2 authentication error scenarios."""
    print("\n" + "="*60)
    print("CONTAINER 2 (Port 8082) - Authentication Error Tests")
    print("="*60)
    
    # 1. Send command without auth (should fail)
    try:
        interact_data = {
            "message": "$whoami",
            "channel_id": "api_test_8082"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.text}"
        expected_fail = response.status_code in [401, 403]
        log_test(f"No auth (expected to fail)", 2, result if expected_fail else None, None if expected_fail else "Should have failed")
    except Exception as e:
        log_test("No auth", 2, None, str(e))
    
    # 2. Send command with wrong auth
    try:
        wrong_headers = {"Authorization": "Bearer wrong_token_12345"}
        interact_data = {
            "message": "$whoami",
            "channel_id": "api_test_8082"
        }
        response = requests.post(
            f"{base_url}/v1/agent/interact", 
            headers=wrong_headers,
            json=interact_data,
            timeout=10
        )
        result = f"Status {response.status_code}: {response.text}"
        expected_fail = response.status_code in [401, 403]
        log_test(f"Wrong auth (expected to fail)", 2, result if expected_fail else None, None if expected_fail else "Should have failed")
    except Exception as e:
        log_test("Wrong auth", 2, None, str(e))
    
    # 3. Login with wrong credentials
    try:
        wrong_login = {"username": "admin", "password": "wrong_password"}
        response = requests.post(f"{base_url}/v1/auth/login", json=wrong_login, timeout=5)
        result = f"Status {response.status_code}: {response.text}"
        expected_fail = response.status_code in [401, 403]
        log_test(f"Wrong password (expected to fail)", 2, result if expected_fail else None, None if expected_fail else "Should have failed")
    except Exception as e:
        log_test("Wrong password", 2, None, str(e))
    
    # 4. Now login correctly and test recovery
    try:
        login_data = {"username": "admin", "password": "ciris_admin_password"}
        response = requests.post(f"{base_url}/v1/auth/login", json=login_data, timeout=5)
        if response.status_code == 200:
            token = response.json()["access_token"]
            headers = {"Authorization": f"Bearer {token}"}
            log_test("Correct login after errors", 2, "Success")
            
            # Send valid command to test recovery
            interact_data = {
                "message": "$speak I have recovered from authentication errors",
                "channel_id": "api_test_8082"
            }
            response = requests.post(
                f"{base_url}/v1/agent/interact", 
                headers=headers, 
                json=interact_data,
                timeout=10
            )
            result = f"Status {response.status_code}: {response.json() if response.status_code == 200 else response.text}"
            log_test("Recovery after auth errors", 2, result)
        else:
            log_test("Correct login", 2, None, f"Status {response.status_code}: {response.text}")
    except Exception as e:
        log_test("Recovery test", 2, None, str(e))

def check_container_logs(container_num):
    """Check container logs for error handling."""
    print(f"\n--- Checking Container {container_num} Logs ---")
    
    # Check incidents log
    cmd = f"docker exec ciris_mock_llm_container{container_num} tail -20 /app/logs/incidents_latest.log 2>/dev/null || echo 'No incidents log found'"
    try:
        import subprocess
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.stdout.strip():
            print(f"Recent incidents in container {container_num}:")
            print(result.stdout)
        else:
            print(f"No recent incidents in container {container_num}")
    except Exception as e:
        print(f"Error checking logs: {e}")

def main():
    """Run all error handling tests."""
    print("CIRIS Error Handling and Recovery Tests")
    print("=" * 60)
    print(f"Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Test Container 1
    test_container_1_errors()
    time.sleep(1)  # Brief pause between tests
    
    # Test Container 2
    test_container_2_auth_errors()
    
    # Check logs
    print("\n" + "="*60)
    print("CONTAINER LOGS ANALYSIS")
    print("="*60)
    check_container_logs(1)
    check_container_logs(2)
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    print("Error Handling Observations:")
    print("1. Check if malformed commands are handled gracefully")
    print("2. Verify authentication errors return appropriate status codes")
    print("3. Confirm system recovers after errors")
    print("4. Review if error messages are helpful and informative")

if __name__ == "__main__":
    main()