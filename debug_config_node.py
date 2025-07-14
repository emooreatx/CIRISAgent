import asyncio
from datetime import datetime, timezone
from ciris_engine.logic.services.graph.tsdb_consolidation.query_manager import QueryManager

async def check_config_node():
    period_start = datetime(2025, 7, 13, 12, 0, 0, tzinfo=timezone.utc)
    period_end = datetime(2025, 7, 13, 18, 0, 0, tzinfo=timezone.utc)
    
    query_manager = QueryManager(memory_bus=None)
    nodes_by_type = await query_manager.query_all_nodes_in_period(period_start, period_end)
    
    # Check if config nodes were found
    print(f"Node types found: {list(nodes_by_type.keys())}")
    
    if 'config' in nodes_by_type:
        config_result = nodes_by_type['config']
        print(f"\nConfig nodes found: {len(config_result.nodes)}")
        for node in config_result.nodes:
            print(f"  - {node.id}")
            if node.id == 'config:adaptive_filter.config':
                print("    ^ This is our missing node!")
    else:
        print("\nNO config nodes found in query!")
    
    # Let's manually check what the query returns
    from ciris_engine.logic.persistence.db.core import get_db_connection
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT node_id, created_at, updated_at
            FROM graph_nodes
            WHERE scope = 'local'
              AND node_type = 'config'
              AND ((datetime(updated_at) >= datetime(?) AND datetime(updated_at) < datetime(?))
                   OR (updated_at IS NULL AND datetime(created_at) >= datetime(?) AND datetime(created_at) < datetime(?)))
        """, (
            period_start.isoformat(),
            period_end.isoformat(),
            period_start.isoformat(),
            period_end.isoformat()
        ))
        
        print("\nDirect query results for config nodes:")
        for row in cursor:
            print(f"  {row['node_id']} - created: {row['created_at']}, updated: {row['updated_at']}")

if __name__ == "__main__":
    asyncio.run(check_config_node())