import pytest
from unittest.mock import AsyncMock, MagicMock
from ciris_engine.utils.graphql_context_provider import GraphQLContextProvider

@pytest.mark.asyncio
async def test_enrich_context_no_authors():
    from ciris_engine.schemas.graphql_schemas_v1 import EnrichedContext
    
    provider = GraphQLContextProvider(enable_remote_graphql=False)
    class Task: context = {}
    result = await provider.enrich_context(Task(), None)
    
    # enrich_context returns EnrichedContext, not dict
    assert isinstance(result, EnrichedContext)
    assert result.user_profiles == {}
    assert result.identity_context is None
