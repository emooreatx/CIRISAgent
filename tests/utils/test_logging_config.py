import logging
from ciris_engine.utils.logging_config import setup_basic_logging


def test_logging_levels_env(monkeypatch, caplog):
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    setup_basic_logging()
    logger = logging.getLogger("dummy_module")
    with caplog.at_level(logging.DEBUG):
        logger.debug("debug")
        logger.info("info")
        logger.warning("warn")
        logger.error("error")

    messages = [rec.getMessage() for rec in caplog.records]
    assert "debug" in messages
    assert "info" in messages
    assert "warn" in messages
    assert "error" in messages
