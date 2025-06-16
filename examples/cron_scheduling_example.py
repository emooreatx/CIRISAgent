"""
Example: Using Cron Scheduling with TaskSchedulerService

This example demonstrates how to schedule recurring tasks using cron expressions.
"""

import asyncio
from datetime import datetime, timezone
from ciris_engine.services.task_scheduler_service import TaskSchedulerService


async def main():
    """Demonstrate cron scheduling capabilities."""
    
    # Create scheduler service
    scheduler = TaskSchedulerService(
        db_path=":memory:",  # Use in-memory database for example
        check_interval_seconds=60  # Check every minute
    )
    
    # Don't start the service (which requires database setup)
    # Just demonstrate the scheduling API
    scheduler.conn = None  # No database for this example
    
    print("=== CIRIS Task Scheduler - Cron Examples ===\n")
    
    # Example 1: Daily morning report
    daily_report = await scheduler.schedule_task(
        name="Daily Morning Report",
        goal_description="Generate and share daily status report with the team",
        trigger_prompt="Please generate the daily status report including: active tasks, completed items from yesterday, and today's priorities.",
        origin_thought_id="thought_daily_001",
        schedule_cron="0 9 * * *"  # Every day at 9:00 AM
    )
    print(f"✅ Scheduled: {daily_report.name}")
    print(f"   Cron: {daily_report.schedule_cron} (Daily at 9:00 AM)")
    print(f"   Next run: {scheduler._get_next_cron_time(daily_report.schedule_cron)}\n")
    
    # Example 2: Weekly team check-in
    weekly_checkin = await scheduler.schedule_task(
        name="Weekly Team Check-in",
        goal_description="Prepare weekly team meeting agenda and discussion points",
        trigger_prompt="Prepare the weekly team check-in agenda. Review last week's action items and gather topics for discussion.",
        origin_thought_id="thought_weekly_001",
        schedule_cron="0 10 * * 1"  # Every Monday at 10:00 AM
    )
    print(f"✅ Scheduled: {weekly_checkin.name}")
    print(f"   Cron: {weekly_checkin.schedule_cron} (Every Monday at 10:00 AM)")
    print(f"   Next run: {scheduler._get_next_cron_time(weekly_checkin.schedule_cron)}\n")
    
    # Example 3: Hourly system health check
    health_check = await scheduler.schedule_task(
        name="System Health Check",
        goal_description="Monitor system resources and report any issues",
        trigger_prompt="Perform system health check: memory usage, disk space, active services, and any errors in logs.",
        origin_thought_id="thought_health_001",
        schedule_cron="0 * * * *"  # Every hour at minute 0
    )
    print(f"✅ Scheduled: {health_check.name}")
    print(f"   Cron: {health_check.schedule_cron} (Every hour)")
    print(f"   Next run: {scheduler._get_next_cron_time(health_check.schedule_cron)}\n")
    
    # Example 4: Reminder every 30 minutes during work hours
    work_reminder = await scheduler.schedule_task(
        name="Work Hours Reminder",
        goal_description="Remind to take breaks and check priority tasks",
        trigger_prompt="Reminder: Take a short break if needed. Review current task progress and priorities.",
        origin_thought_id="thought_reminder_001",
        schedule_cron="*/30 9-17 * * 1-5"  # Every 30 minutes, 9 AM-5 PM, Monday-Friday
    )
    print(f"✅ Scheduled: {work_reminder.name}")
    print(f"   Cron: {work_reminder.schedule_cron} (Every 30 min during work hours)")
    print(f"   Next run: {scheduler._get_next_cron_time(work_reminder.schedule_cron)}\n")
    
    # Example 5: Monthly report on the 1st
    monthly_report = await scheduler.schedule_task(
        name="Monthly Summary Report",
        goal_description="Generate comprehensive monthly activity summary",
        trigger_prompt="Generate monthly summary report including: completed tasks, key achievements, issues resolved, and recommendations for next month.",
        origin_thought_id="thought_monthly_001",
        schedule_cron="0 9 1 * *"  # 9:00 AM on the 1st of every month
    )
    print(f"✅ Scheduled: {monthly_report.name}")
    print(f"   Cron: {monthly_report.schedule_cron} (1st of each month at 9:00 AM)")
    print(f"   Next run: {scheduler._get_next_cron_time(monthly_report.schedule_cron)}\n")
    
    # Show all active tasks
    print("=== Active Scheduled Tasks ===")
    active_tasks = await scheduler.get_active_tasks()
    for task in active_tasks:
        print(f"- {task.name} ({task.task_id})")
        if task.schedule_cron:
            print(f"  Cron: {task.schedule_cron}")
        
    print("\n=== Common Cron Patterns ===")
    print("* * * * *         - Every minute")
    print("*/5 * * * *       - Every 5 minutes")
    print("0 * * * *         - Every hour")
    print("0 9 * * *         - Daily at 9 AM")
    print("0 9 * * 1         - Every Monday at 9 AM")
    print("0 9 1 * *         - Monthly on the 1st at 9 AM")
    print("0 0 * * 0         - Weekly on Sunday at midnight")
    print("*/15 9-17 * * 1-5 - Every 15 min during work hours")
    
    # Note: In production, the scheduler would run continuously
    print("\n⏰ In production, the scheduler would run continuously and execute tasks at their scheduled times.")


if __name__ == "__main__":
    asyncio.run(main())