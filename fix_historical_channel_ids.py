#!/usr/bin/env python3
"""Fix historical correlations with NULL channel_id values in request_data JSON."""

import sqlite3
import logging
import json
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def fix_historical_channel_ids():
    """Update correlations with NULL channel_id in request_data JSON to 'unknown'."""
    db_path = "data/ciris_engine.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check correlations where request_data has NULL channel_id
            cursor.execute("""
                SELECT COUNT(*) FROM service_correlations 
                WHERE json_extract(request_data, '$.channel_id') IS NULL
                AND request_data IS NOT NULL
                AND request_data != '{}'
            """)
            null_count = cursor.fetchone()[0]
            logger.info(f"Found {null_count} correlations with NULL channel_id in request_data")
            
            if null_count > 0:
                # Get sample of affected correlations
                cursor.execute("""
                    SELECT correlation_id, service_type, action_type, created_at, request_data
                    FROM service_correlations 
                    WHERE json_extract(request_data, '$.channel_id') IS NULL
                    AND request_data IS NOT NULL
                    AND request_data != '{}'
                    LIMIT 10
                """)
                samples = cursor.fetchall()
                logger.info("Sample affected correlations:")
                for sample in samples:
                    try:
                        req_data = json.loads(sample[4]) if sample[4] else {}
                        logger.info(f"  {sample[0]} - {sample[1]}/{sample[2]} - {sample[3]} - has channel_id: {'channel_id' in req_data}")
                    except:
                        logger.info(f"  {sample[0]} - {sample[1]}/{sample[2]} - {sample[3]} - invalid JSON")
                
                # Update the JSON to set channel_id to 'unknown'
                cursor.execute("""
                    UPDATE service_correlations
                    SET request_data = json_set(request_data, '$.channel_id', 'unknown')
                    WHERE json_extract(request_data, '$.channel_id') IS NULL
                    AND request_data IS NOT NULL
                    AND request_data != '{}'
                """)
                updated = cursor.rowcount
                conn.commit()
                logger.info(f"Updated {updated} correlations with channel_id = 'unknown' in request_data")
            
            # Verify no more NULLs remain
            cursor.execute("""
                SELECT COUNT(*) FROM service_correlations 
                WHERE json_extract(request_data, '$.channel_id') IS NULL
                AND request_data IS NOT NULL
                AND request_data != '{}'
            """)
            remaining = cursor.fetchone()[0]
            if remaining == 0:
                logger.info("✓ All NULL channel_ids in request_data have been fixed")
            else:
                logger.warning(f"⚠ Still {remaining} correlations with NULL channel_id")
                
    except Exception as e:
        logger.error(f"Error fixing historical channel_ids: {e}")
        raise

def verify_cleanup():
    """Verify that the cleanup removed stale thoughts and tasks."""
    db_path = "data/ciris_engine.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Check active thoughts count
            cursor.execute("""
                SELECT COUNT(*) FROM thoughts 
                WHERE status IN ('PENDING', 'PROCESSING')
            """)
            active_thoughts = cursor.fetchone()[0]
            logger.info(f"Active thoughts (PENDING/PROCESSING): {active_thoughts}")
            
            # Check completed thoughts count
            cursor.execute("""
                SELECT COUNT(*) FROM thoughts 
                WHERE status = 'COMPLETED'
            """)
            completed_thoughts = cursor.fetchone()[0]
            logger.info(f"Completed thoughts: {completed_thoughts}")
            
            # Check tasks
            cursor.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE status IN ('pending', 'active', 'processing')
            """)
            active_tasks = cursor.fetchone()[0]
            logger.info(f"Active tasks: {active_tasks}")
            
            # Check for orphaned thoughts (no associated task)
            cursor.execute("""
                SELECT COUNT(*) FROM thoughts t
                WHERE NOT EXISTS (
                    SELECT 1 FROM tasks 
                    WHERE task_id = t.source_task_id
                )
            """)
            orphaned_thoughts = cursor.fetchone()[0]
            logger.info(f"Orphaned thoughts (no task): {orphaned_thoughts}")
            
            # Check graph nodes - these should be preserved
            cursor.execute("SELECT COUNT(*) FROM graph_nodes")
            total_nodes = cursor.fetchone()[0]
            logger.info(f"Total graph nodes (preserved): {total_nodes}")
            
            # Check graph nodes by type
            cursor.execute("""
                SELECT node_type, COUNT(*) as count 
                FROM graph_nodes 
                GROUP BY node_type 
                ORDER BY count DESC
            """)
            node_types = cursor.fetchall()
            logger.info("Graph nodes by type:")
            for node_type, count in node_types:
                logger.info(f"  {node_type}: {count}")
            
            # Check for stale wakeup tasks
            cursor.execute("""
                SELECT COUNT(*) FROM tasks 
                WHERE description LIKE '%WAKEUP%' 
                OR description LIKE '%VERIFY_IDENTITY%'
                OR description LIKE '%EXPRESS_GRATITUDE%'
            """)
            wakeup_tasks = cursor.fetchone()[0]
            logger.info(f"Remaining wakeup-related tasks: {wakeup_tasks}")
            
            # Check specific high-activity thoughts by task
            cursor.execute("""
                SELECT t.task_id, t.description, COUNT(th.thought_id) as thought_count
                FROM tasks t
                LEFT JOIN thoughts th ON t.task_id = th.source_task_id
                WHERE th.status IN ('PENDING', 'PROCESSING')
                GROUP BY t.task_id
                HAVING thought_count > 10
                ORDER BY thought_count DESC
                LIMIT 10
            """)
            high_activity_tasks = cursor.fetchall()
            if high_activity_tasks:
                logger.info("\nTasks with many active thoughts:")
                for task_id, desc, count in high_activity_tasks:
                    logger.info(f"  {task_id}: {desc[:50]}... - {count} thoughts")
            
            # Summary
            logger.info("\n=== Cleanup Verification Summary ===")
            logger.info(f"Active thoughts: {active_thoughts}")
            logger.info(f"Active tasks: {active_tasks}")
            logger.info(f"Orphaned thoughts: {orphaned_thoughts}")
            logger.info(f"Graph nodes preserved: {total_nodes}")
            
            if active_thoughts > 100:
                logger.warning("⚠ High number of active thoughts may cause resource issues")
            if orphaned_thoughts > 0:
                logger.warning("⚠ Orphaned thoughts found - may need additional cleanup")
                
    except Exception as e:
        logger.error(f"Error verifying cleanup: {e}")
        raise

def cleanup_orphaned_thoughts():
    """Clean up orphaned thoughts that have no associated task."""
    db_path = "data/ciris_engine.db"
    
    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            
            # Delete orphaned thoughts
            cursor.execute("""
                DELETE FROM thoughts 
                WHERE thought_id IN (
                    SELECT t.thought_id FROM thoughts t
                    WHERE NOT EXISTS (
                        SELECT 1 FROM tasks 
                        WHERE task_id = t.source_task_id
                    )
                )
            """)
            deleted = cursor.rowcount
            conn.commit()
            
            if deleted > 0:
                logger.info(f"Deleted {deleted} orphaned thoughts")
            else:
                logger.info("No orphaned thoughts to delete")
                
    except Exception as e:
        logger.error(f"Error cleaning orphaned thoughts: {e}")
        raise

if __name__ == "__main__":
    logger.info("=== Fixing Historical Channel IDs ===")
    fix_historical_channel_ids()
    
    logger.info("\n=== Verifying Cleanup ===")
    verify_cleanup()
    
    logger.info("\n=== Cleaning Orphaned Thoughts ===")
    cleanup_orphaned_thoughts()
    
    logger.info("\nDone!")