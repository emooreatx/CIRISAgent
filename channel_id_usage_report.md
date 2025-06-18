# Channel ID Usage Report - CIRIS Agent Codebase

## Overview
This report documents all occurrences and usage patterns of channel IDs throughout the CIRIS Agent codebase, including various naming conventions and contexts.

## Channel ID Naming Variants Found
- `channel_id` - Most common, standard field name
- `destination_id` - Used in IncomingMessage schema with alias to channel_id
- `startup_channel_id` - Used in runtime initialization
- `home_channel_id` - Discord adapter config for primary communication
- `default_channel_id` - CLI adapter config
- `deferral_channel_id` - Discord adapter config for WA deferrals
- `monitored_channel_ids` - List of channels Discord monitors

## Key Schemas and Data Models

### 1. **foundational_schemas_v1.py**
- `IncomingMessage`: 
  - Field: `destination_id` (aliased as `channel_id`)
  - Used as base for all incoming messages
- `DiscordMessage`: 
  - Inherits channel_id from IncomingMessage
  - Converts between `destination_id` and `channel_id` for compatibility
- `DispatchContext`:
  - Field: `channel_id` (REQUIRED)
  - Used for action handler dispatch

### 2. **context_schemas_v1.py**
- `SystemSnapshot`:
  - Field: `channel_id: Optional[str]`
  - Stores current channel context
- `TaskContext`:
  - Field: `channel_id: Optional[str]`
  - Preserves channel from original task creation

### 3. **action_params_v1.py**
- `ObserveParams`:
  - Field: `channel_id: Optional[str]`
  - Specifies channel to observe
- `SpeakParams`:
  - Field: `channel_id: Optional[str]`
  - Target channel for messages

## Configuration Files

### 1. **Discord Adapter Config** (`discord/config.py`)
- `home_channel_id` - Primary channel for agent communication
- `deferral_channel_id` - Channel for WA deferrals
- `monitored_channel_ids` - List of channels to monitor
- Environment variables:
  - `DISCORD_HOME_CHANNEL_ID`
  - `DISCORD_CHANNEL_ID` (legacy support)
  - `DISCORD_CHANNEL_IDS` (comma-separated list)
  - `DISCORD_DEFERRAL_CHANNEL_ID`

### 2. **CLI Adapter Config** (`cli/config.py`)
- `default_channel_id` - Default channel for CLI messages
- `get_home_channel_id()` - Generates unique channel ID per CLI session
- Environment variable: `CIRIS_CLI_CHANNEL_ID`

### 3. **API Adapter Config**
- Generates channel ID based on host/port combination

## Runtime and Initialization

### 1. **main.py**
- Determines `startup_channel_id` from adapter configs
- Priority order: Discord > API > CLI
- Passes to `CIRISRuntime` constructor

### 2. **ciris_runtime.py**
- Stores `startup_channel_id` as instance variable
- Passes to service initializer and component builder
- Used as default channel for wakeup tasks

### 3. **processor/main_processor.py**
- Receives `startup_channel_id` in constructor
- Passes to sub-processors (wakeup, work, etc.)
- Used for creating preload tasks

## Action Handlers

### 1. **observe_handler.py**
- Retrieves channel_id from:
  1. Action parameters
  2. Dispatch context
  3. Thought context system snapshot
- Filters out placeholder channels (starting with "@")

### 2. **speak_handler.py**
- Retrieves channel_id similarly to observe handler
- Falls back to `snore_channel_id` if not found
- Includes channel_id in service correlations

### 3. **helpers.py**
- `_get_channel_id()` - Standardized channel retrieval logic
- Used by multiple handlers for consistency

## Task and Thought Management

### 1. **task_manager.py**
- `create_task()` - Accepts channel_id in context
- `create_wakeup_sequence_tasks()` - Uses provided channel_id
- Falls back to `DISCORD_CHANNEL_ID` env var if not provided

### 2. **thought_manager.py**
- Preserves channel_id in thought context
- Passes through processing pipeline

## Service Layer

### 1. **multi_service_sink.py**
- `send_message()` requires channel_id parameter
- `fetch_messages()` requires channel_id parameter
- Routes to appropriate communication service

### 2. **Discord Services**
- `discord_adapter.py` - Implements send/fetch with channel_id
- `discord_message_handler.py` - Handles actual Discord API calls
- `discord_observer.py` - Filters messages by monitored channels

## Database Storage

### 1. **Tasks Table**
- Channel ID stored in `context_json` field as part of ThoughtContext

### 2. **Thoughts Table**
- Channel ID preserved in `context_json` field

### 3. **Service Correlations**
- Channel ID included in request_data JSON for tracking

## Special Use Cases

### 1. **Wakeup Sequence**
- Uses `startup_channel_id` for initial greeting
- Creates wakeup tasks with this channel context

### 2. **Multi-Channel Support**
- Discord can monitor multiple channels
- Each message preserves its source channel
- Agent responds in the same channel

### 3. **Channel Filtering**
- Discord observer checks if message is from monitored channel
- Ignores messages from non-monitored channels
- Special handling for deferral channel

### 4. **Dynamic Channel Assignment**
- CLI generates unique channel per session
- API generates channel based on endpoint
- Discord uses configured channels

## Environment Variable Summary
- `DISCORD_CHANNEL_ID` - Legacy, maps to home_channel_id
- `DISCORD_HOME_CHANNEL_ID` - Primary Discord channel
- `DISCORD_CHANNEL_IDS` - Comma-separated monitored channels
- `DISCORD_DEFERRAL_CHANNEL_ID` - WA deferral channel
- `CIRIS_CLI_CHANNEL_ID` - CLI default channel

## Key Functions and Methods

### Channel ID Retrieval Priority
1. Action parameters (explicit)
2. Dispatch context
3. Thought context system snapshot
4. Environment variables
5. Adapter-specific defaults

### Channel ID Validation
- Filters out placeholders (e.g., "@username")
- Validates channel exists before use
- Provides fallback mechanisms

## Recommendations

1. **Standardization**: Consider using consistent naming (always `channel_id`)
2. **Validation**: Add channel validation at service boundaries
3. **Documentation**: Document channel ID flow in architecture docs
4. **Testing**: Ensure channel ID propagation in integration tests
5. **Monitoring**: Add telemetry for channel usage patterns