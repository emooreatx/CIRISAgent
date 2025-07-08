#!/usr/bin/env python3
"""Test SVG node click functionality and query endpoint."""

import asyncio
import json
import logging
from datetime import datetime, timezone
import aiohttp

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

API_BASE = "http://localhost:8080"
USERNAME = "admin"
PASSWORD = "ciris_admin_password"

async def login(session):
    """Login and get auth token."""
    async with session.post(
        f"{API_BASE}/v1/auth/login",
        json={"username": USERNAME, "password": PASSWORD}
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Login failed: {text}")
        data = await resp.json()
        return data["data"]["access_token"]

async def get_svg_visualization(session, token):
    """Get SVG visualization and extract node IDs."""
    headers = {"Authorization": f"Bearer {token}"}
    
    # Get visualization
    async with session.get(
        f"{API_BASE}/v1/memory/visualize/graph",
        headers=headers,
        params={"limit": 10, "layout": "force"}
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise Exception(f"Failed to get visualization: {text}")
        svg_content = await resp.text()
        
    # Extract node IDs from SVG
    import re
    node_ids = re.findall(r'data-node-id="([^"]+)"', svg_content)
    logger.info(f"Found {len(node_ids)} nodes in SVG")
    
    return node_ids, svg_content

async def test_node_queries(session, token, node_ids):
    """Test querying each node ID."""
    headers = {"Authorization": f"Bearer {token}"}
    
    for node_id in node_ids[:5]:  # Test first 5 nodes
        logger.info(f"\nTesting node: {node_id}")
        
        # Test 1: Direct query with node_id field
        async with session.post(
            f"{API_BASE}/v1/memory/query",
            headers=headers,
            json={"node_id": node_id}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                nodes = data.get("data", [])
                logger.info(f"  Direct query: Found {len(nodes)} nodes")
                if nodes:
                    node = nodes[0]
                    logger.info(f"    Type: {node.get('type')}, Scope: {node.get('scope')}")
            else:
                text = await resp.text()
                logger.error(f"  Direct query failed: {text}")
        
        # Test 2: Query as text (simulating frontend behavior)
        async with session.post(
            f"{API_BASE}/v1/memory/query",
            headers=headers,
            json={"query": node_id}
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                nodes = data.get("data", [])
                logger.info(f"  Text query: Found {len(nodes)} nodes")
            else:
                text = await resp.text()
                logger.error(f"  Text query failed: {text}")
        
        # Test 3: Direct node endpoint
        async with session.get(
            f"{API_BASE}/v1/memory/{node_id}",
            headers=headers
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                logger.info(f"  Direct endpoint: Success")
            else:
                text = await resp.text()
                logger.error(f"  Direct endpoint failed: {text}")

async def test_sdk_node_detection():
    """Test the SDK's node ID detection logic."""
    test_cases = [
        ("metric_cpu_usage_1234567890", True),
        ("audit_entry_1234567890", True),
        ("log_error_1234567890", True),
        ("dream_schedule_daily_1234567890", True),
        ("thought_abc123_1234567890", True),
        ("simple text query", False),
        ("search for metrics", False),
        ("node_without_timestamp", False),
        ("test_node_1234567890", True),
    ]
    
    logger.info("\nTesting SDK node ID detection logic:")
    for test_id, expected in test_cases:
        # Simulate SDK detection logic
        is_node_id = (
            test_id.startswith('metric_') or 
            test_id.startswith('audit_') or 
            test_id.startswith('log_') or
            test_id.startswith('dream_schedule_') or
            (test_id.count('_') >= 1 and any(char.isdigit() for char in test_id) and len(re.findall(r'\d{10}', test_id)) > 0)
        )
        
        status = "✓" if is_node_id == expected else "✗"
        logger.info(f"  {status} '{test_id}' -> detected as node ID: {is_node_id} (expected: {expected})")

async def main():
    """Run all tests."""
    async with aiohttp.ClientSession() as session:
        # Login
        logger.info("Logging in...")
        token = await login(session)
        
        # Test SDK node detection
        await test_sdk_node_detection()
        
        # Get SVG and node IDs
        logger.info("\nGetting SVG visualization...")
        node_ids, svg_content = await get_svg_visualization(session, token)
        
        if node_ids:
            logger.info(f"Sample node IDs from SVG:")
            for node_id in node_ids[:5]:
                logger.info(f"  - {node_id}")
            
            # Test queries
            await test_node_queries(session, token, node_ids)
        else:
            logger.warning("No nodes found in SVG!")
        
        # Save SVG for inspection
        with open("test_svg_output.svg", "w") as f:
            f.write(svg_content)
        logger.info("\nSVG saved to test_svg_output.svg")

if __name__ == "__main__":
    asyncio.run(main())