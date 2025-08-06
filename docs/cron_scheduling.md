# Cron Scheduling in TaskSchedulerService

The TaskSchedulerService now supports cron-style scheduling for recurring tasks, enabling CIRIS agents to schedule regular activities like daily reports, hourly health checks, or weekly summaries.

## Features

- **Cron Expression Support**: Standard 5-field cron expressions (minute hour day month weekday)
- **Validation**: Validates cron expressions before scheduling
- **Next Run Calculation**: Shows when tasks will next execute
- **Graceful Fallback**: Works without croniter but warns about limited functionality
- **Integration**: Seamlessly integrates with existing defer_until mechanism

## Usage

```python
# Schedule a daily report at 9 AM
task = await scheduler.schedule_task(
    name="Daily Report",
    goal_description="Generate daily status report",
    trigger_prompt="Generate the daily report",
    origin_thought_id="thought_123",
    schedule_cron="0 9 * * *"  # Daily at 9:00 AM
)
```

## Common Cron Patterns

- `* * * * *` - Every minute
- `*/5 * * * *` - Every 5 minutes
- `0 * * * *` - Every hour
- `0 9 * * *` - Daily at 9 AM
- `0 9 * * 1` - Every Monday at 9 AM
- `0 9 1 * *` - Monthly on 1st at 9 AM
- `*/30 9-17 * * 1-5` - Every 30 minutes during work hours

## Implementation Details

- Uses `croniter` library for cron parsing and calculation
- Updates `last_triggered_at` after each execution
- Recurring tasks remain in "ACTIVE" status
- One-time tasks complete after execution
- Checks for due tasks based on configured interval
