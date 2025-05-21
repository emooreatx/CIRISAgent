import pytest
import pytest_asyncio
from unittest.mock import MagicMock

from ciris_engine.utils.profile_loader import load_profile, DEFAULT_PROFILE_PATH
from ciris_engine.dma.factory import create_dsdma_from_profile
from ciris_engine.dma.dsdma_base import BaseDSDMA
from openai import AsyncOpenAI

@pytest.mark.asyncio
async def test_load_profile_defaults_to_default():
    profile = await load_profile(None)
    assert profile is not None
    assert profile.name.lower() == "default"

@pytest.mark.asyncio
async def test_create_dsdma_from_default_profile():
    mock_client = MagicMock(spec=AsyncOpenAI)
    dsdma = await create_dsdma_from_profile(None, mock_client, model_name="x")
    assert isinstance(dsdma, BaseDSDMA)
    assert "CIRIS Explainer" in dsdma.prompt_template
