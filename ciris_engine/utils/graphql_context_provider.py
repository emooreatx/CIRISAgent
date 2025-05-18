import os
import logging
from typing import Dict, Any, List
import httpx

logger = logging.getLogger(__name__)

class GraphQLClient:
    def __init__(self, endpoint: str | None = None):
        self.endpoint = endpoint or os.getenv("GRAPHQL_ENDPOINT", "http://localhost:8000/graphql")
        self._client = httpx.AsyncClient()

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
    def __init__(self, graphql_client: GraphQLClient | None = None):
        self.client = graphql_client or GraphQLClient()

    async def enrich_context(self, task, thought) -> Dict[str, Any]:
        authors: set[str] = set()
        if task and isinstance(task.context, dict):
            name = task.context.get("author_name")
            if name:
                authors.add(name)
        history: List[Dict[str, Any]] = thought.processing_context.get("history", []) if getattr(thought, "processing_context", None) else []
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
        result = await self.client.query(query, {"names": list(authors)})
        users = result.get("users", [])
        enriched = {u["name"]: {"nick": u.get("nick"), "channel": u.get("channel")}
                    for u in users}
        return {"user_profiles": enriched}
