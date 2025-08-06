#!/usr/bin/env python3
"""
Grace command-line interface.
Simple, direct, helpful.
"""

import sys

from .main import Grace


def main():
    """Main entry point."""
    grace = Grace()

    # Default command
    if len(sys.argv) < 2:
        command = "status"
    else:
        command = sys.argv[1]

    # Command mapping
    commands = {
        "status": grace.status,
        "morning": grace.morning,
        "pause": grace.pause,
        "resume": grace.resume,
        "night": grace.night,
        "deploy": grace.deploy_status,
        "deployment": grace.deploy_status,
        # Aliases
        "s": grace.status,
        "m": grace.morning,
        "p": grace.pause,
        "r": grace.resume,
        "n": grace.night,
        "d": grace.deploy_status,
    }

    if command in commands:
        print(commands[command]())
    elif command in ["help", "-h", "--help"]:
        print("Grace - Sustainable development companion\n")
        print("Commands:")
        print("  status    - Current session and system health")
        print("  morning   - Morning check-in")
        print("  pause     - Save context before break")
        print("  resume    - Resume after break")
        print("  night     - Evening choice point")
        print("  deploy    - Check deployment status")
        print("\nShort forms: s, m, p, r, n, d")
    else:
        print(f"Unknown command: {command}")
        print("Try 'grace help' for available commands")


if __name__ == "__main__":
    main()
