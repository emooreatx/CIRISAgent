from __future__ import annotations
import logging
from typing import Optional, Any, Dict
import asyncio
import json

from ciris_engine.config.config_manager import get_sqlite_db_full_path
from ciris_engine.persistence import initialize_database, get_db_connection
from ciris_engine import persistence

from ciris_engine.schemas.graph_schemas_v1 import (
    GraphScope,
    GraphNode,
    NodeType,
    GraphEdge,
)
from ciris_engine.schemas.memory_schemas_v1 import MemoryOpStatus, MemoryOpResult
from ciris_engine.adapters.base import Service

logger = logging.getLogger(__name__)


class LocalGraphMemoryService(Service):
    """Graph memory backed by the persistence database."""

    def __init__(self, db_path: Optional[str] = None):
        super().__init__()
        self.db_path = db_path or get_sqlite_db_full_path()
        initialize_database(db_path=self.db_path)

    async def start(self):
        await super().start()

    async def stop(self):
        await super().stop()

    async def memorize(self, node: GraphNode, *args, **kwargs) -> MemoryOpResult:
        """Store a node. Only accepts GraphNode as input."""
        try:
            persistence.add_graph_node(node, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:  # pragma: no cover - log and return error
            logger.exception("Error storing node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def recall(self, node: GraphNode) -> MemoryOpResult:
        try:
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                return MemoryOpResult(status=MemoryOpStatus.OK, data=stored.attributes)
            return MemoryOpResult(status=MemoryOpStatus.OK, data=None)
        except Exception as e:  # pragma: no cover - log and return error
            logger.exception("Error recalling node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def forget(self, node: GraphNode) -> MemoryOpResult:
        try:
            persistence.delete_graph_node(node.id, node.scope, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:  # pragma: no cover - log and return error
            logger.exception("Error forgetting node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    def export_identity_context(self) -> str:
        lines = []
        with get_db_connection(db_path=self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT node_id, attributes_json FROM graph_nodes WHERE scope = ?",
                (GraphScope.IDENTITY.value,)
            )
            for row in cursor.fetchall():
                attrs = json.loads(row["attributes_json"]) if row["attributes_json"] else {}
                lines.append(f"{row['node_id']}: {attrs}")
        return "\n".join(lines)

    async def update_identity_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update identity graph nodes based on WA feedback."""
        from datetime import datetime, timezone
        # Validate update data structure
        if not self._validate_identity_update(update_data):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Invalid identity update format"
            )
        # Check for required WA authorization
        if not update_data.get("wa_authorized"):
            return MemoryOpResult(
                status=MemoryOpStatus.DENIED,
                reason="Identity updates require WA authorization"
            )
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                persistence.delete_graph_node(node_id, GraphScope.IDENTITY, db_path=self.db_path)
            else:
                attrs = node_update.get("attributes", {})
                attrs["updated_by"] = update_data.get("wa_user_id", "unknown")
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                node = GraphNode(
                    id=node_id,
                    type=NodeType.CONCEPT,
                    scope=GraphScope.IDENTITY,
                    attributes=attrs,
                )
                persistence.add_graph_node(node, db_path=self.db_path)

        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            edge_id = f"{source}->{target}->{edge_update.get('relationship','related')}"
            if edge_update.get("action") == "delete":
                persistence.delete_graph_edge(edge_id, db_path=self.db_path)
            else:
                attrs = edge_update.get("attributes", {})
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relationship=edge_update.get("relationship", "related"),
                    scope=GraphScope.IDENTITY,
                    weight=edge_update.get("weight", 1.0),
                    attributes=attrs,
                )
                persistence.add_graph_edge(edge, db_path=self.db_path)

        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    async def update_environment_graph(self, update_data: Dict[str, Any]) -> MemoryOpResult:
        """Update environment graph based on WA feedback."""
        from datetime import datetime, timezone
        # Example: No WA required, but could add more validation as needed
        for node_update in update_data.get("nodes", []):
            node_id = node_update["id"]
            if node_update.get("action") == "delete":
                persistence.delete_graph_node(node_id, GraphScope.ENVIRONMENT, db_path=self.db_path)
            else:
                attrs = node_update.get("attributes", {})
                attrs["updated_at"] = datetime.now(timezone.utc).isoformat()
                node = GraphNode(
                    id=node_id,
                    type=NodeType.CONCEPT,
                    scope=GraphScope.ENVIRONMENT,
                    attributes=attrs,
                )
                persistence.add_graph_node(node, db_path=self.db_path)
        for edge_update in update_data.get("edges", []):
            source = edge_update["source"]
            target = edge_update["target"]
            edge_id = f"{source}->{target}->{edge_update.get('relationship','related')}"
            if edge_update.get("action") == "delete":
                persistence.delete_graph_edge(edge_id, db_path=self.db_path)
            else:
                attrs = edge_update.get("attributes", {})
                edge = GraphEdge(
                    source=source,
                    target=target,
                    relationship=edge_update.get("relationship", "related"),
                    scope=GraphScope.ENVIRONMENT,
                    weight=edge_update.get("weight", 1.0),
                    attributes=attrs,
                )
                persistence.add_graph_edge(edge, db_path=self.db_path)
        return MemoryOpResult(
            status=MemoryOpStatus.OK,
            data={
                "nodes_updated": len(update_data.get("nodes", [])),
                "edges_updated": len(update_data.get("edges", []))
            }
        )

    def _validate_identity_update(self, update_data: Dict[str, Any]) -> bool:
        """Validate identity update structure."""
        required_fields = ["wa_user_id", "wa_authorized", "update_timestamp"]
        if not all(field in update_data for field in required_fields):
            return False
        for node in update_data.get("nodes", []):
            if "id" not in node or "type" not in node:
                return False
            if node["type"] != NodeType.CONCEPT:
                return False
        return True


