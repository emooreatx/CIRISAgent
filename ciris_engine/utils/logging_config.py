import logging
import sys
import os
from typing import Optional
from pathlib import Path
from datetime import datetime

logger = logging.getLogger(__name__)

DEFAULT_LOG_FORMAT = '%(asctime)s.%(msecs)03d - %(name)s - %(levelname)s - %(message)s'
DEFAULT_LOG_DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def setup_basic_logging(level: int = logging.INFO, 
                        log_format: str = DEFAULT_LOG_FORMAT, 
                        date_format: str = DEFAULT_LOG_DATE_FORMAT,
                        logger_instance: Optional[logging.Logger] = None,
                        prefix: Optional[str] = None,
                        log_to_file: bool = True,
                        log_dir: str = "logs",
                        console_output: bool = False):
    """
    Sets up basic logging configuration with file output and optional console output.

    Args:
        level: The logging level (e.g., logging.INFO, logging.DEBUG)
        log_format: The format string for log messages
        date_format: The format string for timestamps in log messages
        logger_instance: An optional specific logger instance to configure
        prefix: An optional prefix to add to log messages
        log_to_file: Whether to also log to a file
        log_dir: Directory for log files
        console_output: Whether to also output to console (default: False for clean log-file-only operation)
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
    
    # Get the target logger
    target_logger = logger_instance or logging.getLogger()
    
    # Clear any existing handlers to avoid duplicates
    target_logger.handlers = []
    
    # Console handler (only if explicitly requested)
    if console_output:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        target_logger.addHandler(console_handler)
    
    # File handler
    if log_to_file:
        # Create log directory if it doesn't exist
        log_path = Path(log_dir)
        log_path.mkdir(exist_ok=True)
        
        # Create filename with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_filename = log_path / f"ciris_agent_{timestamp}.log"
        
        file_handler = logging.FileHandler(log_filename, encoding='utf-8')
        file_handler.setFormatter(formatter)
        target_logger.addHandler(file_handler)
        
        # Also create a symlink to latest.log for easy access
        latest_link = log_path / "latest.log"
        if latest_link.exists():
            latest_link.unlink()
        try:
            latest_link.symlink_to(log_filename.name)
        except Exception:
            # Symlinks might not work on Windows
            pass
    
    target_logger.setLevel(level)
    target_logger.propagate = False
    
    # Configure specific noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("openai").setLevel(logging.WARNING)
    
    log_msg = f"Logging configured. Level: {logging.getLevelName(level)}"
    if log_to_file:
        log_msg += f", Log file: {log_filename}"
    logging.info(log_msg)

if __name__ == '__main__':
    setup_basic_logging(level=logging.DEBUG)
    logger = logging.getLogger("logging_config_demo")
    logger.debug("Debug message")
    logger.info("Info message")
    logger = logging.getLogger("logging_config_demo")
    logger.debug("Debug message")
    logger.info("Info message")
