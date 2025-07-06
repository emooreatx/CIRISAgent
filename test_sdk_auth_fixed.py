#!/usr/bin/env python3
"""Test SDK with proper authentication handling."""

import asyncio
import sys
sys.path.append('/home/emoore/CIRISAgent')
from ciris_sdk import CIRISClient


async def test_sdk_with_auth():
    """Test SDK with proper auth token handling."""
    async with CIRISClient(base_url="http://localhost:8080") as client:
        # Login and get the token
        print("Logging in...")
        login_response = await client.auth.login("admin", "ciris_admin_password")
        print(f"✓ Login successful, got token: {login_response.access_token[:20]}...")
        
        # Set the API key from the login response
        client.set_api_key(login_response.access_token)
        print("✓ API key set")
        
        # Now test methods that require auth
        print("\n=== Testing Authenticated Methods ===")
        
        # Test get current user
        try:
            print("\nTesting auth.get_current_user()...")
            user = await client.auth.get_current_user()
            print(f"✓ Current user: {user.username} (role: {user.role})")
            print(f"  Permissions: {user.permissions}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test agent status
        try:
            print("\nTesting agent.get_status()...")
            status = await client.agent.get_status()
            print(f"✓ Agent status: {status}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test interact
        try:
            print("\nTesting agent.interact()...")
            # Use proper context format
            response = await client.agent.interact(
                message="Hello from SDK test",
                context={"channel_id": "sdk_test_channel"}
            )
            print(f"✓ Response: {response.response}")
            print(f"  Thought ID: {response.thought_id}")
            print(f"  Processing time: {response.processing_time_ms}ms")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test convenience methods
        try:
            print("\nTesting client.interact() convenience method...")
            response = await client.interact("Hello again from SDK test")
            print(f"✓ Response: {response.response}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test system endpoints
        try:
            print("\nTesting system.health()...")
            health = await client.system.health()
            print(f"✓ System health: {health.status}")
            print(f"  Version: {health.version}")
            print(f"  Uptime: {health.uptime_seconds}s")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test memory operations
        try:
            print("\nTesting memory.store()...")
            from ciris_sdk import GraphNode
            node = GraphNode(
                id="test_sdk_node_1",
                type="test",
                attributes={
                    "content": "Test node from SDK",
                    "source": "sdk_test"
                }
            )
            result = await client.memory.store(node)
            print(f"✓ Stored node: {result}")
        except Exception as e:
            print(f"✗ Error: {e}")
        
        # Test telemetry
        try:
            print("\nTesting telemetry.get_metrics()...")
            metrics = await client.telemetry.get_metrics(hours=1)
            print(f"✓ Got {len(metrics.metrics)} metrics")
        except Exception as e:
            print(f"✗ Error: {e}")


if __name__ == "__main__":
    asyncio.run(test_sdk_with_auth())