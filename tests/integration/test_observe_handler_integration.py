#!/usr/bin/env python3
"""
Integration test for the actual ObserveHandler._recall_from_messages method
with real Discord adapter message structure.

This script tests the actual implementation to ensure it correctly unpacks
the message structure that the observer in the platform adapter is building.
"""
import asyncio
import logging
import sys
import os
from typing import Dict, Any, List
from unittest.mock import Mock, AsyncMock

# Add the project root to sys.path
sys.path.insert(0, '/home/emoore/CIRISAgent')

from ciris_engine.action_handlers.observe_handler import ObserveHandler
from ciris_engine.schemas.graph_schemas_v1 import GraphScope

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

class TestMemoryService:
    """Test memory service that tracks all recall calls"""
    def __init__(self):
        self.recall_calls = []
        self.recall_details = []
        
    async def recall(self, node_id: str, scope: GraphScope):
        """Track recall calls with full details"""
        self.recall_calls.append((node_id, scope))
        self.recall_details.append({
            'node_id': node_id,
            'scope': scope,
            'scope_value': scope.value if hasattr(scope, 'value') else str(scope)
        })
        logger.info(f"MEMORY RECALL: node_id='{node_id}', scope='{scope}'")

def create_realistic_discord_messages() -> List[Dict[str, Any]]:
    """Create messages that exactly match Discord adapter output structure"""
    return [
        {
            "id": "1084151813175242762",
            "content": "Hey everyone! How's the project going?",
            "author_id": "918273645098123456",
            "author_name": "Alice",
            "timestamp": "2025-06-01T19:30:15.123000+00:00",
            "is_bot": False
        },
        {
            "id": "1084151813175242763", 
            "content": "Working on the new feature branch. Should be ready for review soon.",
            "author_id": "918273645098123457",
            "author_name": "Bob", 
            "timestamp": "2025-06-01T19:31:22.456000+00:00",
            "is_bot": False
        },
        {
            "id": "1084151813175242764",
            "content": "🤖 Automated deployment successful for branch feature/user-auth",
            "author_id": "918273645098123458",
            "author_name": "DeployBot",
            "timestamp": "2025-06-01T19:32:18.789000+00:00", 
            "is_bot": True
        },
        {
            "id": "1084151813175242765",
            "content": "Great work team! The tests are all passing ✅",
            "author_id": "918273645098123456",  # Same as Alice (duplicate author)
            "author_name": "Alice",
            "timestamp": "2025-06-01T19:33:45.012000+00:00",
            "is_bot": False
        },
        {
            "id": "1084151813175242766",
            "content": "Let's schedule a demo for tomorrow",
            "author_id": "918273645098123459",
            "author_name": "Charlie",
            "timestamp": "2025-06-01T19:34:12.345000+00:00",
            "is_bot": False
        }
    ]

def create_edge_case_messages() -> List[Dict[str, Any]]:
    """Create edge case messages to test robustness"""
    return [
        {
            "id": "edge1",
            "content": "",  # Empty content
            "author_id": "918273645098123460",
            "author_name": "EdgeUser1",
            "timestamp": "2025-06-01T19:35:00.000000+00:00",
            "is_bot": False
        },
        {
            "id": "edge2", 
            "content": "Message with empty author_id",
            "author_id": "",  # Empty author_id
            "author_name": "EdgeUser2",
            "timestamp": "2025-06-01T19:35:01.000000+00:00",
            "is_bot": False
        },
        {
            "id": "edge3",
            "content": "Message with None author_id", 
            "author_id": None,  # None author_id
            "author_name": "EdgeUser3",
            "timestamp": "2025-06-01T19:35:02.000000+00:00",
            "is_bot": False
        },
        {
            "id": "edge4",
            "content": "Missing author_id field",
            # author_id field completely missing
            "author_name": "EdgeUser4", 
            "timestamp": "2025-06-01T19:35:03.000000+00:00",
            "is_bot": False
        }
    ]

async def test_real_observe_handler():
    """Test the actual ObserveHandler._recall_from_messages method"""
    logger.info("=== Testing Real ObserveHandler Implementation ===")
    
    # Create test memory service
    memory_service = TestMemoryService()
    
    # Test realistic Discord messages
    channel_id = "918273645012345678"  # Realistic Discord channel ID
    messages = create_realistic_discord_messages()
    
    logger.info(f"Testing with {len(messages)} realistic Discord messages")
    logger.info(f"Channel ID: {channel_id}")
    
    for i, msg in enumerate(messages, 1):
        logger.info(f"Message {i}: ID={msg['id']}, Author={msg['author_name']} ({msg['author_id']}), Bot={msg['is_bot']}")
        logger.info(f"  Content: {msg['content'][:80]}{'...' if len(msg['content']) > 80 else ''}")
    
    # Create a mock ObserveHandler instance to call the method
    handler = ObserveHandler()
    
    # Call the actual method
    await handler._recall_from_messages(memory_service, channel_id, messages)
    
    # Analyze results
    logger.info(f"\n--- Recall Analysis ---")
    logger.info(f"Total recall operations: {len(memory_service.recall_calls)}")
    
    # Group by node type and ID
    channel_recalls = [call for call in memory_service.recall_details if call['node_id'].startswith('channel/')]
    user_recalls = [call for call in memory_service.recall_details if call['node_id'].startswith('user/')]
    
    logger.info(f"Channel recalls: {len(channel_recalls)}")
    logger.info(f"User recalls: {len(user_recalls)}")
    
    # Check unique nodes
    unique_nodes = set(call['node_id'] for call in memory_service.recall_details)
    logger.info(f"Unique nodes recalled: {len(unique_nodes)}")
    
    for node_id in sorted(unique_nodes):
        node_calls = [call for call in memory_service.recall_details if call['node_id'] == node_id]
        scopes = [call['scope_value'] for call in node_calls]
        logger.info(f"  {node_id}: {scopes}")
    
    # Validate expectations
    # Should have: 1 channel + 4 unique users (Alice, Bob, DeployBot, Charlie) = 5 nodes
    # Alice appears twice but should only be recalled once per scope
    unique_authors = set()
    for msg in messages:
        author_id = msg.get('author_id')
        if author_id:
            unique_authors.add(author_id)
    
    expected_nodes = 1 + len(unique_authors)  # channel + unique authors
    expected_calls = expected_nodes * 3  # 3 scopes per node
    
    assert len(unique_nodes) == expected_nodes, f"Expected {expected_nodes} unique nodes, got {len(unique_nodes)}"
    assert len(memory_service.recall_calls) == expected_calls, f"Expected {expected_calls} recall calls, got {len(memory_service.recall_calls)}"
    
    # Verify channel recall
    channel_node = f"channel/{channel_id}"
    assert channel_node in unique_nodes, f"Channel node {channel_node} not found in recalls"
    
    # Verify user recalls
    for author_id in unique_authors:
        user_node = f"user/{author_id}"
        assert user_node in unique_nodes, f"User node {user_node} not found in recalls"
    
    logger.info("✅ Real ObserveHandler test passed!")

async def test_edge_cases_real_handler():
    """Test edge cases with the real handler"""
    logger.info("\n=== Testing Edge Cases with Real Handler ===")
    
    memory_service = TestMemoryService()
    channel_id = "918273645012345679"
    edge_messages = create_edge_case_messages()
    
    logger.info(f"Testing {len(edge_messages)} edge case messages:")
    for i, msg in enumerate(edge_messages, 1):
        author_id = msg.get('author_id', 'MISSING')
        logger.info(f"Edge case {i}: author_id={repr(author_id)}, content='{msg.get('content', '')[:50]}'")
    
    handler = ObserveHandler()
    await handler._recall_from_messages(memory_service, channel_id, edge_messages)
    
    # Analyze edge case results
    unique_nodes = set(call['node_id'] for call in memory_service.recall_details)
    user_nodes = [node for node in unique_nodes if node.startswith('user/')]
    
    logger.info(f"Edge case results:")
    logger.info(f"  Total unique nodes: {len(unique_nodes)}")
    logger.info(f"  User nodes: {user_nodes}")
    
    # Should only have channel recall + valid user recall (first message has valid author_id)
    valid_user_nodes = [node for node in user_nodes if len(node) > 5 and not node.endswith('None') and not node.endswith('')]
    
    expected_valid_users = 1  # Only first message has valid author_id
    assert len(valid_user_nodes) == expected_valid_users, f"Expected {expected_valid_users} valid user nodes, got {len(valid_user_nodes)}"
    
    logger.info("✅ Edge cases test passed!")

async def test_no_messages():
    """Test with no messages"""
    logger.info("\n=== Testing Empty Message List ===")
    
    memory_service = TestMemoryService()
    channel_id = "918273645012345680"
    
    handler = ObserveHandler()
    await handler._recall_from_messages(memory_service, channel_id, [])
    
    # Should only have channel recalls
    unique_nodes = set(call['node_id'] for call in memory_service.recall_details)
    assert len(unique_nodes) == 1, f"Expected 1 node (channel only), got {len(unique_nodes)}"
    assert f"channel/{channel_id}" in unique_nodes, "Expected channel recall"
    
    logger.info("✅ Empty message list test passed!")

async def test_no_memory_service():
    """Test with no memory service"""
    logger.info("\n=== Testing No Memory Service ===")
    
    # Should not crash and should handle gracefully
    handler = ObserveHandler()
    await handler._recall_from_messages(None, "test_channel", create_realistic_discord_messages())
    
    logger.info("✅ No memory service test passed!")

async def test_message_field_variations():
    """Test various message field variations and data types"""
    logger.info("\n=== Testing Message Field Variations ===")
    
    memory_service = TestMemoryService()
    channel_id = "test_channel"
    
    # Messages with different data types for author_id
    variant_messages = [
        {"id": "1", "content": "string author_id", "author_id": "12345"},
        {"id": "2", "content": "int author_id", "author_id": 67890},  # Should be converted to string
        {"id": "3", "content": "bool author_id", "author_id": True},   # Edge case
        {"id": "4", "content": "list author_id", "author_id": ["123"]}, # Invalid type
    ]
    
    # Test each message type
    handler = ObserveHandler()
    for msg in variant_messages:
        logger.info(f"Testing message: {msg}")
        try:
            await handler._recall_from_messages(memory_service, channel_id, [msg])
        except Exception as e:
            logger.warning(f"Error processing message {msg['id']}: {e}")
    
    logger.info("✅ Message field variations test completed!")

async def main():
    """Run all integration tests"""
    logger.info("Starting ObserveHandler integration tests...")
    
    try:
        await test_real_observe_handler()
        await test_edge_cases_real_handler()
        await test_no_messages()
        await test_no_memory_service()
        await test_message_field_variations()
        
        logger.info("\n🎉 All integration tests passed!")
        logger.info("The ObserveHandler._recall_from_messages logic correctly unpacks")
        logger.info("the message structure from the Discord adapter observer.")
        
    except Exception as e:
        logger.error(f"\n❌ Integration test failed: {e}")
        import traceback
        traceback.print_exc()
        raise

if __name__ == "__main__":
    asyncio.run(main())
