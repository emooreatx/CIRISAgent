#!/usr/bin/env python3
"""Test parsing incidents from log file."""

from datetime import datetime, timedelta, timezone
from pathlib import Path

def parse_incidents_log():
    """Parse incidents from the log file."""
    log_file = Path("logs/incidents_latest.log")
    
    if not log_file.exists():
        print(f"No incidents log file found at {log_file}")
        return []
    
    incidents = []
    with open(log_file, 'r') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("==="):
                continue
            
            # Parse log line: "2025-07-09 15:24:43.200 - WARNING  - component - file.py:line - message"
            parts = line.split(" - ", 4)
            if len(parts) >= 5:
                timestamp_str = parts[0]
                level = parts[1].strip()
                component = parts[2].strip()
                location = parts[3].strip()
                message = parts[4].strip()
                
                incidents.append({
                    'timestamp': timestamp_str,
                    'level': level,
                    'component': component,
                    'location': location,
                    'message': message
                })
    
    return incidents

if __name__ == "__main__":
    incidents = parse_incidents_log()
    print(f"Found {len(incidents)} incidents in log file")
    
    # Show last 5 incidents
    for incident in incidents[-5:]:
        print(f"\n{incident['timestamp']} - {incident['level']}")
        print(f"  Component: {incident['component']}")
        print(f"  Message: {incident['message'][:100]}...")