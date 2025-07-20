#!/usr/bin/env python3
"""
Test CIRISManager GUI integration - verifies end-to-end functionality.
"""
import requests
import json
import sys

def test_ciris_manager_integration():
    """Test that CIRISManager API is accessible through nginx."""
    base_url = "https://agents.ciris.ai"
    
    print("Testing CIRISManager GUI Integration")
    print("=" * 50)
    
    # Test 1: CIRISManager health through nginx
    print("\n1. Testing CIRISManager API health through nginx...")
    try:
        response = requests.get(f"{base_url}/manager/v1/health", timeout=5)
        if response.status_code == 200:
            print("✓ CIRISManager API is accessible through nginx")
            print(f"  Response: {response.json()}")
        else:
            print(f"✗ Failed to access CIRISManager API: {response.status_code}")
            print(f"  Response: {response.text}")
            return False
    except Exception as e:
        print(f"✗ Error accessing CIRISManager API: {e}")
        return False
    
    # Test 2: List agents through nginx
    print("\n2. Testing agent discovery through nginx...")
    try:
        response = requests.get(f"{base_url}/manager/v1/agents", timeout=5)
        if response.status_code == 200:
            agents = response.json()
            print(f"✓ Successfully discovered {len(agents)} agent(s)")
            for agent in agents:
                print(f"  - {agent['agent_name']} ({agent['agent_id']}): {agent['status']}")
        else:
            print(f"✗ Failed to list agents: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error listing agents: {e}")
        return False
    
    # Test 3: Direct API health check
    print("\n3. Testing direct agent API access...")
    try:
        response = requests.get(f"{base_url}/v1/system/health", timeout=5)
        if response.status_code == 200:
            health = response.json()
            print("✓ Direct agent API is healthy")
            print(f"  Status: {health['data']['status']}")
            print(f"  Version: {health['data']['version']}")
        else:
            print(f"✗ Failed to access agent API: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error accessing agent API: {e}")
        return False
    
    # Test 4: GUI is accessible
    print("\n4. Testing GUI accessibility...")
    try:
        response = requests.get(base_url, timeout=5)
        if response.status_code == 200:
            print("✓ GUI is accessible")
        else:
            print(f"✗ GUI returned unexpected response: {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error accessing GUI: {e}")
        return False
    
    print("\n" + "=" * 50)
    print("All tests passed! CIRISManager is fully integrated.")
    return True

if __name__ == "__main__":
    success = test_ciris_manager_integration()
    sys.exit(0 if success else 1)