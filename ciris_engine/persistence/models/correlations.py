import json
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from ciris_engine.persistence import get_db_connection
from ciris_engine.schemas.correlation_schemas_v1 import ServiceCorrelation, ServiceCorrelationStatus, CorrelationType

logger = logging.getLogger(__name__)


def add_correlation(corr: ServiceCorrelation, db_path: Optional[str] = None) -> str:
    sql = """
        INSERT INTO service_correlations (
            correlation_id, service_type, handler_name, action_type,
            request_data, response_data, status, created_at, updated_at,
            correlation_type, timestamp, metric_name, metric_value, log_level,
            trace_id, span_id, parent_span_id, tags, retention_policy
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    # Convert timestamp to ISO string if it's a datetime object
    timestamp_str = None
    if corr.timestamp:
        if isinstance(corr.timestamp, datetime):
            timestamp_str = corr.timestamp.isoformat()
        else:
            timestamp_str = str(corr.timestamp)  # type: ignore[unreachable]
    
    params = (
        corr.correlation_id,
        corr.service_type,
        corr.handler_name,
        corr.action_type,
        json.dumps(corr.request_data) if corr.request_data is not None else None,
        json.dumps(corr.response_data) if corr.response_data is not None else None,
        corr.status.value,
        corr.created_at or datetime.now(timezone.utc).isoformat(),
        corr.updated_at or datetime.now(timezone.utc).isoformat(),
        corr.correlation_type.value,
        timestamp_str,
        corr.metric_name,
        corr.metric_value,
        corr.log_level,
        corr.trace_id,
        corr.span_id,
        corr.parent_span_id,
        json.dumps(corr.tags) if corr.tags else None,
        corr.retention_policy,
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
    updates: List[Any] = []
    params: list[Any] = []
    if response_data is not None:
        updates.append("response_data = ?")
        params.append(json.dumps(response_data))
    if status is not None:
        updates.append("status = ?")
        params.append(status.value)
    updates.append("updated_at = ?")
    params.append(datetime.now(timezone.utc).isoformat())
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
                # Parse timestamp if present
                timestamp = None
                if row["timestamp"]:
                    try:
                        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = None
                
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
                    # New TSDB fields
                    correlation_type=CorrelationType(row["correlation_type"] or "service_interaction"),
                    timestamp=timestamp,
                    metric_name=row["metric_name"],
                    metric_value=row["metric_value"],
                    log_level=row["log_level"],
                    trace_id=row["trace_id"],
                    span_id=row["span_id"],
                    parent_span_id=row["parent_span_id"],
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                )
            return None
    except Exception as e:
        logger.exception("Failed to fetch correlation %s: %s", correlation_id, e)
        return None


def get_correlations_by_task_and_action(task_id: str, action_type: str, status: Optional[ServiceCorrelationStatus] = None, db_path: Optional[str] = None) -> List[ServiceCorrelation]:
    """Get correlations for a specific task and action type."""
    sql = """
        SELECT * FROM service_correlations 
        WHERE action_type = ?
        AND json_extract(request_data, '$.task_id') = ?
    """
    params = [action_type, task_id]
    
    if status is not None:
        sql += " AND status = ?"
        params.append(status.value)
    
    sql += " ORDER BY created_at DESC"
    
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            correlations = []
            for row in rows:
                # Parse timestamp if present
                timestamp = None
                if row["timestamp"]:
                    try:
                        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = None
                
                correlations.append(ServiceCorrelation(
                    correlation_id=row["correlation_id"],
                    service_type=row["service_type"],
                    handler_name=row["handler_name"],
                    action_type=row["action_type"],
                    request_data=json.loads(row["request_data"]) if row["request_data"] else None,
                    response_data=json.loads(row["response_data"]) if row["response_data"] else None,
                    status=ServiceCorrelationStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    # New TSDB fields
                    correlation_type=CorrelationType(row["correlation_type"] or "service_interaction"),
                    timestamp=timestamp,
                    metric_name=row["metric_name"],
                    metric_value=row["metric_value"],
                    log_level=row["log_level"],
                    trace_id=row["trace_id"],
                    span_id=row["span_id"],
                    parent_span_id=row["parent_span_id"],
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                ))
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch correlations for task %s and action %s: %s", task_id, action_type, e)
        return []


def get_correlations_by_type_and_time(
    correlation_type: CorrelationType,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    metric_names: Optional[List[str]] = None,
    log_levels: Optional[List[str]] = None,
    limit: int = 1000,
    db_path: Optional[str] = None
) -> List[ServiceCorrelation]:
    """Get correlations by type with optional time filtering for TSDB queries."""
    sql = "SELECT * FROM service_correlations WHERE correlation_type = ?"
    if hasattr(correlation_type, 'value'):
        params = [correlation_type.value]
    else:
        params = [str(correlation_type)]
    
    if start_time:
        sql += " AND timestamp >= ?"
        params.append(start_time)
    
    if end_time:
        sql += " AND timestamp <= ?"
        params.append(end_time)
    
    if metric_names:
        placeholders = ",".join("?" * len(metric_names))
        sql += f" AND metric_name IN ({placeholders})"
        params.extend(metric_names)
    
    if log_levels:
        placeholders = ",".join("?" * len(log_levels))
        sql += f" AND log_level IN ({placeholders})"
        params.extend(log_levels)
    
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            correlations = []
            for row in rows:
                timestamp = None
                if row["timestamp"]:
                    try:
                        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = None
                
                correlations.append(ServiceCorrelation(
                    correlation_id=row["correlation_id"],
                    service_type=row["service_type"],
                    handler_name=row["handler_name"],
                    action_type=row["action_type"],
                    request_data=json.loads(row["request_data"]) if row["request_data"] else None,
                    response_data=json.loads(row["response_data"]) if row["response_data"] else None,
                    status=ServiceCorrelationStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    correlation_type=CorrelationType(row["correlation_type"] or "service_interaction"),
                    timestamp=timestamp,
                    metric_name=row["metric_name"],
                    metric_value=row["metric_value"],
                    log_level=row["log_level"],
                    trace_id=row["trace_id"],
                    span_id=row["span_id"],
                    parent_span_id=row["parent_span_id"],
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                ))
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch correlations by type %s: %s", correlation_type, e)
        return []


def get_metrics_timeseries(
    metric_name: str,
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    tags: Optional[Dict[str, str]] = None,
    limit: int = 1000,
    db_path: Optional[str] = None
) -> List[ServiceCorrelation]:
    """Get metric correlations as time series data."""
    sql = """
        SELECT * FROM service_correlations 
        WHERE correlation_type = 'metric_datapoint' 
        AND metric_name = ?
    """
    params = [metric_name]
    
    if start_time:
        sql += " AND timestamp >= ?"
        params.append(start_time)
    
    if end_time:
        sql += " AND timestamp <= ?"
        params.append(end_time)
    
    if tags:
        for key, value in tags.items():
            sql += " AND json_extract(tags, ?) = ?"
            params.extend([f"$.{key}", value])
    
    sql += " ORDER BY timestamp ASC LIMIT ?"
    params.append(limit)
    
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(sql, params)
            rows = cursor.fetchall()
            
            correlations = []
            for row in rows:
                timestamp = None
                if row["timestamp"]:
                    try:
                        timestamp = datetime.fromisoformat(row["timestamp"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        timestamp = None
                
                correlations.append(ServiceCorrelation(
                    correlation_id=row["correlation_id"],
                    service_type=row["service_type"],
                    handler_name=row["handler_name"],
                    action_type=row["action_type"],
                    request_data=json.loads(row["request_data"]) if row["request_data"] else None,
                    response_data=json.loads(row["response_data"]) if row["response_data"] else None,
                    status=ServiceCorrelationStatus(row["status"]),
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    correlation_type=CorrelationType(row["correlation_type"] or "service_interaction"),
                    timestamp=timestamp,
                    metric_name=row["metric_name"],
                    metric_value=row["metric_value"],
                    log_level=row["log_level"],
                    trace_id=row["trace_id"],
                    span_id=row["span_id"],
                    parent_span_id=row["parent_span_id"],
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                ))
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch metrics timeseries for %s: %s", metric_name, e)
        return []

