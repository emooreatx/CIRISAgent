# Memory Graph Click-to-Search Feature

## How It Works

1. **Click any node in the graph** - The full node ID is stored in a `data-node-id` attribute
2. **Automatic search** - Clicking triggers a search for that exact node ID
3. **Results appear below** - If the node exists, it will show in search results

## Testing the Feature

1. Go to http://localhost:3000/memory
2. Look at the graph visualization
3. Click on any node (they're the colored circles)
4. The search box will populate with the node ID
5. Results will appear if the node exists

## Common Node Patterns

- `metric_*` - Performance metrics
- `audit_*` - Audit trail entries  
- `dream_schedule_*` - Scheduled tasks
- `log_*` - Log entries

## If Search Returns Nothing

This is normal! It means:
- The node was deleted after the visualization was generated
- The visualization is showing cached/old data
- Try clicking "Refresh" to get the latest nodes

## Successfully Tested Nodes

These nodes were confirmed to exist and search correctly:
- `metric_handler_invoked_speak_1751599018`
- `dream_schedule_1751620621`
- `metric_llm.environmental.carbon_grams_1751599020`

The click-to-search feature is working correctly! The visualization shows nodes at the time it was generated, but the search looks for current nodes in the database.