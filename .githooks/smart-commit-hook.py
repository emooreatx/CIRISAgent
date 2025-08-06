#!/usr/bin/env python3
"""
Smart commit hook that automatically re-stages files modified by pre-commit hooks.
This makes committing with hooks seamless - "the right way is the easy way".
"""

import subprocess
import sys


def run_command(cmd):
    """Run a command and return output."""
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return result.returncode, result.stdout, result.stderr


def get_modified_files():
    """Get list of modified files."""
    code, stdout, _ = run_command("git diff --name-only")
    if code == 0 and stdout:
        return stdout.strip().split("\n")
    return []


def get_staged_files():
    """Get list of staged files."""
    code, stdout, _ = run_command("git diff --cached --name-only")
    if code == 0 and stdout:
        return stdout.strip().split("\n")
    return []


def main():
    """Main smart commit logic."""
    print("🚀 Smart Commit Hook: Checking for hook modifications...")

    # Get initial state
    initial_modified = set(get_modified_files())
    initial_staged = set(get_staged_files())

    if not initial_staged:
        print("⚠️  No files staged for commit")
        return 0

    # This hook runs AFTER other pre-commit hooks
    # Check if any staged files were modified by hooks
    current_modified = set(get_modified_files())
    new_modifications = current_modified - initial_modified

    if new_modifications:
        print(f"🔄 Found {len(new_modifications)} files modified by hooks:")
        for file in new_modifications:
            print(f"   - {file}")

        print("📝 Re-staging modified files...")
        for file in new_modifications:
            run_command(f"git add {file}")

        print("✅ Files re-staged successfully!")
        print("💡 Tip: The commit will proceed with the hook-modified files.")
    else:
        print("✅ No additional modifications needed")

    return 0


if __name__ == "__main__":
    sys.exit(main())
