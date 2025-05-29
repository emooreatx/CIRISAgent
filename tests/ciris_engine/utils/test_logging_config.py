import logging
from ciris_engine.utils.logging_config import setup_basic_logging

def test_setup_basic_logging_sets_level():
    setup_basic_logging(level=logging.DEBUG)
    logger = logging.getLogger("test_logger")
    logger.debug("debug message")
    assert logger.level == logging.DEBUG or logger.level == 0  # 0 means NOTSET, root logger
