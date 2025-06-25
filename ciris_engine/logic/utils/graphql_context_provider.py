import logging
import asyncio
from typing import Dict, Any, Optional
import httpx
from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.schemas.services.graph_core import GraphScope, GraphNode, NodeType
from ciris_engine.schemas.adapters.graphql_core import (
    GraphQLQuery, GraphQLResponse, UserQueryVariables, UserQueryResponse,
    UserProfile, EnrichedContext
)
from ciris_engine.logic.config.env_utils import get_env_var

logger = logging.getLogger(__name__)

class GraphQLClient:
    def __init__(self, endpoint: str | None = None) -> None:
        self.endpoint = endpoint or get_env_var("GRAPHQL_ENDPOINT", "https://localhost:8000/graphql")
        self._client = httpx.AsyncClient(timeout=3.0)

    async def query(self, query_obj: GraphQLQuery) -> GraphQLResponse:
        try:
            # Ensure endpoint is not None
            if self.endpoint is None:
                raise ValueError("GraphQL endpoint is not configured")
            payload = {
                "query": query_obj.query,
                "variables": query_obj.variables.model_dump()
            }
            if query_obj.operation_name:
                payload["operationName"] = query_obj.operation_name
                
            resp = await self._client.post(self.endpoint, json=payload)
            resp.raise_for_status()
            data = resp.json()
            return GraphQLResponse.model_validate(data)
        except Exception as exc:
            logger.error("GraphQL query failed: %s", exc)
            return GraphQLResponse()

class GraphQLContextProvider:
    def __init__(self, graphql_client: GraphQLClient | None = None,
                 memory_service: Optional[LocalGraphMemoryService] = None,
                 enable_remote_graphql: bool = False) -> None:
        self.enable_remote_graphql = enable_remote_graphql
        self.client: Optional[GraphQLClient]
        if enable_remote_graphql:
            self.client = graphql_client or GraphQLClient()
        else:
            self.client = graphql_client
        self.memory_service = memory_service

    async def enrich_context(self, task: Any, thought: Any = None) -> EnrichedContext:
        authors: Set[str] = set()
        
        # Extract author names from task context
        if task and hasattr(task, 'context'):
            if hasattr(task.context, 'initial_task_context') and task.context.initial_task_context:
                if hasattr(task.context.initial_task_context, 'author_name'):
                    authors.add(task.context.initial_task_context.author_name)
            elif isinstance(task.context, dict) and 'author_name' in task.context:
                authors.add(task.context['author_name'])
                
        # Extract author names from thought context        
        if thought and hasattr(thought, 'context'):
            if hasattr(thought.context, 'initial_task_context') and thought.context.initial_task_context:
                if hasattr(thought.context.initial_task_context, 'author_name'):
                    authors.add(thought.context.initial_task_context.author_name)
            elif isinstance(thought.context, dict) and 'author_name' in thought.context:
                authors.add(thought.context['author_name'])
        
        if not authors:
            return EnrichedContext()
            
        query_str = """
            query($names:[String!]!){
                users(names:$names){ name nick channel }
            }
        """
        
        user_profiles: Dict[str, UserProfile] = {}
        
        if self.enable_remote_graphql and self.client:
            query_obj = GraphQLQuery(
                query=query_str,
                variables=UserQueryVariables(names=list(authors))
            )
            response = await self.client.query(query_obj)
            
            if response.data and "users" in response.data:
                try:
                    user_response = UserQueryResponse.model_validate(response.data)
                    for user in user_response.users:
                        user_profiles[user.name] = UserProfile(
                            nick=user.nick,
                            channel=user.channel
                        )
                except Exception as exc:
                    logger.warning("Failed to parse user query response: %s", exc)

        # Get missing users from memory service
        missing = [name for name in authors if name not in user_profiles and name is not None]
        if self.memory_service and missing:
            from ciris_engine.schemas.services.operations import MemoryQuery
            memory_results = await asyncio.gather(
                *(self.memory_service.recall(
                    MemoryQuery(
                        node_id=n,
                        scope=GraphScope.LOCAL,
                        type=NodeType.USER,
                        include_edges=False,
                        depth=1
                    )
                ) for n in missing if n),
                return_exceptions=True
            )
            for name, mem_result in zip(missing, memory_results):
                if mem_result and not isinstance(mem_result, Exception) and isinstance(mem_result, list):
                    if mem_result and mem_result[0].attributes:
                        user_profiles[name] = UserProfile(
                            attributes=mem_result[0].attributes if isinstance(mem_result[0].attributes, dict) else {"data": mem_result[0].attributes}
                        )

        # Get identity context
        identity_block = ""
        if self.memory_service:
            try:
                identity_block = await self.memory_service.export_identity_context()
            except Exception as exc:
                logger.warning("Failed to export identity context: %s", exc)

        return EnrichedContext(
            user_profiles=user_profiles,
            identity_context=identity_block if identity_block else None
        )
