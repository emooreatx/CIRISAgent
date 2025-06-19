"""Pytest configuration and fixtures for CIRIS SDK tests."""
import pytest
import asyncio
from typing import AsyncGenerator
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from ciris_sdk import CIRISClient


@pytest.fixture
async def client() -> AsyncGenerator[CIRISClient, None]:
    """Provide a CIRIS client for tests."""
    import httpx
    
    # Check if API is running
    try:
        async with httpx.AsyncClient() as check_client:
            response = await check_client.get("http://localhost:8080/api/v1/health", timeout=1.0)
            if response.status_code != 200:
                pytest.skip("API is not running (health check failed)")
    except Exception:
        pytest.skip("API is not running (cannot connect)")
    
    async with CIRISClient(base_url="http://localhost:8080") as c:
        yield c


# Remove the event_loop fixture - let pytest-asyncio handle it
# The asyncio_mode = auto in pytest.ini will create event loops as needed