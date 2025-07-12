# CIRIS Deferral System Design

## Overview

The CIRIS deferral system allows tasks to be deferred either:
1. **To Wise Authority** - for human guidance and approval
2. **To Time** - for scheduled future reactivation

Both types can coexist - a task can be deferred to WA with a timeout, where it reactivates automatically if no response is received.

## Core Principles

### Tasks vs Thoughts
- **Tasks are deferred, not thoughts**
- Tasks persist indefinitely until resolved
- Thoughts are ephemeral and cleaned up after 24 hours
- This ensures deferred work is never lost

### No Special Cases
- Following "no dicts, no strings, no kings" principle
- No special treatment for any task IDs
- All tasks follow the same lifecycle rules

## Implementation Details

### 1. Deferral Storage

Deferrals are stored in the `tasks` table by:
- Setting `status = 'deferred'`
- Storing deferral metadata in `context_json`:

```json
{
  "deferral": {
    "deferral_id": "defer_task123_1234567890",
    "thought_id": "thought_456",
    "reason": "Need human approval for sensitive action",
    "defer_until": "2024-01-02T10:00:00Z",  // Optional
    "requires_wa_approval": true,
    "context": { /* additional context */ },
    "created_at": "2024-01-01T10:00:00Z"
  }
}
```

### 2. Deferral Types

#### Defer to Wise Authority Only
```python
DeferParams(
    reason="Need approval for database deletion",
    defer_until=None,  # No timeout
    context={"action": "delete_user", "user_id": "123"}
)
```
- Task waits indefinitely for WA response
- Only reactivates when WA approves/rejects

#### Defer to Time Only
```python
DeferParams(
    reason="Wait for market to open",
    defer_until="2024-01-02T09:30:00Z",
    context={"action": "check_stock_prices"}
)
```
- Task automatically reactivates at specified time
- No WA approval needed
- Still sent to WA for visibility

#### Defer to Both (WA with Timeout)
```python
DeferParams(
    reason="Approval needed within 24 hours",
    defer_until="2024-01-02T10:00:00Z",
    context={"action": "process_refund", "amount": 1000}
)
```
- Task waits for WA response
- If no response by defer_until, reactivates anyway
- Whichever comes first wins

### 3. Reactivation Flow

#### WA Approval/Rejection
1. WA calls `/v1/wa/deferrals/{id}/resolve`
2. WiseAuthority service:
   - Updates task status: 'deferred' → 'pending'
   - Adds resolution to context_json
   - If approved, adds `wa_guidance` for the agent
3. Agent processor picks up pending task
4. Creates new seed thought with guidance

#### Time-based Reactivation
1. TaskScheduler monitors scheduled deferrals
2. When defer_until time passes:
   - Updates task status: 'deferred' → 'pending'
3. Agent processor picks up pending task
4. Creates new seed thought

### 4. Service Responsibilities

#### WiseAuthority Service
- Stores deferrals in tasks table
- Provides `/v1/wa/deferrals` API endpoints
- Handles WA approval/rejection
- Updates task status and context

#### TaskScheduler Service
- Monitors tasks with defer_until timestamps
- Reactivates tasks when time expires
- Uses `schedule_deferred_task()` method
- Runs checks every 60 seconds

#### DatabaseMaintenanceService
- **Does NOT clean up tasks** (removed)
- Only cleans up thoughts after 24 hours
- Ensures deferred tasks persist indefinitely

#### TSDB Consolidator
- Skips deferred tasks in consolidation
- Only consolidates completed/failed tasks
- Creates task summaries every 6 hours

#### Defer Handler
- Updates task status to 'deferred'
- Sends deferral to WiseAuthority (always)
- If defer_until present, also schedules with TaskScheduler
- Updates thought status to 'deferred'

### 5. API Endpoints

#### List Pending Deferrals
```
GET /v1/wa/deferrals
```
Returns all deferred tasks with their context

#### Resolve Deferral
```
POST /v1/wa/deferrals/{deferral_id}/resolve
{
    "approved": true,
    "reason": "Approved with modifications: limit to 100 records"
}
```
Updates task to pending with resolution

### 6. Lifecycle Summary

```
Task Created → Processing → DEFER Action
    ↓
Task Status = 'deferred'
Thoughts cleaned up after 24 hours
    ↓
Wait for trigger:
- WA approval/rejection
- defer_until time passes
    ↓
Task Status = 'pending'
    ↓
Agent creates new thought
Processing continues with guidance
```

## Benefits

1. **No Lost Work** - Deferred tasks persist indefinitely
2. **Flexible Deferrals** - Support human, time, or both
3. **Clean Architecture** - Tasks for persistence, thoughts for processing
4. **No Special Cases** - All tasks follow same rules

## Migration Notes

### From Thought-based to Task-based Deferrals
1. WiseAuthority now updates tasks table, not thoughts
2. Deferral metadata stored in task's context_json
3. Thoughts are ephemeral and get cleaned up
4. Tasks persist until explicitly resolved