import logging
import sys
import os
from typing import Optional

logger = logging.getLogger(__name__)

DEFAULT_LOG_FORMAT = '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_basic_logging(level: int = logging.INFO, 
                        log_format: str = DEFAULT_LOG_FORMAT, 
                        date_format: str = DEFAULT_LOG_DATE_FORMAT,
                        logger_instance: Optional[logging.Logger] = None,
                        prefix: Optional[str] = None):
    """
    Sets up basic logging configuration.

    Args:
        level: The logging level (e.g., logging.INFO, logging.DEBUG). This will be
            overridden by the ``LOG_LEVEL`` environment variable if present.
        log_format: The format string for log messages.
        date_format: The format string for timestamps in log messages.
        logger_instance: An optional specific logger instance to configure. 
                         If None, configures the root logger.
        prefix: An optional prefix to add to log messages for this specific setup.
    """
    
    env_level = os.getenv("LOG_LEVEL")
    if env_level:
        level_from_env = logging.getLevelName(env_level.upper())
        if isinstance(level_from_env, int):
            level = level_from_env

    if prefix:
        effective_log_format = f"{prefix} {log_format}"
    else:
        effective_log_format = log_format

    formatter = logging.Formatter(effective_log_format, datefmt=date_format)
    
    # If a specific logger instance is provided, configure it.
    # Otherwise, configure the root logger.
    if logger_instance:
        # Ensure it has a handler, or add one.
        # This avoids duplicate handlers if called multiple times on the same logger.
        if not logger_instance.handlers:
            handler = logging.StreamHandler(sys.stdout)
            logger_instance.addHandler(handler)
        
        for handler in logger_instance.handlers:
            handler.setFormatter(formatter)
        logger_instance.setLevel(level)
    else:
        # Configure the root logger
        # This will affect all loggers that don't have their own specific configuration,
        # unless propagate is set to False on child loggers.
        logging.basicConfig(level=level, format=effective_log_format, datefmt=date_format, stream=sys.stdout)

    # You can also set levels for specific noisy libraries here if needed
    # logging.getLogger("httpx").setLevel(logging.WARNING)
    # logging.getLogger("openai").setLevel(logging.WARNING)
    
    logging.info(f"Basic logging configured. Level: {logging.getLevelName(level)}")

if __name__ == '__main__':
    setup_basic_logging(level=logging.DEBUG)
    logger = logging.getLogger("logging_config_demo")
    logger.debug("Debug message")
    logger.info("Info message")
