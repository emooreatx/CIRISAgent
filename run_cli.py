#!/usr/bin/env python3
"""
run_cli.py

Simple script to run CIRIS in CLI mode for testing.
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
from ciris_engine.runtime.cli_runtime import CLIRuntime

# Configure logging
setup_basic_logging(level=logging.INFO)
logger = logging.getLogger(__name__)


async def main():
    """Main entry point."""
    # Get profile name from command line or default
    profile_name = "default"
    if len(sys.argv) > 1:
        profile_name = sys.argv[1]
        
    logger.info(f"Starting CIRIS CLI with profile: {profile_name}")
    
    # Get optional configuration
    max_rounds = int(os.getenv("CIRIS_MAX_ROUNDS", "0")) or None
    
    # Create and run CLI runtime
    runtime = CLIRuntime(
        profile_name=profile_name,
        interactive=True,
    )
    
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