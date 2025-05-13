import logging
import sys
from typing import Optional # Added import

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
        level: The logging level (e.g., logging.INFO, logging.DEBUG).
        log_format: The format string for log messages.
        date_format: The format string for timestamps in log messages.
        logger_instance: An optional specific logger instance to configure. 
                         If None, configures the root logger.
        prefix: An optional prefix to add to log messages for this specific setup.
    """
    
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
    # Example usage:
    setup_basic_logging(level=logging.DEBUG)
    
    logger = logging.getLogger("MyTestApp")
    logger.debug("This is a debug message from MyTestApp.")
    logger.info("This is an info message from MyTestApp.")
    
    another_logger = logging.getLogger("AnotherModule")
    another_logger.info("Info from AnotherModule (should use root config).")

    # Example with a specific logger instance and prefix
    custom_logger = logging.getLogger("CustomPrefixedLogger")
    setup_basic_logging(logger_instance=custom_logger, level=logging.INFO, prefix="[CUSTOM]")
    custom_logger.info("This message has a custom prefix.")
    
    # Root logger messages will still use the initial basicConfig setup
    logging.info("Root logger info message.")
