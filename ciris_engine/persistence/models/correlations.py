import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any

from ciris_engine.persistence.db import get_db_connection
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus

logger = logging.getLogger(__name__)


def add_correlation(corr: ServiceCorrelation, db_path: Optional[str] = None) -> str:
    sql = """
        INSERT INTO service_correlations (
            correlation_id, service_type, handler_name, action_type,
            request_data, response_data, status, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    params = (
        corr.correlation_id,
        corr.service_type,
        corr.handler_name,
        corr.action_type,
        json.dumps(corr.request_data) if corr.request_data is not None else None,
        json.dumps(corr.response_data) if corr.response_data is not None else None,
        corr.status.value,
        corr.created_at or datetime.utcnow().isoformat(),
        corr.updated_at or datetime.utcnow().isoformat(),
    )
    try:
        with get_db_connection(db_path=db_path) as conn:
            conn.execute(sql, params)
            conn.commit()
        logger.debug("Inserted correlation %s", corr.correlation_id)
        return corr.correlation_id
    except Exception as e:
        logger.exception("Failed to add correlation %s: %s", corr.correlation_id, e)
        raise


def update_correlation(correlation_id: str, *, response_data: Optional[Dict[str, Any]] = None,
                        status: Optional[ServiceCorrelationStatus] = None,
                        db_path: Optional[str] = None) -> bool:
    updates = []
    params: list[Any] = []
    if response_data is not None:
        updates.append("response_data = ?")
        params.append(json.dumps(response_data))
    if status is not None:
        updates.append("status = ?")
        params.append(status.value)
    updates.append("updated_at = ?")
    params.append(datetime.utcnow().isoformat())
    params.append(correlation_id)

    sql = f"UPDATE service_correlations SET {', '.join(updates)} WHERE correlation_id = ?"
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Failed to update correlation %s: %s", correlation_id, e)
        return False


def get_correlation(correlation_id: str, db_path: Optional[str] = None) -> Optional[ServiceCorrelation]:
    sql = "SELECT * FROM service_correlations WHERE correlation_id = ?"
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (correlation_id,))
            row = cursor.fetchone()
            if row:
                return ServiceCorrelation(
                    correlation_id=row["correlation_id"],
                    service_type=row["service_type"],
                    handler_name=row["handler_name"],
                    action_type=row["action_type"],
                    request_data=json.loads(row["request_data"]) if row["request_data"] else None,
                    response_data=json.loads(row["response_data"]) if row["response_data"] else None,
                    status=ServiceCorrelationStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                )
            return None
    except Exception as e:
        logger.exception("Failed to fetch correlation %s: %s", correlation_id, e)
        return None

