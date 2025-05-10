# src/ciris_engine/utils/logging_config.py
import logging
import sys

def setup_basic_logging(level=logging.INFO):
    """
    Configures basic stream logging for the application.
    """
    # More sophisticated logging (e.g., to file, with rotation, tamper-evident)
    # can be added later.
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout) # Log to stdout
        ]
    )
    logging.info("Basic logging configured.")
