import json
import logging
from datetime import datetime, timezone
from typing import List, Optional, Any

from ciris_engine.logic.persistence import get_db_connection
from ciris_engine.schemas.telemetry.core import ServiceCorrelation, ServiceCorrelationStatus, CorrelationType
from ciris_engine.schemas.persistence.core import CorrelationUpdateRequest, MetricsQuery
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol

logger = logging.getLogger(__name__)

def add_correlation(corr: ServiceCorrelation, time_service: TimeServiceProtocol, db_path: Optional[str] = None) -> str:
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
            timestamp_str = str(corr.timestamp)

    params = (
        corr.correlation_id,
        corr.service_type,
        corr.handler_name,
        corr.action_type,
        corr.request_data.model_dump_json() if hasattr(corr.request_data, 'model_dump_json') else json.dumps(corr.request_data) if corr.request_data is not None else None,
        corr.response_data.model_dump_json() if hasattr(corr.response_data, 'model_dump_json') else json.dumps(corr.response_data) if corr.response_data is not None else None,
        corr.status.value,
        corr.created_at.isoformat() if isinstance(corr.created_at, datetime) else str(corr.created_at) if corr.created_at else time_service.now().isoformat(),
        corr.updated_at.isoformat() if isinstance(corr.updated_at, datetime) else str(corr.updated_at) if corr.updated_at else time_service.now().isoformat(),
        corr.correlation_type.value,
        timestamp_str,
        corr.metric_data.metric_name if corr.metric_data else None,
        corr.metric_data.metric_value if corr.metric_data else None,
        corr.log_data.log_level if corr.log_data else None,
        corr.trace_context.trace_id if corr.trace_context else None,
        corr.trace_context.span_id if corr.trace_context else None,
        corr.trace_context.parent_span_id if corr.trace_context else None,
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

def update_correlation(update_request: CorrelationUpdateRequest, time_service: TimeServiceProtocol, db_path: Optional[str] = None) -> bool:
    updates: List[Any] = []
    params: List[Any] = []
    if update_request.response_data is not None:
        updates.append("response_data = ?")
        params.append(json.dumps(update_request.response_data))
    if update_request.status is not None:
        updates.append("status = ?")
        params.append(update_request.status.value)
    if update_request.metric_value is not None:
        updates.append("metric_value = ?")
        params.append(update_request.metric_value)
    if update_request.tags is not None:
        updates.append("tags = ?")
        params.append(json.dumps(update_request.tags))
    updates.append("updated_at = ?")
    params.append(time_service.now().isoformat())
    params.append(update_request.correlation_id)

    sql = f"UPDATE service_correlations SET {', '.join(updates)} WHERE correlation_id = ?"
    try:
        with get_db_connection(db_path=db_path) as conn:
            cursor = conn.execute(sql, params)
            conn.commit()
            return cursor.rowcount > 0
    except Exception as e:
        logger.exception("Failed to update correlation %s: %s", update_request.correlation_id, e)
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
                        # Handle both 'Z' and '+00:00' formats
                        timestamp_str = row["timestamp"]
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        timestamp = None

                # Build the correlation without None values for optional fields
                correlation_data = {
                    "correlation_id": row["correlation_id"],
                    "service_type": row["service_type"],
                    "handler_name": row["handler_name"],
                    "action_type": row["action_type"],
                    "request_data": json.loads(row["request_data"]) if row["request_data"] else None,
                    "response_data": json.loads(row["response_data"]) if row["response_data"] else None,
                    "status": ServiceCorrelationStatus(row["status"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "correlation_type": CorrelationType(row["correlation_type"] or "service_interaction"),
                    "timestamp": timestamp or datetime.now(timezone.utc),
                    "tags": json.loads(row["tags"]) if row["tags"] else {},
                    "retention_policy": row["retention_policy"] or "raw",
                }

                # Only add optional TSDB fields if they have values
                if row["metric_name"] and row["metric_value"] is not None:
                    from ciris_engine.schemas.telemetry.core import MetricData
                    correlation_data["metric_data"] = MetricData(
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        metric_unit="count",
                        metric_type="gauge",
                        labels={}
                    )

                if row["log_level"]:
                    from ciris_engine.schemas.telemetry.core import LogData
                    correlation_data["log_data"] = LogData(
                        log_level=row["log_level"],
                        log_message="",
                        logger_name="",
                        module_name="",
                        function_name="",
                        line_number=0
                    )

                if row["trace_id"]:
                    from ciris_engine.schemas.telemetry.core import TraceContext
                    trace_context = TraceContext(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"] or "",
                        span_name=""
                    )
                    if row["parent_span_id"]:
                        trace_context.parent_span_id = row["parent_span_id"]
                    correlation_data["trace_context"] = trace_context

                return ServiceCorrelation(**correlation_data)
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
                        # Handle both 'Z' and '+00:00' formats
                        timestamp_str = row["timestamp"]
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        timestamp = None

                # Build the correlation without None values for optional fields
                correlation_data = {
                    "correlation_id": row["correlation_id"],
                    "service_type": row["service_type"],
                    "handler_name": row["handler_name"],
                    "action_type": row["action_type"],
                    "request_data": json.loads(row["request_data"]) if row["request_data"] else None,
                    "response_data": json.loads(row["response_data"]) if row["response_data"] else None,
                    "status": ServiceCorrelationStatus(row["status"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "correlation_type": CorrelationType(row["correlation_type"] or "service_interaction"),
                    "timestamp": timestamp or datetime.now(timezone.utc),
                    "tags": json.loads(row["tags"]) if row["tags"] else {},
                    "retention_policy": row["retention_policy"] or "raw",
                }

                # Only add optional TSDB fields if they have values
                if row["metric_name"] and row["metric_value"] is not None:
                    from ciris_engine.schemas.telemetry.core import MetricData
                    correlation_data["metric_data"] = MetricData(
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        metric_unit="count",
                        metric_type="gauge",
                        labels={}
                    )

                if row["log_level"]:
                    from ciris_engine.schemas.telemetry.core import LogData
                    correlation_data["log_data"] = LogData(
                        log_level=row["log_level"],
                        log_message="",
                        logger_name="",
                        module_name="",
                        function_name="",
                        line_number=0
                    )

                if row["trace_id"]:
                    from ciris_engine.schemas.telemetry.core import TraceContext
                    trace_context = TraceContext(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"] or "",
                        span_name=""
                    )
                    if row["parent_span_id"]:
                        trace_context.parent_span_id = row["parent_span_id"]
                    correlation_data["trace_context"] = trace_context

                correlations.append(ServiceCorrelation(**correlation_data))
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
        params: List[Any] = [correlation_type.value]
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
                        # Handle both 'Z' and '+00:00' formats
                        timestamp_str = row["timestamp"]
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        timestamp = None

                # Import required types
                from ciris_engine.schemas.telemetry.core import MetricData, LogData, TraceContext

                # Build metric_data if this is a metric correlation
                metric_data = None
                if row["metric_name"] and row["metric_value"] is not None:
                    metric_data = MetricData(
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        metric_unit="count",
                        metric_type="gauge",
                        labels={}
                    )

                # Build log_data if this is a log correlation
                log_data = None
                if row["log_level"]:
                    log_data = LogData(
                        log_level=row["log_level"],
                        log_message="",  # Not stored in DB
                        logger_name="",
                        module_name="",
                        function_name="",
                        line_number=0
                    )

                # Build trace_context if this is a trace correlation
                trace_context = None
                if row["trace_id"]:
                    trace_context = TraceContext(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"] or "",
                        span_name=""
                    )
                    if row["parent_span_id"]:
                        trace_context.parent_span_id = row["parent_span_id"]

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
                    metric_data=metric_data,
                    log_data=log_data,
                    trace_context=trace_context,
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                ))
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch correlations by type %s: %s", correlation_type, e)
        return []

def get_correlations_by_channel(
    channel_id: str,
    limit: int = 50,
    before: Optional[datetime] = None,
    db_path: Optional[str] = None
) -> List[ServiceCorrelation]:
    """Get correlations for a specific channel (for message history)."""
    sql = """
        SELECT * FROM service_correlations
        WHERE (
            (action_type = 'speak' AND json_extract(request_data, '$.channel_id') = ?) OR
            (action_type = 'observe' AND json_extract(request_data, '$.channel_id') = ?)
        )
    """
    params: List[Any] = [channel_id, channel_id]
    
    if before:
        sql += " AND timestamp < ?"
        before_str = before.isoformat() if hasattr(before, 'isoformat') else str(before)
        params.append(before_str)
    
    sql += " ORDER BY timestamp DESC LIMIT ?"
    params.append(limit)
    
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
                        # Handle both 'Z' and '+00:00' formats
                        timestamp_str = row["timestamp"]
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        timestamp = None
                
                # Build the correlation without None values for optional fields
                correlation_data = {
                    "correlation_id": row["correlation_id"],
                    "service_type": row["service_type"],
                    "handler_name": row["handler_name"],
                    "action_type": row["action_type"],
                    "request_data": json.loads(row["request_data"]) if row["request_data"] else None,
                    "response_data": json.loads(row["response_data"]) if row["response_data"] else None,
                    "status": ServiceCorrelationStatus(row["status"]),
                    "created_at": row["created_at"],
                    "updated_at": row["updated_at"],
                    "correlation_type": CorrelationType(row["correlation_type"] or "service_interaction"),
                    "timestamp": timestamp or datetime.now(timezone.utc),
                    "tags": json.loads(row["tags"]) if row["tags"] else {},
                    "retention_policy": row["retention_policy"] or "raw",
                }
                
                correlations.append(ServiceCorrelation(**correlation_data))
            
            # Reverse to get chronological order (oldest first)
            correlations.reverse()
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch correlations for channel %s: %s", channel_id, e)
        return []

def get_metrics_timeseries(
    query: MetricsQuery,
    db_path: Optional[str] = None
) -> List[ServiceCorrelation]:
    """Get metric correlations as time series data."""
    sql = """
        SELECT * FROM service_correlations
        WHERE correlation_type = 'metric_datapoint'
        AND metric_name = ?
    """
    params: List[Any] = [query.metric_name]

    if query.start_time:
        sql += " AND timestamp >= ?"
        params.append(query.start_time.isoformat() if hasattr(query.start_time, 'isoformat') else query.start_time)

    if query.end_time:
        sql += " AND timestamp <= ?"
        params.append(query.end_time.isoformat() if hasattr(query.end_time, 'isoformat') else query.end_time)

    if query.tags:
        for key, value in query.tags.items():
            sql += " AND json_extract(tags, ?) = ?"
            params.extend([f"$.{key}", value])

    # Default limit to 1000 if not specified
    limit = 1000 if not hasattr(query, 'limit') else getattr(query, 'limit', 1000)
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
                        # Handle both 'Z' and '+00:00' formats
                        timestamp_str = row["timestamp"]
                        if timestamp_str.endswith('Z'):
                            timestamp_str = timestamp_str[:-1] + '+00:00'
                        timestamp = datetime.fromisoformat(timestamp_str)
                    except (ValueError, AttributeError):
                        timestamp = None

                # Import required types
                from ciris_engine.schemas.telemetry.core import MetricData, LogData, TraceContext

                # Build metric_data if this is a metric correlation
                metric_data = None
                if row["metric_name"] and row["metric_value"] is not None:
                    metric_data = MetricData(
                        metric_name=row["metric_name"],
                        metric_value=row["metric_value"],
                        metric_unit="count",
                        metric_type="gauge",
                        labels={}
                    )

                # Build log_data if this is a log correlation
                log_data = None
                if row["log_level"]:
                    log_data = LogData(
                        log_level=row["log_level"],
                        log_message="",  # Not stored in DB
                        logger_name="",
                        module_name="",
                        function_name="",
                        line_number=0
                    )

                # Build trace_context if this is a trace correlation
                trace_context = None
                if row["trace_id"]:
                    trace_context = TraceContext(
                        trace_id=row["trace_id"],
                        span_id=row["span_id"] or "",
                        span_name=""
                    )
                    if row["parent_span_id"]:
                        trace_context.parent_span_id = row["parent_span_id"]

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
                    metric_data=metric_data,
                    log_data=log_data,
                    trace_context=trace_context,
                    tags=json.loads(row["tags"]) if row["tags"] else {},
                    retention_policy=row["retention_policy"] or "raw",
                ))
            return correlations
    except Exception as e:
        logger.exception("Failed to fetch metrics timeseries for %s: %s", query.metric_name, e)
        return []
