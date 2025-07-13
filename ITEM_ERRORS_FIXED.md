# Fixed "Item has no attribute" Errors Summary

## Total Errors Fixed: 30

### 1. Rate Limiter (2 errors)
**File**: `ciris_engine/logic/adapters/api/middleware/rate_limiter.py`
- **Issue**: `request.client` can be None, accessing `.host` caused "Item 'None' has no attribute 'host'"
- **Fix**: Added null checks with fallback to "unknown" when client is None

### 2. Discord Tool Service (12 errors)
**File**: `ciris_engine/logic/adapters/discord/discord_tool_service.py`
- **Issue**: Discord channel types form a union, some types (ForumChannel, CategoryChannel) don't have `send` or `fetch_message` methods
- **Fixes**:
  - Replaced `hasattr` checks with proper type narrowing using `isinstance`
  - Added specific channel type checks for TextChannel, DMChannel, Thread, VoiceChannel, StageChannel
  - Used `getattr` with defaults for optional attributes like `name` and `type`

### 3. Memory Routes (1 error)
**File**: `ciris_engine/logic/adapters/api/routes/memory.py`
- **Issue**: `node.updated_at` can be None, calling `.replace()` caused error
- **Fix**: Added null check to skip nodes with None updated_at

### 4. Agent Routes (1 error)
**File**: `ciris_engine/logic/adapters/api/routes/agent.py`
- **Issue**: `comm_service` can be None, accessing `.fetch_messages()` caused error
- **Fix**: Added null check with logging before attempting to call fetch_messages

### 5. Discord Adapter (2 errors)
**File**: `ciris_engine/logic/adapters/discord/discord_adapter.py`
- **Issue**: `channel.created_at` can be None even when attribute exists
- **Fix**: Added additional null check in the conditional: `hasattr(channel, 'created_at') and channel.created_at`

## Key Patterns Fixed

1. **Optional/Union Types**: Added proper null checks before accessing attributes
2. **Discord Channel Types**: Used isinstance for type narrowing instead of hasattr
3. **Datetime Fields**: Added null checks before calling datetime methods
4. **Service Dependencies**: Added null checks for optional service dependencies

All errors were related to accessing attributes on items that could be None or of a different type in a union.