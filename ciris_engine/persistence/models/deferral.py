import json
from typing import Optional, Dict, Any
from ciris_engine.persistence import get_db_connection
import logging

logger = logging.getLogger(__name__)

def save_deferral_report_mapping(message_id: str, task_id: str, thought_id: str, package: Optional[Dict[str, Any]] = None, db_path: Optional[str] = None) -> None:
    sql = """
        INSERT OR REPLACE INTO deferral_reports (message_id, task_id, thought_id, package_json)
        VALUES (?, ?, ?, ?)
    """
    package_json = json.dumps(package) if package is not None else None
    try:
        with get_db_connection(db_path=db_path) as conn:
            conn.execute(sql, (message_id, task_id, thought_id, package_json))
            conn.commit()
        logger.debug(
            "Saved deferral report mapping: %s -> task %s, thought %s",
            message_id,
            task_id,
            thought_id,
        )
    except Exception as e:
        logger.exception(
            "Failed to save deferral report mapping for message %s: %s",
            message_id,
            e,
        )

def get_deferral_report_context(message_id: str, db_path: Optional[str] = None) -> Optional[tuple[str, str, Optional[Dict[str, Any]]]]:
    sql = "SELECT task_id, thought_id, package_json FROM deferral_reports WHERE message_id = ?"
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (message_id,))
            row = cursor.fetchone()
            if row:
                pkg = None
                if row["package_json"]:
                    try:
                        pkg = json.loads(row["package_json"])
                    except Exception:
                        pkg = None
                return row["task_id"], row["thought_id"], pkg
            return None
    except Exception as e:
        logger.exception(
            "Failed to fetch deferral report context for message %s: %s",
            message_id,
            e,
        )
        return None
