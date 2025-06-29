"""
Unit tests for GraphQL context provider search functionality.
Tests that the provider uses search instead of direct node lookups.
"""
import pytest
from unittest.mock import Mock, AsyncMock, MagicMock
import asyncio

from ciris_engine.logic.utils.graphql_context_provider import GraphQLContextProvider, GraphQLClient
from ciris_engine.schemas.services.graph_core import GraphNode, NodeType, GraphScope
from ciris_engine.schemas.adapters.graphql_core import EnrichedContext, GraphQLUserProfile


class TestGraphQLContextSearch:
    """Test GraphQL context provider uses search for user lookups."""

    @pytest.fixture
    def mock_memory_service(self):
        """Create mock memory service with search capability."""
        memory = AsyncMock()
        memory.recall = AsyncMock(return_value=[])
        memory.search = AsyncMock(return_value=[])
        memory.export_identity_context = AsyncMock(return_value="Mock identity context")
        return memory

    @pytest.fixture
    def provider(self, mock_memory_service):
        """Create GraphQL context provider."""
        return GraphQLContextProvider(
            graphql_client=None,
            memory_service=mock_memory_service,
            enable_remote_graphql=False
        )

    @pytest.mark.asyncio
    async def test_enrich_context_uses_search_for_users(self, provider, mock_memory_service):
        """Test that enrich_context uses search to find users."""
        # Create mock task with author
        mock_task = Mock()
        mock_task.context = Mock()
        mock_task.context.initial_task_context = Mock()
        mock_task.context.initial_task_context.author_name = "TestUser"

        # Mock search to return a user node
        user_node = GraphNode(
            id="user/123456789",
            type=NodeType.USER,
            scope=GraphScope.LOCAL,
            attributes={
                "username": "TestUser",
                "display_name": "Test User",
                "user_id": "123456789"
            }
        )
        mock_memory_service.search.return_value = [user_node]

        # Call enrich_context
        result = await provider.enrich_context(mock_task, None)

        # Verify search was called with correct parameters
        mock_memory_service.search.assert_called_once()
        call_args = mock_memory_service.search.call_args

        # Check the arguments - search(query, filters)
        if call_args.args:  # Positional args
            assert call_args.args[0] == "TestUser"
            filters = call_args.kwargs.get('filters', call_args.args[1] if len(call_args.args) > 1 else None)
        else:  # Keyword args
            assert call_args.kwargs['query'] == "TestUser"
            filters = call_args.kwargs['filters']

        assert filters is not None
        assert filters.node_type == NodeType.USER.value
        assert filters.scope == GraphScope.LOCAL.value

        # Verify result contains user profile
        assert isinstance(result, EnrichedContext)
        # user_profiles is a list of tuples
        assert len(result.user_profiles) == 1
        assert result.user_profiles[0][0] == "TestUser"
        profile = result.user_profiles[0][1]
        # Check that username attribute exists
        username_attrs = [attr for attr in profile.attributes if attr.key == "username"]
        assert len(username_attrs) > 0
        assert username_attrs[0].value == "TestUser"

    @pytest.mark.asyncio
    async def test_search_matches_exact_username(self, provider, mock_memory_service):
        """Test that search results are filtered for exact username match."""
        # Create mock task
        mock_task = Mock()
        mock_task.context = Mock()
        mock_task.context.initial_task_context = Mock()
        mock_task.context.initial_task_context.author_name = "JohnDoe"

        # Mock search to return multiple users
        user_nodes = [
            GraphNode(
                id="user/111",
                type=NodeType.USER,
                scope=GraphScope.LOCAL,
                attributes={"username": "JohnDoe123", "user_id": "111"}
            ),
            GraphNode(
                id="user/222",
                type=NodeType.USER,
                scope=GraphScope.LOCAL,
                attributes={"username": "JohnDoe", "user_id": "222"}  # Exact match
            ),
            GraphNode(
                id="user/333",
                type=NodeType.USER,
                scope=GraphScope.LOCAL,
                attributes={"display_name": "John Doe", "user_id": "333"}
            )
        ]
        mock_memory_service.search.return_value = user_nodes

        # Call enrich_context
        result = await provider.enrich_context(mock_task, None)

        # Verify only exact match is included
        assert len(result.user_profiles) == 1
        assert result.user_profiles[0][0] == "JohnDoe"
        profile = result.user_profiles[0][1]
        # Check user_id attribute
        user_id_attrs = [attr for attr in profile.attributes if attr.key == "user_id"]
        assert len(user_id_attrs) > 0
        assert user_id_attrs[0].value == "222"

    @pytest.mark.asyncio
    async def test_search_checks_multiple_name_fields(self, provider, mock_memory_service):
        """Test that search checks username, display_name, and name fields."""
        # Create mock task
        mock_task = Mock()
        mock_task.context = Mock()
        mock_task.context.initial_task_context = Mock()
        mock_task.context.initial_task_context.author_name = "TestUser"

        # Test different name field scenarios
        test_cases = [
            {"username": "TestUser", "user_id": "111"},
            {"display_name": "TestUser", "user_id": "222"},
            {"name": "TestUser", "user_id": "333"}
        ]

        for attrs in test_cases:
            # Reset mock
            mock_memory_service.search.reset_mock()

            # Mock search to return node with specific attribute
            user_node = GraphNode(
                id=f"user/{attrs['user_id']}",
                type=NodeType.USER,
                scope=GraphScope.LOCAL,
                attributes=attrs
            )
            mock_memory_service.search.return_value = [user_node]

            # Call enrich_context
            result = await provider.enrich_context(mock_task, None)

            # Verify user was found
            assert len(result.user_profiles) == 1
            assert result.user_profiles[0][0] == "TestUser"
            profile = result.user_profiles[0][1]
            # Check user_id attribute
            user_id_attrs = [attr for attr in profile.attributes if attr.key == "user_id"]
            assert len(user_id_attrs) > 0
            assert user_id_attrs[0].value == attrs["user_id"]

    @pytest.mark.asyncio
    async def test_handles_search_errors_gracefully(self, provider, mock_memory_service):
        """Test that search errors are handled gracefully."""
        # Create mock task
        mock_task = Mock()
        mock_task.context = Mock()
        mock_task.context.initial_task_context = Mock()
        mock_task.context.initial_task_context.author_name = "ErrorUser"

        # Mock search to raise exception
        mock_memory_service.search.side_effect = Exception("Search failed")

        # Call enrich_context - should not raise
        result = await provider.enrich_context(mock_task, None)

        # Verify empty result
        assert isinstance(result, EnrichedContext)
        assert len(result.user_profiles) == 0

    @pytest.mark.asyncio
    async def test_handles_multiple_authors(self, provider, mock_memory_service):
        """Test that multiple authors are searched individually."""
        # Create mock task and thought with different authors
        mock_task = Mock()
        mock_task.context = Mock()
        mock_task.context.initial_task_context = Mock()
        mock_task.context.initial_task_context.author_name = "Author1"

        mock_thought = Mock()
        mock_thought.context = Mock()
        mock_thought.context.initial_task_context = Mock()
        mock_thought.context.initial_task_context.author_name = "Author2"

        # Track search calls
        search_calls = []

        async def mock_search(query, filters):
            search_calls.append(query)
            if query == "Author1":
                return [GraphNode(
                    id="user/111",
                    type=NodeType.USER,
                    scope=GraphScope.LOCAL,
                    attributes={"username": "Author1", "user_id": "111"}
                )]
            elif query == "Author2":
                return [GraphNode(
                    id="user/222",
                    type=NodeType.USER,
                    scope=GraphScope.LOCAL,
                    attributes={"username": "Author2", "user_id": "222"}
                )]
            return []

        mock_memory_service.search.side_effect = mock_search

        # Call enrich_context
        result = await provider.enrich_context(mock_task, mock_thought)

        # Verify both authors were searched
        assert "Author1" in search_calls
        assert "Author2" in search_calls

        # Verify both profiles returned
        assert len(result.user_profiles) == 2
        # Check both authors are in the results
        author_names = [profile[0] for profile in result.user_profiles]
        assert "Author1" in author_names
        assert "Author2" in author_names
