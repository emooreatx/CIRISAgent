"""
Database path utilities for the new config system.

Provides compatibility functions for getting database paths.
"""

from pathlib import Path
from typing import Optional

from ciris_engine.schemas.config.essential import EssentialConfig


def get_sqlite_db_full_path(config: Optional[EssentialConfig] = None) -> str:
    """
    Get the full path to the main SQLite database.

    Args:
        config: Optional EssentialConfig instance. If not provided, uses defaults.

    Returns:
        Full path to the SQLite database file
    """
    if config is None:
        config = EssentialConfig()

    db_path = Path(config.database.main_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path.resolve())


def get_secrets_db_full_path(config: Optional[EssentialConfig] = None) -> str:
    """
    Get the full path to the secrets database.

    Args:
        config: Optional EssentialConfig instance. If not provided, uses defaults.

    Returns:
        Full path to the secrets database file
    """
    if config is None:
        config = EssentialConfig()

    db_path = Path(config.database.secrets_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path.resolve())


def get_audit_db_full_path(config: Optional[EssentialConfig] = None) -> str:
    """
    Get the full path to the audit database.

    Args:
        config: Optional EssentialConfig instance. If not provided, uses defaults.

    Returns:
        Full path to the audit database file
    """
    if config is None:
        config = EssentialConfig()

    db_path = Path(config.database.audit_db)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path.resolve())


# For backward compatibility - uses defaults
def get_graph_memory_full_path() -> str:
    """Legacy function - graph memory is now in the main database."""
    return get_sqlite_db_full_path()
