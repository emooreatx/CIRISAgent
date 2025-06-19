#!/usr/bin/env python3
"""Debug SDK test failure."""
import asyncio
import sys
from ciris_sdk import CIRISClient


async def main():
    """Test speak action with detailed debugging."""
    async with CIRISClient(base_url="http://localhost:8080") as client:
        print("1. Sending message...")
        msg = await client.messages.send(
            content="$speak Hello from SDK test!",
            channel_id="test_speak_channel"
        )
        print(f"   Sent message ID: {msg.id}")
        print(f"   Content: {msg.content}")
        print(f"   Channel: {msg.channel_id}")
        
        # Wait for processing
        print("\n2. Waiting 2 seconds for processing...")
        await asyncio.sleep(2)
        
        # List all messages in channel
        print("\n3. Listing all messages in channel...")
        messages = await client.messages.list(
            channel_id="test_speak_channel",
            limit=20
        )
        print(f"   Found {len(messages)} messages")
        for i, m in enumerate(messages):
            print(f"   [{i}] ID: {m.id}")
            print(f"       Author: {m.author_id} ({m.author_name})")
            print(f"       Content length: {len(m.content)}")
            print(f"       First 100 chars: {m.content[:100]}...")
            print()
        
        # Try wait_for_response
        print("\n4. Waiting for response...")
        response = await client.messages.wait_for_response(
            channel_id="test_speak_channel",
            after_message_id=msg.id,
            timeout=5.0
        )
        
        if response:
            print(f"   Got response ID: {response.id}")
            print(f"   Author: {response.author_id} ({response.author_name})")
            print(f"   Content: {response.content[:200]}...")
        else:
            print("   No response found (timeout)")
            
            # Debug the wait logic
            print("\n5. Debug wait_for_response logic:")
            print(f"   Looking for messages after ID: {msg.id}")
            print("   Filtering criteria:")
            print("   - author_id != 'sdk_user'")
            print("   - author_name != 'SDK User'")
            
            # Check each message manually
            found_agent_msg = False
            for i, m in enumerate(messages):
                is_after = False  # We'll check this differently
                is_agent = m.author_id != "sdk_user" and m.author_name != "SDK User"
                print(f"\n   Message [{i}]:")
                print(f"   - ID: {m.id}")
                print(f"   - Is agent message: {is_agent}")
                print(f"   - Author: {m.author_id} / {m.author_name}")
                
                if is_agent:
                    found_agent_msg = True
                    print(f"   ✓ This is an agent message!")
                    
            if not found_agent_msg:
                print("\n   ❌ No agent messages found in channel")
            else:
                print("\n   ✓ Agent messages exist but wait_for_response didn't find them")


if __name__ == "__main__":
    asyncio.run(main())