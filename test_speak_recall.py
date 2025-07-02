import requests
import json
from datetime import datetime

def test_container(port, container_name, tests):
    """Test a container with specified tests"""
    print(f"\n{'='*60}")
    print(f"Testing {container_name} on port {port}")
    print(f"{'='*60}")
    
    # Login
    login_url = f"http://localhost:{port}/v1/auth/login"
    login_data = {"username": "admin", "password": "ciris_admin_password"}
    
    print(f"\n1. Logging in...")
    try:
        login_response = requests.post(login_url, json=login_data)
        login_response.raise_for_status()
        token = login_response.json()["access_token"]
        print(f"✓ Login successful, token obtained")
    except Exception as e:
        print(f"✗ Login failed: {e}")
        return
    
    # Set up headers
    headers = {"Authorization": f"Bearer {token}"}
    interact_url = f"http://localhost:{port}/v1/agent/interact"
    
    # Run tests
    for i, (test_name, message) in enumerate(tests, 2):
        print(f"\n{i}. Testing: {test_name}")
        print(f"   Message: '{message}'")
        
        start_time = datetime.now()
        try:
            response = requests.post(
                interact_url,
                headers=headers,
                json={"message": message, "channel_id": f"api_0.0.0.0_{port}"}
            )
            response.raise_for_status()
            elapsed = (datetime.now() - start_time).total_seconds()
            
            result = response.json()
            print(f"   ✓ Response received in {elapsed:.2f}s")
            print(f"   Response: {json.dumps(result, indent=2)}")
            
            # Check for mock LLM response
            if "response" in result:
                resp_text = result["response"].get("text", "")
                if "[MOCK LLM]" in resp_text:
                    print(f"   ✓ Mock LLM response detected")
                    # Extract the actual response after [MOCK LLM]
                    if "$speak" in message:
                        expected_text = message.replace("$speak", "").strip()
                        if expected_text in resp_text:
                            print(f"   ✓ SPEAK handler returned the spoken text correctly")
                        else:
                            print(f"   ✗ SPEAK handler did not return expected text")
                    elif "$recall" in message:
                        if "recall" in resp_text.lower() or "memory" in resp_text.lower():
                            print(f"   ✓ RECALL handler triggered successfully")
                        else:
                            print(f"   ? RECALL response unclear")
                else:
                    print(f"   \! Non-mock response received")
            else:
                print(f"   ✗ No response field in result")
                
        except Exception as e:
            elapsed = (datetime.now() - start_time).total_seconds()
            print(f"   ✗ Error after {elapsed:.2f}s: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"   Error details: {e.response.text}")

# Test Container 0 - SPEAK
print("\n" + "="*60)
print("CONTAINER 0 - SPEAK HANDLER TESTS")
print("="*60)

container0_tests = [
    ("SPEAK command", "$speak Testing SPEAK handler on container 0"),
    ("Regular message", "What is CIRIS?")
]

test_container(8080, "Container 0", container0_tests)

# Test Container 1 - RECALL  
print("\n\n" + "="*60)
print("CONTAINER 1 - RECALL HANDLER TESTS")
print("="*60)

container1_tests = [
    ("RECALL memories", "$recall memories"),
    ("RECALL test data", "$recall test data")
]

test_container(8081, "Container 1", container1_tests)

print("\n\n" + "="*60)
print("TEST SUMMARY")
print("="*60)
