"""
Main Grace class - ties everything together simply.
"""

import subprocess
from datetime import datetime

from .context import WorkContext
from .health import check_all, check_deployment
from .schedule import get_current_session, get_next_transition, get_remaining_time


class Grace:
    """Your sustainable development companion."""

    def __init__(self) -> None:
        """Initialize Grace."""
        self.context = WorkContext()

    def status(self) -> str:
        """Current status - time, session, health."""
        message = []

        # Time and session
        now = datetime.now()
        message.append(f"Time: {now.strftime('%I:%M %p')}")

        session = get_current_session()
        if session:
            remaining = get_remaining_time()
            message.append(f"Session: {session} ({remaining:.1f}h remaining)")
        else:
            next_hour, next_desc = get_next_transition()
            message.append(f"Break until {next_hour}:00 - {next_desc}")

        # Work today
        hours = self.context.get_today_hours()
        message.append(f"Today: {hours:.1f} hours worked")

        # System health
        health = check_all()

        # Show deployment if active
        if "deployment" in health:
            message.append(f"\n🚀 {health['deployment']}")

        # Show problems first
        if health.get("production") != "UP":
            message.append(f"\n🔴 Production: {health.get('production', 'UNKNOWN')}")
        if health.get("datum") not in ["HEALTHY", "HTTP 200"]:
            message.append(f"🔴 Datum: {health.get('datum', 'UNKNOWN')}")
        if health.get("ci_cd") in ["FAILURE", "FAILED"]:
            message.append(f"⚠️  CI/CD: {health.get('ci_cd')}")

        # Git status
        ctx = self.context.load()
        if ctx and ctx.get("uncommitted"):
            message.append("\n📝 You have uncommitted changes")

        return "\n".join(message)

    def morning(self) -> str:
        """Morning check-in."""
        hour = datetime.now().hour

        if hour < 7:
            return "Early start! Remember to pace yourself today."
        elif hour > 10:
            return "Morning session passed. Consider starting with midday tasks."

        message = ["Good morning. Checking systems...\n"]

        # Health check
        health = check_all()

        # Priority issues
        if health.get("production") != "UP":
            message.append(f"🔴 PRODUCTION ISSUE: {health.get('production')}")
            message.append("Priority: Check production immediately")
            return "\n".join(message)

        if health.get("ci_cd") in ["FAILURE", "FAILED"]:
            message.append("⚠️  CI/CD failed - check recent builds")

        # Normal morning
        message.append("✅ Systems operational")

        remaining = get_remaining_time()
        message.append(f"\nYou have {remaining:.1f} hours until break")
        message.append("Best for: Complex problems, architecture decisions")

        return "\n".join(message)

    def pause(self) -> str:
        """Pause for a break."""
        # Save context
        self.context.save("Taking a break")

        # Log approximate work time
        session = get_current_session()
        if session:
            # Rough estimate - you've worked part of this session
            hours = 1.5  # Conservative estimate
            self.context.log_work(hours)

        return "Context saved. Enjoy your break.\nRun 'grace resume' when you return."

    def resume(self) -> str:
        """Resume after break."""
        session = get_current_session()
        if not session:
            next_hour, next_desc = get_next_transition()
            return f"Not in work session. Next: {next_hour}:00"

        message = [f"Welcome back. {session.capitalize()} session."]

        ctx = self.context.load()
        if ctx and ctx.get("uncommitted"):
            message.append("📝 You have uncommitted changes")
            message.append(f"Last commit: {ctx.get('last_commit', 'unknown')}")

        remaining = get_remaining_time()
        message.append(f"\n{remaining:.1f} hours until next break")

        if session == "midday":
            message.append("Good for: Code review, bug fixes, documentation")
        elif session == "evening":
            message.append("Good for: Tests, refactoring, mechanical tasks")

        return "\n".join(message)

    def night(self) -> str:
        """Night session choice point."""
        hours_today = self.context.get_today_hours()

        message = ["Choice point. How are you feeling?\n"]
        message.append(f"Today: {hours_today:.1f} hours already")

        if hours_today > 6:
            message.append("You've put in a solid day.")
            message.append("Rest is earned, not weakness.")
        else:
            message.append("If you code: Pick something you WANT to explore")
            message.append("If you rest: Tomorrow you'll be fresh")

        return "\n".join(message)

    def deploy_status(self) -> str:
        """Check deployment status."""
        message = ["Deployment Status\n" + "─" * 40]

        # Get deployment info
        deployment = check_deployment()
        if deployment:
            message.append(deployment)

        # Check if OAuth fix is live (simple check)
        try:
            result = subprocess.run(
                ["curl", "-s", "https://agents.ciris.ai"], capture_output=True, text=True, timeout=10
            )
            if "/api/${agent.agent_id}/v1/auth/oauth/" in result.stdout:
                message.append("\n✅ OAuth fix is LIVE!")
                message.append("Ready to test login functionality")
            elif deployment and "in progress" in deployment:
                message.append("\n⏳ Deployment building...")
            else:
                message.append("\n⏰ OAuth fix not detected yet")
        except Exception:
            message.append("\nCould not check OAuth status")

        return "\n".join(message)
