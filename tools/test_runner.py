#!/usr/bin/env python3
"""
Background Test Runner for CIRIS

Manages pytest runs in Docker containers with consistent output handling.
Runs tests in background, saves output, and provides status checking.

Usage:
    python tools/test_runner.py start [--coverage] [--filter PATTERN]
    python tools/test_runner.py status
    python tools/test_runner.py logs [--tail N]
    python tools/test_runner.py stop
    python tools/test_runner.py results
"""

import os
import sys
import json
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

# Configuration
TEST_OUTPUT_DIR = Path.home() / ".ciris_test_runs"
CONTAINER_NAME = "ciris-pytest"
STATUS_FILE = TEST_OUTPUT_DIR / "current_run.json"

class TestRunner:
    """Manages background test execution in Docker containers."""
    
    def __init__(self):
        TEST_OUTPUT_DIR.mkdir(exist_ok=True)
    
    def start(self, coverage: bool = False, filter_pattern: Optional[str] = None, 
              compose_file: str = "docker/docker-compose-pytest.yml") -> str:
        """Start a new test run in the background."""
        # Check if already running
        if self.is_running():
            print("⚠️  Tests already running. Use 'status' to check or 'stop' to cancel.")
            return ""
        
        # Generate run ID
        run_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_file = TEST_OUTPUT_DIR / f"test_run_{run_id}.log"
        
        # Build pytest command
        pytest_cmd = "pytest -xvs --tb=short"
        if coverage:
            pytest_cmd += " --cov=ciris_engine --cov-report=term-missing --cov-report=html"
        if filter_pattern:
            pytest_cmd += f" -k '{filter_pattern}'"
        
        # Docker command
        cmd = [
            "docker", "compose", "-f", compose_file, "run",
            "--rm", "--name", CONTAINER_NAME,
            "-T",  # Disable TTY for background execution
            "pytest",
            "/bin/bash", "-c", pytest_cmd
        ]
        
        # Start process in background
        with open(output_file, 'w') as outfile:
            process = subprocess.Popen(
                cmd,
                stdout=outfile,
                stderr=subprocess.STDOUT,
                cwd=Path.cwd()
            )
        
        # Save status
        status = {
            "run_id": run_id,
            "pid": process.pid,
            "start_time": datetime.now().isoformat(),
            "output_file": str(output_file),
            "coverage": coverage,
            "filter": filter_pattern,
            "command": " ".join(cmd)
        }
        
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
        
        print(f"✅ Test run started: {run_id}")
        print(f"   Output: {output_file}")
        print(f"   Command: {pytest_cmd}")
        print(f"\nUse 'python tools/test_runner.py status' to check progress")
        
        return run_id
    
    def is_running(self) -> bool:
        """Check if tests are currently running."""
        if not STATUS_FILE.exists():
            return False
        
        try:
            with open(STATUS_FILE) as f:
                status = json.load(f)
            
            # Check if process is still running
            pid = status['pid']
            try:
                os.kill(pid, 0)  # Check if process exists
                return True
            except ProcessLookupError:
                return False
        except:
            return False
    
    def status(self) -> Dict[str, Any]:
        """Get current test run status."""
        if not STATUS_FILE.exists():
            print("❌ No test run found")
            return {}
        
        with open(STATUS_FILE) as f:
            status = json.load(f)
        
        # Check if still running
        running = self.is_running()
        status['running'] = running
        
        # Get output stats
        output_file = Path(status['output_file'])
        if output_file.exists():
            lines = output_file.read_text().splitlines()
            status['output_lines'] = len(lines)
            
            # Check for test counts
            passed = sum(1 for line in lines if " PASSED" in line)
            failed = sum(1 for line in lines if " FAILED" in line)
            status['passed'] = passed
            status['failed'] = failed
            
            # Get last few lines
            status['last_lines'] = lines[-10:] if lines else []
        
        return status
    
    def show_status(self):
        """Display formatted status."""
        status = self.status()
        if not status:
            return
        
        print(f"Test Run: {status['run_id']}")
        print(f"Started: {status['start_time']}")
        print(f"Status: {'🟢 Running' if status['running'] else '🔴 Completed'}")
        
        if 'passed' in status:
            print(f"\nTests: {status['passed']} passed, {status['failed']} failed")
            print(f"Output lines: {status['output_lines']}")
        
        if status.get('last_lines'):
            print("\nLast 10 lines:")
            print("-" * 70)
            for line in status['last_lines']:
                print(line)
    
    def logs(self, tail: int = 50):
        """Show test output logs."""
        status = self.status()
        if not status:
            return
        
        output_file = Path(status['output_file'])
        if not output_file.exists():
            print("❌ Output file not found")
            return
        
        if tail:
            # Use tail command for efficiency
            subprocess.run(['tail', '-n', str(tail), str(output_file)])
        else:
            # Cat the entire file
            subprocess.run(['cat', str(output_file)])
    
    def stop(self):
        """Stop the current test run."""
        if not self.is_running():
            print("❌ No tests running")
            return
        
        status = self.status()
        
        # Try to stop via docker first
        subprocess.run(['docker', 'stop', CONTAINER_NAME], capture_output=True)
        
        # Then kill the process
        try:
            os.kill(status['pid'], 15)  # SIGTERM
            print(f"✅ Test run {status['run_id']} stopped")
        except:
            print("⚠️  Process already terminated")
    
    def results(self):
        """Show test results summary."""
        status = self.status()
        if not status:
            return
        
        output_file = Path(status['output_file'])
        if not output_file.exists():
            print("❌ Output file not found")
            return
        
        content = output_file.read_text()
        
        # Extract pytest summary
        summary_start = content.rfind("=")
        if summary_start > 0:
            summary = content[summary_start:]
            print("\nTest Summary:")
            print(summary)
        
        # Extract coverage if present
        if status.get('coverage'):
            cov_start = content.find("---------- coverage:")
            if cov_start > 0:
                cov_end = content.find("\n\n", cov_start)
                if cov_end > 0:
                    print("\nCoverage Report:")
                    print(content[cov_start:cov_end])

def main():
    parser = argparse.ArgumentParser(description="CIRIS Background Test Runner")
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    # Start command
    start_parser = subparsers.add_parser("start", help="Start a new test run")
    start_parser.add_argument("--coverage", action="store_true", help="Run with coverage")
    start_parser.add_argument("--filter", help="Pytest -k filter pattern")
    start_parser.add_argument("--compose-file", default="docker/docker-compose-pytest.yml",
                            help="Docker compose file to use")
    
    # Status command
    status_parser = subparsers.add_parser("status", help="Check test run status")
    
    # Logs command
    logs_parser = subparsers.add_parser("logs", help="Show test output")
    logs_parser.add_argument("--tail", type=int, default=50, 
                           help="Number of lines to show (0 for all)")
    
    # Stop command
    stop_parser = subparsers.add_parser("stop", help="Stop current test run")
    
    # Results command
    results_parser = subparsers.add_parser("results", help="Show test results summary")
    
    args = parser.parse_args()
    runner = TestRunner()
    
    if args.command == "start":
        runner.start(coverage=args.coverage, filter_pattern=args.filter, 
                    compose_file=args.compose_file)
    elif args.command == "status":
        runner.show_status()
    elif args.command == "logs":
        runner.logs(tail=args.tail)
    elif args.command == "stop":
        runner.stop()
    elif args.command == "results":
        runner.results()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()