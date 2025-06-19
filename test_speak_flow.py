#!/usr/bin/env python3
"""Test speak flow to understand the issue."""
import asyncio
import sys
from ciris_sdk import CIRISClient


async def main():
    """Test speak action flow."""
    async with CIRISClient(base_url="http://localhost:8080") as client:
        # Clear previous messages by using unique channel
        import uuid
        channel = f"test_speak_{uuid.uuid4().hex[:8]}"
        
        print(f"1. Sending message to channel: {channel}")
        msg = await client.messages.send(
            content="$speak Hello from test!",
            channel_id=channel
        )
        print(f"   Sent message ID: {msg.id}")
        
        # Wait and check messages periodically
        for i in range(5):
            await asyncio.sleep(1)
            print(f"\n{i+2}. Checking messages after {i+1} seconds...")
            
            messages = await client.messages.list(
                channel_id=channel,
                limit=20
            )
            
            print(f"   Found {len(messages)} messages")
            
            # Group messages by author
            sdk_msgs = []
            agent_msgs = []
            
            for m in messages:
                if m.author_id == "sdk_user":
                    sdk_msgs.append(m)
                else:
                    agent_msgs.append(m)
            
            print(f"   SDK messages: {len(sdk_msgs)}")
            print(f"   Agent messages: {len(agent_msgs)}")
            
            # Check for the expected speak response
            for m in agent_msgs:
                if "Hello from test!" in m.content and len(m.content) < 100:
                    print(f"\n   ✓ FOUND CORRECT RESPONSE:")
                    print(f"     ID: {m.id}")
                    print(f"     Content: {m.content}")
                    return
                elif "Hello from test!" in m.content:
                    print(f"\n   ❌ Found response but with extra content:")
                    print(f"     ID: {m.id}")
                    print(f"     Content length: {len(m.content)}")
                    print(f"     First 200 chars: {m.content[:200]}...")
                    
                    # Check if it's the follow-up instruction
                    if "CIRIS_FOLLOW_UP_THOUGHT" in m.content:
                        print("     ⚠️  This is the follow-up thought instruction, not the actual speak response!")
                
            if len(agent_msgs) == 0:
                print("   ⏳ No agent messages yet, waiting...")
        
        print("\n❌ Test failed - no correct response found")
        print("\nAll agent messages:")
        for i, m in enumerate(agent_msgs):
            print(f"\n[{i}] ID: {m.id}")
            print(f"    Content preview: {m.content[:150]}...")


if __name__ == "__main__":
    asyncio.run(main())