import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider

@pytest.mark.asyncio
async def test_enrich_context_no_authors():
    provider = GraphQLContextProvider(enable_remote_graphql=False)
    class Task: context = {}
    result = await provider.enrich_context(Task(), None)
    assert result == {}
