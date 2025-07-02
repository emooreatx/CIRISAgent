#!/usr/bin/env python3
"""
Fix for wakeup performance issue - batch fetch thoughts to avoid serialization.

The issue: async_get_thought_by_id uses asyncio.to_thread which serializes
database access when multiple thoughts are fetched in parallel.

Solution: Add a batch fetch method and pre-fetch thoughts before parallel processing.
"""

# Step 1: Add batch fetch method to thoughts.py
batch_fetch_method = '''
def get_thoughts_by_ids(thought_ids: List[str], db_path: Optional[str] = None) -> dict[str, Thought]:
    """Fetch multiple thoughts by their IDs in a single query.
    
    Returns a dict mapping thought_id to Thought object.
    More efficient than multiple individual queries.
    """
    if not thought_ids:
        return {}
    
    placeholders = ','.join(['?'] * len(thought_ids))
    sql = f"SELECT * FROM thoughts WHERE thought_id IN ({placeholders})"
    
    result = {}
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, thought_ids)
            rows = cursor.fetchall()
            for row in rows:
                thought = map_row_to_thought(row)
                result[thought.thought_id] = thought
    except Exception as e:
        logger.exception(f"Failed to batch fetch thoughts: {e}")
    
    return result

async def async_get_thoughts_by_ids(thought_ids: List[str], db_path: Optional[str] = None) -> dict[str, Thought]:
    """Asynchronous wrapper for get_thoughts_by_ids."""
    return await asyncio.to_thread(get_thoughts_by_ids, thought_ids, db_path)
'''

# Step 2: Modify main_processor.py to pre-fetch thoughts
main_processor_changes = '''
# In _process_pending_thoughts_async, after getting the batch:

# Pre-fetch all thoughts in the batch to avoid serialization
thought_ids = [t.thought_id for t in batch]
prefetched_thoughts = await persistence.async_get_thoughts_by_ids(thought_ids)

# Then in the loop, pass the prefetched thought to avoid individual fetches:
for thought in batch:
    full_thought = prefetched_thoughts.get(thought.thought_id, thought)
    task = self._process_single_thought(full_thought, prefetched=True)
    tasks.append(task)
'''

# Step 3: Modify thought_processor to accept prefetched thoughts
thought_processor_changes = '''
# Add parameter to process_thought:
async def process_thought(
    self,
    thought_item: ProcessingQueueItem,
    context: Optional[dict] = None,
    prefetched_thought: Optional[Thought] = None
) -> Optional[ActionSelectionDMAResult]:

# Then skip fetch if prefetched:
if prefetched_thought:
    thought = prefetched_thought
    logger.info(f"[DEBUG TIMING] Using prefetched thought {thought_item.thought_id}")
else:
    logger.info(f"[DEBUG TIMING] About to fetch thought {thought_item.thought_id}")
    thought = await self._fetch_thought(thought_item.thought_id)
    logger.info(f"[DEBUG TIMING] Fetched thought {thought_item.thought_id}")
'''

print("Solution overview:")
print("1. Add batch fetch methods to reduce database queries")
print("2. Pre-fetch all thoughts in a batch before parallel processing")
print("3. Pass prefetched thoughts to avoid individual fetches")
print("\nThis will eliminate the serialization bottleneck and restore parallel processing.")