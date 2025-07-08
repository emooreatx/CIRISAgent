"""
Incident Capture Handler for capturing WARNING and ERROR level log messages as incidents.
"""
import logging
import asyncio
import traceback
import uuid
from pathlib import Path
from typing import Optional
from ciris_engine.protocols.services import TimeServiceProtocol
from ciris_engine.schemas.services.graph.incident import IncidentNode, IncidentSeverity, IncidentStatus

class IncidentCaptureHandler(logging.Handler):
    """
    A logging handler that captures WARNING and ERROR level messages as incidents.
    These incidents are stored in the graph for analysis, pattern detection, and self-improvement.
    """

    def __init__(self, log_dir: str = "logs", filename_prefix: str = "incidents", time_service: TimeServiceProtocol = None, graph_audit_service=None):
        super().__init__()
        if not time_service:
            raise RuntimeError("CRITICAL: TimeService is required for IncidentCaptureHandler")
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        self._time_service = time_service

        self._graph_audit_service = graph_audit_service

        # Create incident log file with timestamp
        timestamp = self._time_service.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = self.log_dir / f"{filename_prefix}_{timestamp}.log"

        # Create symlink to latest dead letter log
        self.latest_link = self.log_dir / f"{filename_prefix}_latest.log"
        self._create_symlink()
        
        # Store the actual incident log filename for the telemetry endpoint
        actual_incident_path = self.log_dir / ".current_incident_log"
        try:
            with open(actual_incident_path, 'w') as f:
                f.write(str(self.log_file.absolute()))
        except Exception:
            pass

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
            f.write(f"=== Incident Log Started at {self._time_service.now_iso()} ===\n")
            f.write("=== This file contains WARNING and ERROR messages captured as incidents ===\n\n")

    def _create_symlink(self) -> None:
        """Create or update the symlink to the latest incident log."""
        if self.latest_link.exists():
            self.latest_link.unlink()
        try:
            self.latest_link.symlink_to(self.log_file.name)
        except Exception:
            # Symlinks might not work on all systems
            pass

    def emit(self, record: logging.LogRecord) -> None:
        """
        Emit a record as an incident to both file and graph.

        Only WARNING, ERROR, and CRITICAL messages are captured as incidents.
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

            # Also save to graph as incident if audit service available
            if self._graph_audit_service:
                # Create async task to save to graph (non-blocking)
                asyncio.create_task(self._save_incident_to_graph(record))

        except Exception:
            # Failsafe - if we can't capture incident, don't crash
            self.handleError(record)

    async def _save_incident_to_graph(self, record: logging.LogRecord) -> None:
        """Save log record as incident in graph."""
        try:
            # Map log level to incident severity
            severity = self._map_log_level_to_severity(record.levelno)

            # Extract correlation data from extra fields if available
            correlation_id = getattr(record, 'correlation_id', None)
            task_id = getattr(record, 'task_id', None)
            thought_id = getattr(record, 'thought_id', None)
            handler_name = getattr(record, 'handler_name', None)

            # Create incident node
            incident = IncidentNode(
                id=f"incident_{uuid.uuid4()}",
                incident_type=record.levelname,
                severity=severity,
                status=IncidentStatus.OPEN,
                description=record.getMessage(),
                source_component=record.name,
                detected_at=self._time_service.now(),

                # Correlation data
                correlation_id=correlation_id,
                task_id=task_id,
                thought_id=thought_id,
                handler_name=handler_name,

                # Technical details
                filename=record.filename,
                line_number=record.lineno,
                function_name=record.funcName,

                # Exception data if present
                exception_type=record.exc_info[0].__name__ if record.exc_info else None,
                stack_trace=''.join(traceback.format_exception(*record.exc_info)) if record.exc_info else None,

                # Impact assessment (to be enhanced by analysis)
                impact="TBD",
                urgency=self._calculate_urgency(severity)
            )

            # Store in graph via audit service
            await self._graph_audit_service.log_event(incident)

        except Exception as e:
            # Log error but don't crash - incident capture should never break the system
            logging.getLogger(__name__).error(f"Failed to save incident to graph: {e}")

    def _map_log_level_to_severity(self, levelno: int) -> IncidentSeverity:
        """Map Python log level to incident severity."""
        if levelno >= logging.CRITICAL:
            return IncidentSeverity.CRITICAL
        elif levelno >= logging.ERROR:
            return IncidentSeverity.HIGH
        elif levelno >= logging.WARNING:
            return IncidentSeverity.MEDIUM
        else:
            return IncidentSeverity.LOW

    def _calculate_urgency(self, severity: IncidentSeverity) -> str:
        """Calculate urgency based on severity."""
        urgency_map = {
            IncidentSeverity.CRITICAL: "IMMEDIATE",
            IncidentSeverity.HIGH: "HIGH",
            IncidentSeverity.MEDIUM: "MEDIUM",
            IncidentSeverity.LOW: "LOW"
        }
        return urgency_map.get(severity, "MEDIUM")

def add_incident_capture_handler(logger_instance: Optional[logging.Logger] = None,
                               log_dir: str = "logs",
                               filename_prefix: str = "incidents",
                               time_service: TimeServiceProtocol = None,
                               graph_audit_service=None) -> IncidentCaptureHandler:
    """
    Add an incident capture handler to the specified logger or root logger.

    Args:
        logger_instance: The logger to add the handler to (None for root logger)
        log_dir: Directory for incident log files
        filename_prefix: Prefix for incident log filenames
        time_service: Time service for timestamps
        graph_audit_service: Audit service for storing incidents in graph

    Returns:
        The created IncidentCaptureHandler instance
    """
    if not time_service:
        raise RuntimeError("CRITICAL: TimeService is required for add_incident_capture_handler")
    handler = IncidentCaptureHandler(log_dir=log_dir, filename_prefix=filename_prefix, time_service=time_service, graph_audit_service=graph_audit_service)

    target_logger = logger_instance or logging.getLogger()
    target_logger.addHandler(handler)

    # Log that we've initialized the incident capture
    logger = logging.getLogger(__name__)
    logger.info(f"Incident capture handler initialized: {handler.log_file}")

    return handler
