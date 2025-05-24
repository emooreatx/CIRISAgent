import subprocess
from pathlib import Path
from packaging import version


def _get_git_version() -> str:
    repo_root = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "describe", "--tags", "--always"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        raw = result.stdout.strip()
        try:
            version.Version(raw)
        except version.InvalidVersion:
            return "0.0.0"
        return raw
    except Exception:
        return "0.0.0"


__version__ = _get_git_version()
