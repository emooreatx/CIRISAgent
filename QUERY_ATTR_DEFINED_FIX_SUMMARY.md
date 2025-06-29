# Query Attr-Defined Fix Summary

## Issue
MyPy was reporting "attr-defined" errors when accessing the `query` attribute on params in handlers, specifically:
- `ciris_engine/logic/handlers/memory/recall_handler.py`: Lines 46, 69, 76 - accessing `params.query`

## Root Cause
The `_validate_and_convert_params` method in `BaseActionHandler` was correctly typed with a generic TypeVar, but the type information was getting lost after the try/except block in handlers. This caused mypy to think `params` was just a generic `BaseModel` instead of the specific parameter type (e.g., `RecallParams`).

## Solution
Added explicit type annotations to the `params` variable assignment in all handlers:

```python
# Before
params = await self._validate_and_convert_params(raw_params, RecallParams)

# After  
params: RecallParams = await self._validate_and_convert_params(raw_params, RecallParams)
```

## Files Fixed
1. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/memory/recall_handler.py`
   - Added type annotation: `params: RecallParams`
   
2. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/external/speak_handler.py`
   - Added type annotation: `params: SpeakParams`
   - Removed unnecessary `# type: ignore[attr-defined]` comments
   
3. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/memory/memorize_handler.py`
   - Added type annotation: `params: MemorizeParams`
   
4. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/control/reject_handler.py`
   - Added type annotation: `params: RejectParams`
   
5. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/external/observe_handler.py`
   - Added type annotation: `params: ObserveParams`
   
6. `/home/emoore/CIRISAgent/ciris_engine/logic/handlers/external/tool_handler.py`
   - Added type annotation: `params: ToolParams`

## Result
- All "query" attr-defined errors in handlers are now resolved
- Removed unnecessary type: ignore comments
- Improved type safety throughout handler code
- No changes to functionality - only type annotations added

## Note
The base handler's `_validate_and_convert_params` method already had proper generic typing using TypeVar. The issue was purely about preserving type information across the try/except boundary in the calling code.