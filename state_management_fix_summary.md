# State Management Test Fixes Summary

## Problem
The test failures were caused by state management changes where:
1. `StateManager` now defaults to `SHUTDOWN` state instead of `WAKEUP`
2. `SHUTDOWN` state was designed to be terminal (no transitions allowed FROM it)
3. Tests were expecting the old behavior where agent started in `WAKEUP` state

## Changes Made

### 1. StateManager Updates (`ciris_engine/processor/state_manager.py`)
- Added `SHUTDOWN -> WAKEUP` as a valid transition for startup sequence
- Modified the transition logic to allow ONLY `SHUTDOWN -> WAKEUP` transition from SHUTDOWN state
- Added metadata initialization for the initial state in the constructor
- Updated comments to reflect the new behavior

### 2. AgentProcessor Updates (`ciris_engine/processor/main_processor.py`)
- Changed initial state from `WAKEUP` to `SHUTDOWN` to match StateManager default
- Updated `start_processing` method to handle transition from SHUTDOWN to WAKEUP
- Added proper handling for unexpected states during startup

### 3. Test Updates

#### `tests/ciris_engine/processor/test_state_manager.py`
- Updated `test_valid_transition_records_history` to start from WAKEUP and test valid transitions
- Fixed `test_invalid_transition_does_not_change_state` to test actual invalid transitions
- Fixed `test_state_duration` to start in WAKEUP state
- Updated `test_shutdown_state_is_terminal` to reflect that SHUTDOWN->WAKEUP is now allowed
- Added tests for default initial state and transitions to shutdown

#### `tests/ciris_engine/processor/test_agent_processor.py`
- Added assertion to verify agent starts in SHUTDOWN state
- Test now correctly expects the SHUTDOWN -> WAKEUP transition

#### `tests/ciris_engine/runtime/test_ciris_runtime.py`
- Updated shutdown sequence test to properly mock state manager
- Added proper state transitions in the mock setup
- Changed assertion from checking `stop_processing` call to verifying state transition

## Result
All state management related tests are now passing. The changes maintain the intended behavior where:
- Agent starts in SHUTDOWN state
- SHUTDOWN -> WAKEUP is allowed only for startup
- All other transitions FROM SHUTDOWN are blocked
- Any state can transition TO SHUTDOWN
- The shutdown sequence properly transitions to SHUTDOWN state