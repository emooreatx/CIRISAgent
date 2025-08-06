"""
Work context management - preserve state across breaks.
"""

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional


class WorkContext:
    """Manages work context and state."""

    def __init__(self):
        """Initialize context manager."""
        self.context_dir = Path.home() / ".grace"
        self.context_dir.mkdir(exist_ok=True)
        self.context_file = self.context_dir / "context.json"
        self.work_log = self.context_dir / "work_log.json"

    def save(self, message: str = "") -> None:
        """Save current work context."""
        context = {
            "timestamp": datetime.now().isoformat(),
            "git_branch": self._get_git_branch(),
            "last_commit": self._get_last_commit(),
            "uncommitted": self._has_uncommitted_changes(),
            "message": message,
        }

        with open(self.context_file, "w") as f:
            json.dump(context, f, indent=2)

    def load(self) -> Optional[Dict]:
        """Load saved context."""
        if not self.context_file.exists():
            return None
        with open(self.context_file) as f:
            return json.load(f)

    def log_work(self, hours: float, note: str = "") -> None:
        """Log work hours."""
        log_entry = {"date": datetime.now().isoformat(), "hours": hours, "note": note}

        logs = []
        if self.work_log.exists():
            with open(self.work_log) as f:
                logs = json.load(f)

        logs.append(log_entry)

        # Keep last 30 days
        if len(logs) > 30:
            logs = logs[-30:]

        with open(self.work_log, "w") as f:
            json.dump(logs, f, indent=2)

    def get_today_hours(self) -> float:
        """Get hours worked today."""
        if not self.work_log.exists():
            return 0.0

        today = datetime.now().date().isoformat()
        total = 0.0

        with open(self.work_log) as f:
            logs = json.load(f)

        for entry in logs:
            if entry["date"].startswith(today):
                total += entry["hours"]

        return total

    def _get_git_branch(self) -> str:
        """Get current git branch."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except:
            return "unknown"

    def _get_last_commit(self) -> str:
        """Get last commit message."""
        try:
            result = subprocess.run(
                ["git", "log", "-1", "--pretty=%s"],
                capture_output=True,
                text=True,
                check=True,
            )
            return result.stdout.strip()
        except:
            return "no commits"

    def _has_uncommitted_changes(self) -> bool:
        """Check for uncommitted changes."""
        try:
            result = subprocess.run(
                ["git", "status", "--porcelain"],
                capture_output=True,
                text=True,
                check=True,
            )
            return bool(result.stdout.strip())
        except:
            return False
