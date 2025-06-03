#!/usr/bin/env python3
"""
Test script to verify that the API returns agent responses in the messages list.
"""
import asyncio
import aiohttp
import json

async def test_api_messages():
    """Test the API messages endpoint functionality."""
    print("🧪 Testing API messages endpoint...")
    
    api_url = "http://localhost:8080"
    
    try:
        async with aiohttp.ClientSession() as session:
            # Test 1: Send a message
            print("📤 Sending test message...")
            send_payload = {
                "content": "Hello, this is a test message",
                "channel_id": "test_channel",
                "author_id": "test_user",
                "author_name": "Test User"
            }
            
            async with session.post(f"{api_url}/v1/messages", json=send_payload) as resp:
                if resp.status == 200:
                    response_data = await resp.json()
                    print(f"✅ Message sent successfully: {response_data}")
                else:
                    print(f"❌ Failed to send message: {resp.status}")
                    return
            
            # Wait a moment for processing
            await asyncio.sleep(2)
            
            # Test 2: Check status endpoint
            print("📊 Checking status endpoint...")
            async with session.get(f"{api_url}/v1/status") as resp:
                if resp.status == 200:
                    status_data = await resp.json()
                    print(f"✅ Status response: {json.dumps(status_data, indent=2)}")
                else:
                    print(f"❌ Failed to get status: {resp.status}")
            
            # Test 3: Get messages
            print("📥 Retrieving messages...")
            async with session.get(f"{api_url}/v1/messages?limit=10") as resp:
                if resp.status == 200:
                    messages_data = await resp.json()
                    print(f"✅ Messages response: {json.dumps(messages_data, indent=2)}")
                    
                    messages = messages_data.get("messages", [])
                    if messages:
                        print(f"📝 Found {len(messages)} messages:")
                        for i, msg in enumerate(messages):
                            print(f"  {i+1}. [{msg.get('author_id', 'unknown')}]: {msg.get('content', '')}")
                        
                        # Check if we have both user and agent messages
                        user_messages = [m for m in messages if m.get('author_id') == 'test_user']
                        agent_messages = [m for m in messages if m.get('author_id') == 'ciris_agent']
                        
                        print(f"👤 User messages: {len(user_messages)}")
                        print(f"🤖 Agent messages: {len(agent_messages)}")
                        
                        if user_messages and agent_messages:
                            print("🎉 SUCCESS: Found both user and agent messages!")
                            return True
                        elif user_messages and not agent_messages:
                            print("⚠️  WARNING: Found user messages but no agent responses")
                            return False
                        else:
                            print("❌ No messages found")
                            return False
                    else:
                        print("📭 No messages found")
                        return False
                else:
                    print(f"❌ Failed to get messages: {resp.status}")
                    return False
                    
    except aiohttp.ClientConnectorError:
        print("❌ Could not connect to API. Make sure the CIRIS API is running on localhost:8080")
        print("   You can start it with: cd CIRISGUI/apps/ciris-api && python main.py")
        return False
    except Exception as e:
        print(f"❌ Error during test: {e}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_api_messages())
    if result:
        print("\n✅ API messages test PASSED!")
    else:
        print("\n❌ API messages test FAILED!")
