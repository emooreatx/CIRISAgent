import os
import logging
import asyncio
from typing import Dict, Any, List, Optional
import httpx
from ciris_engine.adapters.local_graph_memory import LocalGraphMemoryService
from ciris_engine.schemas.graph_schemas_v1 import GraphScope

logger = logging.getLogger(__name__)

class GraphQLClient:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or os.getenv("GRAPHQL_ENDPOINT", "https://localhost:8000/graphql")
        # Use a short timeout per repository guidelines
        self._client = httpx.AsyncClient(timeout=3.0)

    async def query(self, query: str, variables: Dict[str, Any]) -> Dict[str, Any]:
        try:
            resp = await self._client.post(self.endpoint, json={"query": query, "variables": variables})
            resp.raise_for_status()
            data = resp.json()
            return data.get("data", {})
        except Exception as exc:
            logger.error("GraphQL query failed: %s", exc)
            return {}

class GraphQLContextProvider:
    def __init__(self, graphql_client: GraphQLClient | None = None,
                 memory_service: Optional[LocalGraphMemoryService] = None,
                 enable_remote_graphql: bool = False):
        self.enable_remote_graphql = enable_remote_graphql
        if enable_remote_graphql:
            self.client = graphql_client or GraphQLClient()
        else:
            self.client = graphql_client  # stored for tests but not used
        self.memory_service = memory_service

    async def enrich_context(self, task, thought) -> Dict[str, Any]:
        authors: set[str] = set()
        if task and isinstance(task.context, dict):
            name = task.context.get("author_name")
            if name:
                authors.add(name)
        history: List[Dict[str, Any]] = []  # Remove legacy processing_context usage, use only v1 fields.
        for item in history:
            name = item.get("author_name")
            if name:
                authors.add(name)
        if not authors:
            return {}
        query = """
            query($names:[String!]!){
                users(names:$names){ name nick channel }
            }
        """
        result = {}
        if self.enable_remote_graphql and self.client:
            result = await self.client.query(query, {"names": list(authors)})
        users = result.get("users", []) if result else []
        enriched = {
            u["name"]: {"nick": u.get("nick"), "channel": u.get("channel")}
            for u in users
        }

        missing = [name for name in authors if name not in enriched]
        if self.memory_service and missing:
            memory_results = await asyncio.gather(
                *(self.memory_service.recall(n, GraphScope.LOCAL) for n in missing)
            )
            for name, result in zip(missing, memory_results):
                if result and result.data:
                    enriched[name] = result.data

        identity_block = ""
        if self.memory_service:
            try:
                identity_block = self.memory_service.export_identity_context()
            except Exception as exc:
                logger.warning("Failed to export identity context: %s", exc)

        context = {}
        if enriched:
            context["user_profiles"] = enriched
        if identity_block:
            context["identity_context"] = identity_block
        return context
