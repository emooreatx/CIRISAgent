#!/usr/bin/env python3
"""Test channel extraction from API context."""

import requests
import json
import time

def test_container(port, container_num):
    """Test a single container's API interaction."""
    print(f"\n{'='*60}")
    print(f"Testing container{container_num} on port {port}")
    print(f"{'='*60}")
    
    results = {
        "container": container_num,
        "port": port,
        "health": False,
        "login": False,
        "interact": False,
        "response": None,
        "errors": []
    }
    
    try:
        # 1. Health check
        print(f"\n1. Health check...")
        start_time = time.time()
        health_resp = requests.get(
            f"http://localhost:{port}/v1/system/health",
            headers={"Authorization": "Bearer admin:ciris_admin_password"},
            timeout=5
        )
        health_time = time.time() - start_time
        
        if health_resp.status_code == 200:
            health_data = health_resp.json()
            results["health"] = True
            print(f"   ✅ Healthy (took {health_time:.2f}s)")
            print(f"   - Version: {health_data['data']['version']}")
            print(f"   - Uptime: {health_data['data']['uptime_seconds']:.1f}s")
            print(f"   - State: {health_data['data']['cognitive_state']}")
        else:
            results["errors"].append(f"Health check failed: {health_resp.status_code}")
            print(f"   ❌ Failed: {health_resp.status_code}")
            return results
            
        # 2. Login
        print(f"\n2. Login...")
        start_time = time.time()
        login_resp = requests.post(
            f"http://localhost:{port}/v1/auth/login",
            json={"username": "admin", "password": "ciris_admin_password"},
            timeout=5
        )
        login_time = time.time() - start_time
        
        if login_resp.status_code == 200:
            token = login_resp.json()["access_token"]
            results["login"] = True
            print(f"   ✅ Logged in (took {login_time:.2f}s)")
            print(f"   - Token: {token[:30]}...")
        else:
            results["errors"].append(f"Login failed: {login_resp.status_code}")
            print(f"   ❌ Failed: {login_resp.status_code}")
            return results
            
        # 3. Test interact with explicit channel
        print(f"\n3. Testing interact endpoint...")
        channel_id = f"api_0.0.0.0_{port}"
        message = f"$speak Testing channel extraction on container {container_num}"
        
        print(f"   - Channel: {channel_id}")
        print(f"   - Message: {message}")
        
        start_time = time.time()
        interact_resp = requests.post(
            f"http://localhost:{port}/v1/agent/interact",
            headers={"Authorization": f"Bearer {token}"},
            json={"message": message, "channel_id": channel_id},
            timeout=35  # Allow for 30s timeout + buffer
        )
        interact_time = time.time() - start_time
        
        if interact_resp.status_code == 200:
            interact_data = interact_resp.json()
            results["interact"] = True
            results["response"] = interact_data
            print(f"   ✅ Response received (took {interact_time:.2f}s)")
            print(f"   - Message ID: {interact_data['data']['message_id']}")
            print(f"   - Response: {interact_data['data']['response'][:100]}...")
            print(f"   - Processing time: {interact_data['data']['processing_time_ms']}ms")
        else:
            results["errors"].append(f"Interact failed: {interact_resp.status_code}")
            print(f"   ❌ Failed: {interact_resp.status_code}")
            
        # 4. Check history to see actual response
        print(f"\n4. Checking history...")
        time.sleep(2)  # Give it time to process
        
        history_resp = requests.get(
            f"http://localhost:{port}/v1/agent/history",
            headers={"Authorization": f"Bearer {token}"},
            params={"limit": 5},
            timeout=5
        )
        
        if history_resp.status_code == 200:
            messages = history_resp.json()["data"]["messages"]
            print(f"   - Found {len(messages)} messages")
            
            # Look for our message and response
            found_our_message = False
            found_response = False
            
            for msg in messages[:5]:  # Check last 5 messages
                if msg["content"] == message and not msg["is_agent"]:
                    found_our_message = True
                    print(f"   ✅ Found our message")
                elif msg["is_agent"] and found_our_message and not found_response:
                    found_response = True
                    print(f"   - Agent response: {msg['content'][:100]}...")
                    
                    # Check if response mentions the correct channel
                    if f"container {container_num}" in msg['content'] or channel_id in msg['content']:
                        print(f"   ✅ Response correctly identifies container/channel!")
                    else:
                        print(f"   ⚠️  Response doesn't mention correct container/channel")
                        results["errors"].append("Channel not properly identified in response")
                        
    except requests.exceptions.Timeout:
        results["errors"].append("Request timed out")
        print(f"   ❌ Request timed out")
    except Exception as e:
        results["errors"].append(str(e))
        print(f"   ❌ Error: {e}")
        
    return results

def main():
    """Test containers 0, 1, and 2."""
    print("Channel Extraction Test for API Containers")
    print("==========================================")
    
    # Test all three containers
    all_results = []
    for i in range(3):
        port = 8080 + i
        results = test_container(port, i)
        all_results.append(results)
        
    # Summary
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    
    for result in all_results:
        status = "✅" if not result["errors"] else "❌"
        print(f"\nContainer {result['container']} (port {result['port']}): {status}")
        print(f"  - Health: {'✅' if result['health'] else '❌'}")
        print(f"  - Login: {'✅' if result['login'] else '❌'}")
        print(f"  - Interact: {'✅' if result['interact'] else '❌'}")
        
        if result["errors"]:
            print(f"  - Errors:")
            for error in result["errors"]:
                print(f"    • {error}")
                
    # Check container logs for errors
    print(f"\n{'='*60}")
    print("CHECKING CONTAINER LOGS")
    print(f"{'='*60}")
    
    import subprocess
    for i in range(3):
        print(f"\nContainer {i} incident log (last 10 lines):")
        try:
            output = subprocess.check_output(
                f"docker exec ciris_mock_llm_container{i} tail -10 /app/logs/incidents_latest.log | grep -E '(ERROR|WARNING.*channel)' || true",
                shell=True,
                text=True
            )
            if output.strip():
                print(output)
            else:
                print("  No channel-related errors found")
        except Exception as e:
            print(f"  Could not read logs: {e}")

if __name__ == "__main__":
    main()