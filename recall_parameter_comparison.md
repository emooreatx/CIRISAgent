# Recall Parameter Comparison Report

## Summary of Findings

I've compared the RECALL parameters across three locations:
1. **Dynamic template** in `action_instruction_generator.py` (lines 140-159)
2. **Static template** in `action_selection_pdma.yml` (line 11)
3. **Actual RecallParams schema** in `parameters.py` (lines 76-84)

## Key Findings

### 1. Parameter Names - ✅ CONSISTENT
All three locations use the same parameter names:
- `query` (optional string)
- `node_type` (optional string)
- `node_id` (optional string)
- `scope` (optional GraphScope)
- `limit` (optional integer, default: 10)

### 2. Parameter Types - ⚠️ INCONSISTENCY FOUND

#### Dynamic Template (action_instruction_generator.py):
```
"node_type"?: "agent"|"user"|"channel"|"concept"
```
- Lists only 4 specific node types as options

#### Static Template (action_selection_pdma.yml):
```
"node_type"?: string
```
- Accepts any string value

#### Actual Schema (RecallParams):
```python
node_type: Optional[str] = Field(None, description="Type of nodes to recall")
```
- Accepts any string value
- In the handler, it's converted to `NodeType` enum which supports 14 values:
  - AGENT, USER, CHANNEL, CONCEPT, CONFIG, TSDB_DATA, TSDB_SUMMARY, 
  - CONVERSATION_SUMMARY, AUDIT_ENTRY, IDENTITY_SNAPSHOT, BEHAVIORAL, 
  - SOCIAL, IDENTITY, OBSERVATION

**Issue**: The dynamic template is too restrictive, listing only 4 of the 14 valid node types.

### 3. GraphScope Values - ✅ CONSISTENT
GraphScope enum accepts these values across all locations:
- LOCAL
- IDENTITY
- ENVIRONMENT
- COMMUNITY

### 4. Optional vs Required - ✅ CONSISTENT
All parameters are optional across all three locations.

### 5. Default Values - ✅ CONSISTENT
Only `limit` has a default value of 10 across all locations.

## Recommendations

1. **Update the dynamic template** in `action_instruction_generator.py` to either:
   - List all 14 valid node types: `"agent"|"user"|"channel"|"concept"|"config"|"tsdb_data"|"tsdb_summary"|"conversation_summary"|"audit_entry"|"identity_snapshot"|"behavioral"|"social"|"identity"|"observation"`
   - Or simplify to just `string` to match the actual schema and static template

2. **Consider adding validation** in the dynamic template to mention that invalid node_type values will be rejected during execution.

3. **Update the guidance** to mention all available node types or direct users to check available types.

## Code Locations

- Dynamic Template: `/home/emoore/CIRISAgent/ciris_engine/logic/dma/action_selection/action_instruction_generator.py:142-143`
- Static Template: `/home/emoore/CIRISAgent/ciris_engine/logic/dma/prompts/action_selection_pdma.yml:11`
- RecallParams Schema: `/home/emoore/CIRISAgent/ciris_engine/schemas/actions/parameters.py:76-84`
- NodeType Enum: `/home/emoore/CIRISAgent/ciris_engine/schemas/services/graph_core.py:19-34`
- RecallHandler: `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/memory/recall_handler.py:52`