"""Test that reproduces the filter_config bug seen in logs."""

import pytest
import tempfile
import os
import sqlite3
import json
from datetime import datetime, timezone

from ciris_engine.logic.services.graph.config_service import GraphConfigService
from ciris_engine.logic.services.graph.memory_service import LocalGraphMemoryService
from ciris_engine.logic.services.lifecycle.time import TimeService
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.services.graph_core import GraphNode, GraphScope, NodeType, GraphNodeAttributes


@pytest.fixture
def time_service():
    """Create a time service for testing."""
    return TimeService()


@pytest.fixture
def temp_db():
    """Create a temporary database for testing."""
    with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
        db_path = f.name
    yield db_path
    os.unlink(db_path)


@pytest.mark.asyncio
async def test_filter_config_bug(temp_db, time_service):
    """Test that reproduces the exact filter_config bug from logs.

    The error "Failed to convert node config/filter_config to ConfigNode: 'key'"
    suggests there's a node with id="config/filter_config" that has malformed attributes.
    """
    # Initialize database
    conn = sqlite3.connect(temp_db)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            node_type TEXT NOT NULL,
            attributes_json TEXT,
            version INTEGER DEFAULT 1,
            updated_by TEXT,
            updated_at TEXT,
            PRIMARY KEY (node_id, scope)
        )
    ''')

    # Insert a malformed config node like what might exist from old code
    # This simulates what happens when a node is created with just GraphNodeAttributes
    # and no extra fields
    malformed_attrs = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": "system",
        "tags": ["config:filter"]
        # NOTE: Missing 'key' and 'value' fields!
    }

    conn.execute(
        "INSERT INTO graph_nodes (node_id, scope, node_type, attributes_json, version, updated_by, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (
            "config/filter_config",  # This is the exact ID from the error
            "LOCAL",
            "config",  # lowercase enum value
            json.dumps(malformed_attrs),
            1,
            "system",
            datetime.now(timezone.utc).isoformat()
        )
    )
    conn.commit()
    conn.close()

    # Create services
    secrets_db = temp_db.replace('.db', '_secrets.db')
    secrets_service = SecretsService(db_path=secrets_db, time_service=time_service)
    await secrets_service.start()

    memory_service = LocalGraphMemoryService(
        db_path=temp_db,
        secrets_service=secrets_service,
        time_service=time_service
    )
    await memory_service.start()

    config_service = GraphConfigService(
        graph_memory_service=memory_service,
        time_service=time_service
    )
    await config_service.start()

    # Try to list configs - this triggers query_graph which causes the error
    print("\nAttempting to list configs (this triggers the bug)...")
    configs = await config_service.list_configs()
    print(f"Successfully listed {len(configs)} configs")

    # Try to get the specific config
    print("\nAttempting to get filter_config...")
    filter_config = await config_service.get_config("filter_config")
    if filter_config:
        print(f"Found filter_config: {filter_config}")
    else:
        print("filter_config not found (expected due to malformed node)")

    # Cleanup
    await config_service.stop()
    await memory_service.stop()
    await secrets_service.stop()

    secrets_db_path = secrets_db
    if os.path.exists(secrets_db_path):
        os.unlink(secrets_db_path)


@pytest.mark.asyncio
async def test_old_node_format_compatibility(temp_db, time_service):
    """Test that we can handle nodes in old format gracefully."""
    # Initialize database and insert various malformed nodes
    conn = sqlite3.connect(temp_db)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS graph_nodes (
            node_id TEXT NOT NULL,
            scope TEXT NOT NULL,
            node_type TEXT NOT NULL,
            attributes_json TEXT,
            version INTEGER DEFAULT 1,
            updated_by TEXT,
            updated_at TEXT,
            PRIMARY KEY (node_id, scope)
        )
    ''')

    # Case 1: Node with empty attributes
    conn.execute(
        "INSERT INTO graph_nodes (node_id, scope, node_type, attributes_json) VALUES (?, ?, ?, ?)",
        ("config_empty", "LOCAL", "config", "{}")
    )

    # Case 2: Node with null attributes
    conn.execute(
        "INSERT INTO graph_nodes (node_id, scope, node_type, attributes_json) VALUES (?, ?, ?, ?)",
        ("config_null", "LOCAL", "config", None)
    )

    # Case 3: Node with only base attributes (no key/value)
    conn.execute(
        "INSERT INTO graph_nodes (node_id, scope, node_type, attributes_json) VALUES (?, ?, ?, ?)",
        ("config_base_only", "LOCAL", "config", json.dumps({
            "created_at": "2024-01-01T00:00:00",
            "created_by": "test"
        }))
    )

    conn.commit()
    conn.close()

    # Create services
    secrets_db = temp_db.replace('.db', '_secrets.db')
    secrets_service = SecretsService(db_path=secrets_db, time_service=time_service)
    await secrets_service.start()

    memory_service = LocalGraphMemoryService(
        db_path=temp_db,
        secrets_service=secrets_service,
        time_service=time_service
    )
    await memory_service.start()

    config_service = GraphConfigService(
        graph_memory_service=memory_service,
        time_service=time_service
    )
    await config_service.start()

    # This should not crash - malformed nodes should be skipped
    configs = await config_service.list_configs()
    print(f"\nSuccessfully handled malformed nodes. Found {len(configs)} valid configs")

    # Cleanup
    await config_service.stop()
    await memory_service.stop()
    await secrets_service.stop()

    if os.path.exists(secrets_db):
        os.unlink(secrets_db)


if __name__ == "__main__":
    import asyncio

    async def main():
        time_service = TimeService()
        with tempfile.NamedTemporaryFile(suffix='.db', delete=False) as f:
            temp_db = f.name

        try:
            print("Testing filter_config bug reproduction...")
            await test_filter_config_bug(temp_db, time_service)

            print("\n" + "="*60 + "\n")

            print("Testing old node format compatibility...")
            await test_old_node_format_compatibility(temp_db, time_service)

        finally:
            if os.path.exists(temp_db):
                os.unlink(temp_db)

    asyncio.run(main())
