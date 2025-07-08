# SVG Node Click Query Improvements

## Summary of Changes

### 1. **Enhanced Node ID Detection in SDK** (`memory.ts`)
- Added more node type prefixes: `thought_`, `task_`, `observation_`, `concept_`, `identity_`, `config_`, `tsdb_data_`
- Fixed edge case where IDs starting with underscore were incorrectly detected as valid
- Pattern: Must contain underscore (not at start) + 10-digit timestamp

### 2. **Added Tooltips to SVG Nodes** (`memory/page.tsx`)
- Hovering over a node shows: `Click to query: <node_id>`
- Tooltip appears above the node with proper positioning
- Dark background with white monospace text for clarity
- Tooltip is cleaned up properly on component unmount

### 3. **Improved Click Handling**
- Clear search query before setting new one to force refresh
- Added 50ms delay to ensure state update
- Shows success toast: `Querying node: <node_id>`

### 4. **Loading State for Node Details**
- Added `isLoadingNode` state
- Shows spinner overlay while loading node details
- Prevents interaction during loading
- Success/error toasts for load completion

### 5. **Visual Improvements**
- Added "Click to view full details →" hint on search result cards
- Loading spinner overlay on node details panel
- Proper handling of null selectedNode during loading

## Testing the Changes

1. **Test Node ID Detection**:
   ```typescript
   // These should be detected as node IDs:
   "thought_abc123_1234567890"
   "task_xyz_1734567890"
   "metric_cpu_usage_1234567890"
   
   // These should NOT be detected:
   "_1234567890"  // Starts with underscore
   "simple text query"  // No timestamp
   ```

2. **Test SVG Interaction**:
   - Hover over nodes to see tooltips
   - Click nodes to query them
   - Verify the query retrieves the correct node

3. **Test Loading States**:
   - Click a search result
   - Verify spinner appears while loading
   - Verify details load correctly

## Query Flow

1. User clicks SVG node → Extract `data-node-id` attribute
2. Set as search query → SDK detects it's a node ID
3. SDK sends `{node_id: "..."}` instead of `{query: "..."}`
4. Backend uses `memory_service.recall()` for direct lookup
5. Results display in search results section
6. User can click result for full details

## Benefits

- **Better UX**: Tooltips show what will happen before clicking
- **More Reliable**: Enhanced node ID detection catches more valid IDs
- **Clearer Feedback**: Loading states and success/error messages
- **Consistent Behavior**: All node types handled uniformly