from __future__ import annotations
import logging
from typing import Optional, Any, Dict, List
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
from ciris_engine.protocols.services import MemoryService
from ciris_engine.secrets.service import SecretsService

logger = logging.getLogger(__name__)


class LocalGraphMemoryService(Service, MemoryService):
    """Graph memory backed by the persistence database."""

    def __init__(self, db_path: Optional[str] = None, secrets_service: Optional[SecretsService] = None) -> None:
        super().__init__()
        self.db_path = db_path or get_sqlite_db_full_path()
        initialize_database(db_path=self.db_path)
        self.secrets_service = secrets_service or SecretsService(db_path=self.db_path.replace('.db', '_secrets.db'))

    async def start(self) -> None:
        await super().start()

    async def stop(self) -> None:
        await super().stop()

    async def memorize(self, node: GraphNode, *args, **kwargs) -> MemoryOpResult:
        """Store a node with automatic secrets detection and processing."""
        try:
            # Process secrets in node attributes before storing
            processed_node = await self._process_secrets_for_memorize(node)
            
            persistence.add_graph_node(processed_node, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error storing node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def recall(self, node: GraphNode) -> MemoryOpResult:
        """Recall a node with automatic secrets decryption if needed."""
        try:
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                # Process secrets in recalled data
                processed_data = await self._process_secrets_for_recall(stored.attributes, "recall")
                return MemoryOpResult(status=MemoryOpStatus.OK, data=processed_data)
            return MemoryOpResult(status=MemoryOpStatus.OK, data=None)
        except Exception as e:
            logger.exception("Error recalling node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    async def forget(self, node: GraphNode) -> MemoryOpResult:
        """Forget a node and clean up any associated secrets."""
        try:
            # First retrieve the node to check for secrets
            stored = persistence.get_graph_node(node.id, node.scope, db_path=self.db_path)
            if stored:
                await self._process_secrets_for_forget(stored.attributes)
            
            persistence.delete_graph_node(node.id, node.scope, db_path=self.db_path)
            return MemoryOpResult(status=MemoryOpStatus.OK)
        except Exception as e:
            logger.exception("Error forgetting node %s: %s", node.id, e)
            return MemoryOpResult(status=MemoryOpStatus.DENIED, error=str(e))

    def export_identity_context(self) -> str:
        lines: List[Any] = []
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
        if not update_data.get("wa_authorized"):  # type: ignore[union-attr]
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
        for node in update_data.get("nodes", []):  # type: ignore[union-attr]
            if "id" not in node or "type" not in node:
                return False
            if node["type"] != NodeType.CONCEPT:
                return False
        return True

    async def _process_secrets_for_memorize(self, node: GraphNode) -> GraphNode:
        """Process secrets in node attributes during memorization."""
        if not node.attributes:
            return node
        
        # Convert attributes to JSON string for processing
        attributes_str = json.dumps(node.attributes)
        
        # Process for secrets detection and replacement
        processed_text, secret_refs = await self.secrets_service.process_incoming_text(
            attributes_str,
            context_hint=f"memorize node_id={node.id} scope={node.scope.value}"
        )
        
        # Create new node with processed attributes
        processed_attributes = json.loads(processed_text) if processed_text != attributes_str else node.attributes
        
        # Add secret references to node metadata if any were found
        if secret_refs:
            processed_attributes.setdefault("_secret_refs", []).extend([ref.secret_uuid for ref in secret_refs])
            logger.info(f"Stored {len(secret_refs)} secret references in memory node {node.id}")
        
        return GraphNode(
            id=node.id,
            type=node.type,
            scope=node.scope,
            attributes=processed_attributes
        )

    async def _process_secrets_for_recall(self, attributes: Dict[str, Any], action_type: str) -> Dict[str, Any]:
        """Process secrets in recalled attributes for potential decryption."""
        if not attributes:
            return attributes
        
        # Check if there are secret references in the attributes
        secret_refs = attributes.get("_secret_refs", [])
        if not secret_refs:
            return attributes
        
        # Auto-decrypt secrets if the action type allows it
        should_decrypt = action_type in getattr(self.secrets_service.filter.config, "auto_decrypt_for_actions", ["speak", "tool"])
        
        if should_decrypt:
            # Convert to JSON for processing
            attributes_str = json.dumps(attributes)
            
            # Attempt to decapsulate secrets
            decapsulated_text = await self.secrets_service.decapsulate_secrets(
                attributes_str,
                action_type=action_type,
                context={
                    "operation": "recall", 
                    "auto_decrypt": True
                }
            )
            
            if decapsulated_text != attributes_str:
                logger.info(f"Auto-decrypted secrets in recalled data for {action_type}")
                return json.loads(decapsulated_text)
        
        return attributes

    async def _process_secrets_for_forget(self, attributes: Dict[str, Any]) -> None:
        """Clean up secrets when forgetting a node."""
        if not attributes:
            return
        
        # Check for secret references
        secret_refs = attributes.get("_secret_refs", [])
        if secret_refs:
            # Note: We don't automatically delete secrets on FORGET since they might be
            # referenced elsewhere. This would need to be a conscious decision by the agent.
            logger.info(f"Node being forgotten contained {len(secret_refs)} secret references")
            
            # Could implement reference counting here in the future if needed


