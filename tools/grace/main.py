"""
Main Grace class - ties everything together simply.
"""

import os
import subprocess
from datetime import datetime

from .context import WorkContext
from .health import check_all, check_deployment
from .schedule import get_current_session, get_next_transition


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
            message.append(f"Session: {session}")
            # Anti-Goodhart: "What gets measured gets gamed"
            # We show sessions for rhythm, not hours for performance
        else:
            next_hour, next_desc = get_next_transition()
            message.append(f"Break until {next_hour}:00 - {next_desc}")

        # System health
        health = check_all()

        # Show deployment if active
        if "deployment" in health:
            message.append(f"\n🚀 {health['deployment']}")

        # ALWAYS check production incidents - they can happen even when service is UP
        prod_containers = ["ciris-agent-datum", "container0", "container1"]
        ssh_key = os.path.expanduser("~/.ssh/ciris_deploy")

        if os.path.exists(ssh_key):
            # We have SSH access, check production incidents
            for container in prod_containers:
                try:
                    result = subprocess.run(
                        [
                            "ssh",
                            "-i",
                            ssh_key,
                            "root@108.61.119.117",
                            f"docker exec {container} tail -n 20 /app/logs/incidents_latest.log | grep ERROR | tail -3",
                        ],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        message.append(f"\n⚠️ Recent errors in {container}:")
                        for line in result.stdout.strip().split("\n")[:2]:  # Show max 2 errors
                            # Extract just the error message part
                            if " - ERROR - " in line:
                                error_part = line.split(" - ERROR - ")[-1][:80]  # First 80 chars
                                message.append(f"  • {error_part}...")
                        break  # Only show first container with errors
                except:
                    pass  # Silent fail, don't disrupt status

        # Show other problems
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

        message.append("\nMorning session active")
        message.append("Best for: Complex problems, architecture decisions")
        message.append("\n💡 Goodhart's Law: Optimizing for hours worked optimizes for sitting, not solving")

        return "\n".join(message)

    def pause(self) -> str:
        """Pause for a break."""
        # Save context
        self.context.save("Taking a break")

        # Session awareness, not time tracking
        session = get_current_session()
        # Anti-pattern avoided: Not tracking hours prevents gaming the metric

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

        message.append(f"\n{session.capitalize()} session in progress")

        if session == "midday":
            message.append("Good for: Code review, bug fixes, documentation")
        elif session == "evening":
            message.append("Good for: Tests, refactoring, mechanical tasks")

        return "\n".join(message)

    def night(self) -> str:
        """Night session choice point."""
        message = ["Choice point. How are you feeling?\n"]

        # Anti-Goodhart: Judge by energy and clarity, not hours logged
        message.append("If you code: Pick something you WANT to explore")
        message.append("If you rest: Tomorrow you'll be fresh")
        message.append("\n🎯 Reminder: Quality emerges from well-rested minds, not exhausted ones")

        return "\n".join(message)

    def incidents(self, container_name: str = "ciris-agent-datum") -> str:
        """Check incidents log for a specific container.

        Args:
            container_name: Docker container name (default: ciris-agent-datum)

        Returns:
            Formatted incidents report
        """
        message = [f"Incidents Check: {container_name}\n" + "─" * 40]

        # Check if this is a production container and SSH key exists
        prod_containers = ["ciris-agent-datum", "container0", "container1"]
        ssh_key = os.path.expanduser("~/.ssh/ciris_deploy")

        if container_name in prod_containers and os.path.exists(ssh_key):
            # Try SSH to production
            try:
                result = subprocess.run(
                    [
                        "ssh",
                        "-i",
                        ssh_key,
                        "root@108.61.119.117",
                        f"docker exec {container_name} tail -n 100 /app/logs/incidents_latest.log",
                    ],
                    capture_output=True,
                    text=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    message[0] = f"Incidents Check: {container_name} (PRODUCTION)\n" + "─" * 40
                else:
                    # SSH failed, fall back to local
                    result = subprocess.run(
                        ["docker", "exec", container_name, "tail", "-n", "100", "/app/logs/incidents_latest.log"],
                        capture_output=True,
                        text=True,
                        timeout=5,
                    )
            except Exception:
                # SSH failed, fall back to local
                result = subprocess.run(
                    ["docker", "exec", container_name, "tail", "-n", "100", "/app/logs/incidents_latest.log"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
        else:
            # Local Docker check
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "tail", "-n", "100", "/app/logs/incidents_latest.log"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
            except Exception:
                # Final fallback
                message.append(f"❌ Could not access container {container_name}")
                message.append("Container may not exist or Docker/SSH is not available")
                return "\n".join(message)

        if result.returncode != 0:
            message.append(f"❌ Could not access container {container_name}")
            message.append("Container may not exist or Docker is not available")
            return "\n".join(message)

        if not result.stdout.strip():
            message.append("✅ No incidents found - log is clean!")
            return "\n".join(message)

        lines = result.stdout.strip().split("\n")

        # Analyze errors
        error_types = {}
        recent_errors = []

        for line in lines:
            if "ERROR" in line:
                # Track recent errors
                recent_errors.append(line)

                # Categorize errors
                if "AttributeError: 'NoneType'" in line:
                    error_types["NoneType errors"] = error_types.get("NoneType errors", 0) + 1
                elif "ValidationError" in line:
                    error_types["Validation errors"] = error_types.get("Validation errors", 0) + 1
                elif "ImportError" in line:
                    error_types["Import errors"] = error_types.get("Import errors", 0) + 1
                elif "KeyError" in line:
                    error_types["Key errors"] = error_types.get("Key errors", 0) + 1
                elif "TypeError" in line:
                    error_types["Type errors"] = error_types.get("Type errors", 0) + 1
                else:
                    error_types["Other errors"] = error_types.get("Other errors", 0) + 1

        # Report summary
        if error_types:
            message.append(f"\n🚨 Found {sum(error_types.values())} errors:")
            for error_type, count in sorted(error_types.items(), key=lambda x: -x[1]):
                message.append(f"  • {error_type}: {count}")

            # Show last 5 errors
            message.append("\nRecent errors (last 5):")
            for error in recent_errors[-5:]:
                # Extract key info
                if "File" in error:
                    # Try to extract file and line
                    parts = error.split("File")
                    if len(parts) > 1:
                        file_info = parts[1].split(",")[0].strip()
                        message.append(f"  📍 {file_info}")
                else:
                    # Show truncated error
                    if len(error) > 100:
                        error = error[:97] + "..."
                    message.append(f"  • {error}")

            message.append("\n💡 RCA Mode:")
            message.append("  docker exec " + container_name + " python debug_tools.py")
            message.append("  Check traces, thoughts, and handler metrics")
        else:
            message.append("✅ No ERROR entries found in recent logs")

        return "\n".join(message)

    def check_incidents(self, container_name: str = None) -> str:
        """Check incidents_latest.log for critical errors.

        Args:
            container_name: Docker container name to check. If None, checks local log.

        Returns:
            Formatted string with incidents summary, or empty string if no issues.
        """
        message = []

        # Try Docker container first if name provided
        if container_name:
            try:
                result = subprocess.run(
                    ["docker", "exec", container_name, "tail", "-n", "50", "/app/logs/incidents_latest.log"],
                    capture_output=True,
                    text=True,
                    timeout=5,
                )
                if result.returncode == 0 and result.stdout.strip():
                    lines = result.stdout.strip().split("\n")
                    # Count error types
                    error_counts = {}
                    for line in lines:
                        if "ERROR" in line:
                            # Extract error type
                            if "AttributeError" in line:
                                error_counts["AttributeError"] = error_counts.get("AttributeError", 0) + 1
                            elif "ValidationError" in line:
                                error_counts["ValidationError"] = error_counts.get("ValidationError", 0) + 1
                            elif "ImportError" in line:
                                error_counts["ImportError"] = error_counts.get("ImportError", 0) + 1
                            elif "KeyError" in line:
                                error_counts["KeyError"] = error_counts.get("KeyError", 0) + 1
                            else:
                                error_counts["Other"] = error_counts.get("Other", 0) + 1

                    if error_counts:
                        message.append(f"\n🚨 Incidents in {container_name}:")
                        for error_type, count in error_counts.items():
                            message.append(f"  - {error_type}: {count} errors")

                        # Show last few lines for context
                        message.append("\nLast 3 errors:")
                        error_lines = [l for l in lines if "ERROR" in l][-3:]
                        for line in error_lines:
                            # Truncate long lines
                            if len(line) > 80:
                                line = line[:77] + "..."
                            message.append(f"  {line}")
            except Exception:
                # Silently fail if container doesn't exist or Docker not available
                pass

        # Try local log file
        else:
            try:
                with open("/app/logs/incidents_latest.log", "r") as f:
                    lines = f.readlines()[-50:]  # Last 50 lines

                error_counts = {}
                for line in lines:
                    if "ERROR" in line:
                        # Extract error type
                        if "AttributeError" in line:
                            error_counts["AttributeError"] = error_counts.get("AttributeError", 0) + 1
                        elif "ValidationError" in line:
                            error_counts["ValidationError"] = error_counts.get("ValidationError", 0) + 1
                        elif "ImportError" in line:
                            error_counts["ImportError"] = error_counts.get("ImportError", 0) + 1
                        else:
                            error_counts["Other"] = error_counts.get("Other", 0) + 1

                if error_counts:
                    message.append("\n🚨 Local incidents detected:")
                    for error_type, count in error_counts.items():
                        message.append(f"  - {error_type}: {count} errors")
            except FileNotFoundError:
                # No local incidents log - that's fine
                pass
            except Exception:
                # Other errors - silently fail
                pass

        return "\n".join(message) if message else ""

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

        # Check incidents log if available (for production containers)
        incidents = self.check_incidents()
        if incidents:
            message.append(incidents)

        return "\n".join(message)

    def precommit(self) -> str:
        """Check and fix pre-commit issues."""
        message = ["Pre-commit Status\n" + "─" * 40]

        # First run pre-commit to see issues
        try:
            result = subprocess.run(["pre-commit", "run", "--all-files"], capture_output=True, text=True, timeout=60)

            # Count failures
            failures = result.stdout.count("Failed")
            passes = result.stdout.count("Passed")

            message.append(f"✅ Passed: {passes} hooks")
            if failures > 0:
                message.append(f"❌ Failed: {failures} hooks")

                # Parse specific failures
                if "black" in result.stdout and "Failed" in result.stdout:
                    message.append("\n🔧 Black: Files need formatting")
                    message.append("  Fix: black . --exclude=venv")

                if "isort" in result.stdout and "Failed" in result.stdout:
                    message.append("\n🔧 Isort: Imports need sorting")
                    message.append("  Fix: isort . --skip=venv")

                if "ruff" in result.stdout and "Failed" in result.stdout:
                    # Count ruff errors
                    ruff_errors = result.stdout.count("E")
                    message.append(f"\n🔧 Ruff: {ruff_errors} linting errors")
                    message.append("  Fix: ruff check --fix")

                if "mypy" in result.stdout and "Failed" in result.stdout:
                    message.append("\n🔧 MyPy: Type annotation errors")
                    message.append("  Analyze: python -m tools.ciris_mypy_toolkit analyze")
                    message.append("  Fix: python -m tools.ciris_mypy_toolkit fix --systematic")

                if "Dict[str, Any]" in result.stdout:
                    dict_count = result.stdout.count("Dict[str, Any]")
                    message.append(f"\n⚠️  Dict[str, Any]: {dict_count} violations")
                    message.append("  This violates 'No Dicts' principle")

                message.append("\n💡 Quick fix all formatters:")
                message.append("  black . --exclude=venv && isort . --skip=venv")
                message.append("\n💡 Smart commit (handles hook modifications):")
                message.append('  ./tools/smart_commit.sh "your message"')
            else:
                message.append("\n🎉 All pre-commit hooks passing!")

        except subprocess.TimeoutExpired:
            message.append("⏱️  Pre-commit check timed out")
        except Exception as e:
            message.append(f"❌ Error running pre-commit: {e}")

        return "\n".join(message)
