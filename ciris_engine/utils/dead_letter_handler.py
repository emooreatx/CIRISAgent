"""
Dead Letter Queue Handler for capturing WARNING and ERROR level log messages.
"""
import logging
import os
from pathlib import Path
from datetime import datetime
from typing import Optional


class DeadLetterQueueHandler(logging.Handler):
    """
    A logging handler that writes WARNING and ERROR level messages to a separate file.
    This acts as a "dead letter queue" for problematic log messages that need attention.
    """
    
    def __init__(self, log_dir: str = "logs", filename_prefix: str = "dead_letter"):
        super().__init__()
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create dead letter log file with timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{filename_prefix}_{timestamp}.log"
        
        # Create symlink to latest dead letter log
        self.latest_link = self.log_dir / f"{filename_prefix}_latest.log"
        self._create_symlink()
        
        # Set level to WARNING so we only capture WARNING and above
        self.setLevel(logging.WARNING)
        
        # Use a detailed format for dead letter messages
        formatter = logging.Formatter(
            '%(asctime)s.%(msecs)03d - %(levelname)-8s - %(name)s - %(filename)s:%(lineno)d - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        self.setFormatter(formatter)
        
        # Write header to the file
        with open(self.log_file, 'w') as f:
            f.write(f"=== Dead Letter Queue Log Started at {datetime.now().isoformat()} ===\n")
            f.write("=== This file contains WARNING and ERROR messages that require attention ===\n\n")
    
    def _create_symlink(self) -> None:
        """Create or update the symlink to the latest dead letter log."""
        if self.latest_link.exists():
            self.latest_link.unlink()
        try:
            self.latest_link.symlink_to(self.log_file.name)
        except Exception:
            # Symlinks might not work on all systems
            pass
    
    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a record to the dead letter queue file.
        
        Only WARNING, ERROR, and CRITICAL messages are written.
        """
        try:
            # Only process WARNING and above
            if record.levelno < logging.WARNING:
                return
                
            msg = self.format(record)
            
            # Add extra context for errors
            if record.levelno >= logging.ERROR and record.exc_info:
                import traceback
                msg += "\nException Traceback:\n"
                msg += ''.join(traceback.format_exception(*record.exc_info))
            
            # Write to file with proper encoding
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(msg + '\n')
                
                # Add separator for ERROR and CRITICAL messages
                if record.levelno >= logging.ERROR:
                    f.write('-' * 80 + '\n')
                    
        except Exception:
            # Failsafe - if we can't write to dead letter queue, don't crash
            self.handleError(record)


def add_dead_letter_handler(logger_instance: Optional[logging.Logger] = None,
                          log_dir: str = "logs",
                          filename_prefix: str = "dead_letter") -> DeadLetterQueueHandler:
    """
    Add a dead letter queue handler to the specified logger or root logger.
    
    Args:
        logger_instance: The logger to add the handler to (None for root logger)
        log_dir: Directory for dead letter log files
        filename_prefix: Prefix for dead letter log filenames
        
    Returns:
        The created DeadLetterQueueHandler instance
    """
    handler = DeadLetterQueueHandler(log_dir=log_dir, filename_prefix=filename_prefix)
    
    target_logger = logger_instance or logging.getLogger()
    target_logger.addHandler(handler)
    
    # Log that we've initialized the dead letter queue
    logger = logging.getLogger(__name__)
    logger.info(f"Dead letter queue handler initialized: {handler.log_file}")
    
    return handler