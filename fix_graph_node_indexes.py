#!/usr/bin/env python3
"""Add missing indexes to graph_nodes table for better query performance."""

import sqlite3
import logging
import time

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def add_graph_node_indexes():
    """Add indexes to improve TSDB query performance."""
    db_path = "data/ciris_engine.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check existing indexes
            cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='graph_nodes'")
            existing_indexes = [row[0] for row in cursor.fetchall()]
            logger.info(f"Existing indexes: {existing_indexes}")
            
            indexes_to_create = [
                ("idx_graph_nodes_type", "node_type"),
                ("idx_graph_nodes_created", "created_at"),
                ("idx_graph_nodes_type_scope_created", "node_type, scope, created_at"),
                ("idx_graph_nodes_tsdb_lookup", "node_type, scope, created_at DESC")
            ]
            
            for index_name, columns in indexes_to_create:
                if index_name not in existing_indexes:
                    logger.info(f"Creating index {index_name} on columns: {columns}")
                    start_time = time.time()
                    cursor.execute(f"CREATE INDEX {index_name} ON graph_nodes ({columns})")
                    elapsed = time.time() - start_time
                    logger.info(f"Created index {index_name} in {elapsed:.2f} seconds")
                else:
                    logger.info(f"Index {index_name} already exists")
            
            conn.commit()
            
            # Analyze table to update statistics
            logger.info("Running ANALYZE on graph_nodes table...")
            cursor.execute("ANALYZE graph_nodes")
            
            # Test the query performance
            logger.info("\nTesting query performance...")
            start_time = time.time()
            cursor.execute("""
                SELECT COUNT(*)
                FROM graph_nodes
                WHERE node_type = 'tsdb_data'
                  AND scope = 'LOCAL'
                  AND datetime(created_at) >= datetime('2025-07-15T00:00:00')
                  AND datetime(created_at) <= datetime('2025-07-16T00:00:00')
            """)
            count = cursor.fetchone()[0]
            elapsed = time.time() - start_time
            logger.info(f"Query returned {count} rows in {elapsed:.2f} seconds")
            
            # Check query plan
            cursor.execute("""
                EXPLAIN QUERY PLAN
                SELECT node_id, attributes_json, created_at
                FROM graph_nodes
                WHERE node_type = 'tsdb_data'
                  AND scope = 'LOCAL'
                  AND datetime(created_at) >= datetime('2025-07-15T00:00:00')
                  AND datetime(created_at) <= datetime('2025-07-16T00:00:00')
                ORDER BY created_at DESC
                LIMIT 1000
            """)
            plan = cursor.fetchall()
            logger.info("\nQuery execution plan:")
            for row in plan:
                logger.info(f"  {row}")
                
    except Exception as e:
        logger.error(f"Error adding indexes: {e}")
        raise

if __name__ == "__main__":
    logger.info("=== Adding Graph Node Indexes ===")
    add_graph_node_indexes()
    logger.info("\nDone!")