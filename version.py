import subprocess
from pathlib import Path
from packaging import version
from datetime import datetime


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


def write_build_version() -> str:
    """Write version info to a build file for release tracking."""
    build_version = _get_git_version()
    build_time = datetime.now().isoformat()
    
    build_info = f"""# Build Information
Version: {build_version}
Build Time: {build_time}
Git Commit: {_get_git_commit()}
"""
    
    build_file = Path(__file__).resolve().parent / "BUILD_INFO.txt"
    build_file.write_text(build_info)
    return build_version


def _get_git_commit() -> str:
    """Get the current git commit hash."""
    repo_root = Path(__file__).resolve().parent
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except Exception:
        return "unknown"


__version__ = _get_git_version()
