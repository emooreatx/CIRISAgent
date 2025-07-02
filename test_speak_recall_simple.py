import requests
import json

def test_speak_handler(port, speak_text):
    """Test SPEAK handler with detailed output"""
    print(f"\nTesting SPEAK on port {port}")
    print(f"Command: $speak {speak_text}")
    
    # Login
    login_response = requests.post(
        f"http://localhost:{port}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    token = login_response.json()["access_token"]
    
    # Send SPEAK command
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": f"$speak {speak_text}", "channel_id": f"api_0.0.0.0_{port}"}
    )
    
    result = response.json()
    
    # Extract the actual response text
    if "data" in result and "response" in result["data"]:
        response_text = result["data"]["response"]
        print(f"\nFull response text length: {len(response_text)} characters")
        print(f"\nFirst 500 chars of response:")
        print(response_text[:500])
        
        # Check if the spoken text appears in the response
        if speak_text in response_text:
            print(f"\n✓ SUCCESS: Spoken text '{speak_text}' found in response")
            # Find where it appears
            index = response_text.find(speak_text)
            print(f"Found at position {index}")
            # Show context around it
            start = max(0, index - 50)
            end = min(len(response_text), index + len(speak_text) + 50)
            print(f"\nContext: ...{response_text[start:end]}...")
        else:
            print(f"\n✗ FAIL: Spoken text '{speak_text}' NOT found in response")
    else:
        print("\n✗ ERROR: Unexpected response structure")
        print(json.dumps(result, indent=2))

def test_recall_handler(port, recall_query):
    """Test RECALL handler with detailed output"""
    print(f"\n\nTesting RECALL on port {port}")
    print(f"Command: $recall {recall_query}")
    
    # Login
    login_response = requests.post(
        f"http://localhost:{port}/v1/auth/login",
        json={"username": "admin", "password": "ciris_admin_password"}
    )
    token = login_response.json()["access_token"]
    
    # First memorize something
    print("\nFirst memorizing test data...")
    memorize_response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": "$memorize test_node_123 CONCEPT LOCAL", "channel_id": f"api_0.0.0.0_{port}"}
    )
    print(f"Memorize response status: {memorize_response.status_code}")
    
    # Now try to recall
    response = requests.post(
        f"http://localhost:{port}/v1/agent/interact",
        headers={"Authorization": f"Bearer {token}"},
        json={"message": f"$recall {recall_query}", "channel_id": f"api_0.0.0.0_{port}"}
    )
    
    result = response.json()
    
    # Check response
    if "data" in result:
        if "response" in result["data"]:
            response_text = result["data"]["response"]
            print(f"\nResponse text: {response_text[:500]}...")
            
            # Check for recall-related content
            if "recall" in response_text.lower() or "memory" in response_text.lower():
                print(f"\n✓ RECALL handler triggered (recall/memory keywords found)")
            else:
                print(f"\n? RECALL response unclear - no recall/memory keywords")
        
        # Check processing time
        if "processing_time_ms" in result["data"]:
            print(f"Processing time: {result['data']['processing_time_ms']}ms")
    else:
        print("\n✗ ERROR: Unexpected response structure")
        print(json.dumps(result, indent=2))

# Test Container 0 - SPEAK
print("="*60)
print("CONTAINER 0 - SPEAK HANDLER TEST")
print("="*60)
test_speak_handler(8080, "Hello from SPEAK test\!")

# Test Container 1 - RECALL
print("\n" + "="*60)
print("CONTAINER 1 - RECALL HANDLER TEST")
print("="*60)
test_recall_handler(8081, "test_node_123")

print("\n\nTEST COMPLETE")
