"""
Log file reader for telemetry endpoint.
Reads actual log files from disk instead of audit entries.
"""
import os
import re
from datetime import datetime
from typing import List, Optional
import json
from pathlib import Path

from ciris_engine.schemas.api.telemetry import LogContext

# Import LogEntry from the route file where it's defined
try:
    from .telemetry import LogEntry
except ImportError:
    # Define locally if import fails
    from pydantic import BaseModel, Field
    from datetime import datetime
    from typing import Optional
    
    class LogEntry(BaseModel):
        """Telemetry log entry."""
        timestamp: datetime = Field(..., description="Log timestamp")
        level: str = Field(..., description="Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)")
        service: str = Field(..., description="Service that generated log")
        message: str = Field(..., description="Log message")
        context: Optional[LogContext] = Field(None, description="Structured context")
        trace_id: Optional[str] = Field(None, description="Trace ID for correlation")


class LogFileReader:
    """Reads and parses log files from disk."""
    
    LOG_PATTERN = re.compile(
        r'^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}) - ([^-]+) - (\w+) - (.*)$'
    )
    
    def __init__(self, logs_dir: str = "/app/logs"):
        self.logs_dir = Path(logs_dir)
        
    def read_logs(
        self,
        level: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        include_incidents: bool = True
    ) -> List[LogEntry]:
        """Read logs from files and return as LogEntry objects."""
        logs = []
        
        # Read from latest.log
        latest_log = self.logs_dir / "latest.log"
        if latest_log.exists():
            logs.extend(self._parse_log_file(latest_log, level, service, limit, start_time, end_time))
        
        # Read from incidents_latest.log if requested
        if include_incidents and len(logs) < limit:
            incidents_log = self.logs_dir / "incidents_latest.log"
            if incidents_log.exists():
                logs.extend(self._parse_log_file(incidents_log, level, service, limit - len(logs), start_time, end_time))
        
        # Sort by timestamp ascending (oldest first, newest last)
        logs.sort(key=lambda x: x.timestamp, reverse=False)
        
        # Return the most recent logs (last N entries)
        return logs[-limit:] if len(logs) > limit else logs
    
    def _parse_log_file(
        self,
        file_path: Path,
        level: Optional[str] = None,
        service: Optional[str] = None,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[LogEntry]:
        """Parse a single log file."""
        logs = []
        
        try:
            # Read file from end (most recent logs)
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                # Read more lines than needed to account for filtering
                # but cap it to avoid reading huge files
                read_lines = min(limit * 20, 10000)
                lines = self._tail(f, read_lines)
                
                # Process lines in order (they're already in chronological order from tail)
                for line in lines:
                    entry = self._parse_log_line(line)
                    if entry:
                        # Apply filters
                        if level and entry.level != level.upper():
                            continue
                        if service and service.lower() not in entry.service.lower():
                            continue
                        if start_time and entry.timestamp < start_time:
                            continue
                        if end_time and entry.timestamp > end_time:
                            continue
                            
                        logs.append(entry)
                            
        except Exception as e:
            # Log parsing error, but don't fail the endpoint
            print(f"Error reading log file {file_path}: {e}")
            
        return logs
    
    def _tail(self, file_obj, num_lines: int) -> List[str]:
        """Read last N lines from a file efficiently."""
        # For large files, seek to end and read backwards
        file_obj.seek(0, 2)  # Go to end of file
        file_size = file_obj.tell()
        
        if file_size == 0:
            return []
        
        # Read chunk size (adjust based on expected line length)
        chunk_size = min(file_size, 8192)
        lines = []
        position = file_size
        
        while len(lines) < num_lines + 1 and position > 0:
            # Calculate how much to read
            read_size = min(chunk_size, position)
            position -= read_size
            
            # Seek to position and read
            file_obj.seek(position)
            chunk = file_obj.read(read_size)
            
            # Split into lines
            chunk_lines = chunk.split('\n')
            
            # Combine with existing lines
            if lines:
                # Last line from previous chunk might be incomplete
                chunk_lines[-1] += lines[0]
                lines = chunk_lines + lines[1:]
            else:
                lines = chunk_lines
        
        # Remove empty lines and return last N non-empty lines
        lines = [line for line in lines if line.strip()]
        return lines[-num_lines:]
    
    def _parse_log_line(self, line: str) -> Optional[LogEntry]:
        """Parse a single log line into a LogEntry."""
        line = line.strip()
        if not line:
            return None
            
        match = self.LOG_PATTERN.match(line)
        if not match:
            return None
            
        timestamp_str, module, level, message = match.groups()
        
        try:
            # Parse timestamp
            timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S.%f")
            
            # Extract service name from module
            service = module.strip().split('.')[0]
            
            # Try to extract JSON context from message
            context_data = {}
            if '{' in message and '}' in message:
                try:
                    # Find JSON in message
                    json_start = message.find('{')
                    json_end = message.rfind('}') + 1
                    json_str = message[json_start:json_end]
                    context_data = json.loads(json_str)
                    # Remove JSON from message
                    message = message[:json_start].strip() + message[json_end:].strip()
                except:
                    pass
            
            # Build log entry
            return LogEntry(
                timestamp=timestamp,
                level=level.upper(),
                service=service,
                message=message.strip(),
                context=LogContext(
                    trace_id=context_data.get('trace_id'),
                    correlation_id=context_data.get('correlation_id'),
                    user_id=context_data.get('user_id'),
                    entity_id=context_data.get('entity_id'),
                    error_details=context_data.get('error_details') if level.upper() in ['ERROR', 'CRITICAL'] else None,
                    metadata=context_data
                ),
                trace_id=context_data.get('trace_id') or context_data.get('correlation_id')
            )
        except Exception:
            # If parsing fails, return None
            return None


# Global instance
log_reader = LogFileReader()