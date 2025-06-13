import os
import tempfile
from ciris_engine.persistence import (
    initialize_database,
    get_db_connection,
    run_migrations,
    MIGRATIONS_DIR,
)


def temp_db_file():
    f = tempfile.NamedTemporaryFile(delete=False)
    f.close()
    return f.name


def test_initialize_runs_migrations():
    db_path = temp_db_file()
    try:
        initialize_database(db_path=db_path)
        with get_db_connection(db_path) as conn:
            # migrations table exists
            cur = conn.execute(
                "SELECT filename FROM schema_migrations ORDER BY filename"
            )
            rows = [r[0] for r in cur.fetchall()]
            assert rows == ["002_add_retry_status.sql"]
            # column from second migration present
            cur = conn.execute("PRAGMA table_info(tasks)")
            cols = [r[1] for r in cur.fetchall()]
            assert "retry_count" in cols
    finally:
        os.unlink(db_path)


def test_failed_migration_rolls_back(tmp_path):
    migrations_dir = tmp_path / "migs"
    migrations_dir.mkdir()
    (migrations_dir / "001_ok.sql").write_text(
        "CREATE TABLE test (id INTEGER PRIMARY KEY);"
    )
    (migrations_dir / "002_fail.sql").write_text("INVALID SQL;")
    db_path = temp_db_file()
    try:
        with get_db_connection(db_path) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS schema_migrations (filename TEXT PRIMARY KEY, applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
            )
            conn.commit()
        original_dir = MIGRATIONS_DIR
        # patch migrations dir
        import ciris_engine.persistence.db.migration_runner as mr
        try:
            mr.MIGRATIONS_DIR = migrations_dir
            try:
                run_migrations(db_path=db_path)
            except Exception:
                pass
        finally:
            mr.MIGRATIONS_DIR = original_dir
        with get_db_connection(db_path) as conn:
            cur = conn.execute("SELECT filename FROM schema_migrations")
            rows = [r[0] for r in cur.fetchall()]
            assert rows == ["001_ok.sql"]
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='test'"
            )
            assert cur.fetchone() is not None
    finally:
        os.unlink(db_path)
