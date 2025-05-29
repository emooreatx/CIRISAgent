#!/usr/bin/env python3
"""
run_cli.py

Simple script to run CIRIS with CLI integration.
Usage: python run_cli.py [profile_name]
"""
import os
import sys
import asyncio
import logging
from pathlib import Path

# Add parent directory to path if running from scripts directory
sys.path.insert(0, str(Path(__file__).parent))

from ciris_engine.utils.logging_config import setup_basic_logging
from ciris_engine.adapters.cli.cli_runtime import CLIRuntime

# Configure logging
setup_basic_logging(level=logging.INFO)

# Set up file logging
log_file = Path("cli_agent.log")
file_handler = logging.FileHandler(log_file, mode='a')
file_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
file_handler.setLevel(logging.INFO)

# Add file handler to root logger
root_logger = logging.getLogger()
root_logger.addHandler(file_handler)

# Reduce console logging to WARNING+
for handler in root_logger.handlers:
    if isinstance(handler, logging.StreamHandler) and handler.stream == sys.stdout:
        handler.setLevel(logging.WARNING)

logger = logging.getLogger(__name__)

async def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Run CIRIS CLI agent')
    parser.add_argument('profile', nargs='?', default='default', help='Agent profile name')
    parser.add_argument('--non-interactive', action='store_true', help='Run in non-interactive mode')
    parser.add_argument('--max-rounds', type=int, help='Maximum processing rounds')
    
    args = parser.parse_args()
    
    # Get profile name from args or environment
    profile_name = args.profile
    if os.getenv("CIRIS_PROFILE"):
        profile_name = os.getenv("CIRIS_PROFILE")

    logger.info(f"Starting CIRIS CLI agent with profile: {profile_name}")

    max_rounds = args.max_rounds or int(os.getenv("CIRIS_MAX_ROUNDS", "0")) or None
    interactive = not args.non_interactive

    runtime = CLIRuntime(
        profile_name=profile_name,
        interactive=interactive,
    )
    try:
        await runtime.initialize()
    except Exception as e:
        logger.error(f"Failed to initialize CLI runtime: {e}", exc_info=True)
        sys.exit(1)
    logger.info("CLI runtime initialized successfully")

    try:
        await runtime.run(max_rounds=max_rounds)
    except KeyboardInterrupt:
        logger.info("Received interrupt signal, shutting down...")
    except Exception as e:
        logger.error(f"Unhandled exception: {e}", exc_info=True)
    finally:
        await runtime.shutdown()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown complete")
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)