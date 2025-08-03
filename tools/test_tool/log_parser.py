"""Parse and analyze pytest output logs."""

import re
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass


@dataclass
class TestResult:
    """Represents a single test result."""
    test_name: str
    status: str  # PASSED, FAILED, ERROR, SKIPPED
    duration: Optional[float] = None
    
    
@dataclass 
class TestError:
    """Represents a test error with context."""
    test_name: str
    error_type: str
    error_message: str
    traceback: List[str]
    captured_output: Optional[str] = None


class LogParser:
    """Parse pytest output logs."""
    
    # Regex patterns
    TEST_RESULT_PATTERN = re.compile(
        r'^(tests/[^\s]+)\s+(PASSED|FAILED|ERROR|SKIPPED)'
    )
    ERROR_HEADER_PATTERN = re.compile(
        r'^_{5,}\s+(ERROR|FAILED|FAILURE)\s+.+\s+_{5,}$'
    )
    TEST_STATS_PATTERN = re.compile(
        r'^=+\s*(\d+)\s+passed(?:,\s*(\d+)\s+skipped)?(?:,\s*(\d+)\s+warnings)?(?:,\s*(\d+)\s+error)?(?:,\s*(\d+)\s+failed)?'
    )
    COVERAGE_PATTERN = re.compile(
        r'^TOTAL\s+\d+\s+\d+\s+([\d.]+)%'
    )
    
    def __init__(self, log_file: Path):
        self.log_file = log_file
        self._lines = []
        self._load_file()
    
    def _load_file(self):
        """Load log file lines."""
        if self.log_file.exists():
            with open(self.log_file, 'r') as f:
                self._lines = f.readlines()
    
    def parse_test_results(self) -> List[TestResult]:
        """Parse individual test results."""
        results = []
        for line in self._lines:
            match = self.TEST_RESULT_PATTERN.match(line.strip())
            if match:
                results.append(TestResult(
                    test_name=match.group(1),
                    status=match.group(2)
                ))
        return results
    
    def parse_test_stats(self) -> Dict[str, int]:
        """Parse test statistics summary."""
        stats = {
            'passed': 0,
            'failed': 0,
            'error': 0,
            'skipped': 0,
            'warnings': 0
        }
        
        for line in self._lines:
            match = self.TEST_STATS_PATTERN.match(line.strip())
            if match:
                stats['passed'] = int(match.group(1) or 0)
                stats['skipped'] = int(match.group(2) or 0)
                stats['warnings'] = int(match.group(3) or 0) 
                stats['error'] = int(match.group(4) or 0)
                stats['failed'] = int(match.group(5) or 0)
                break
                
        return stats
    
    def parse_coverage(self) -> Optional[float]:
        """Parse coverage percentage."""
        for line in reversed(self._lines):
            match = self.COVERAGE_PATTERN.match(line.strip())
            if match:
                return float(match.group(1))
        return None
    
    def parse_errors(self) -> List[TestError]:
        """Parse test errors with full context."""
        errors = []
        i = 0
        
        while i < len(self._lines):
            line = self._lines[i].strip()
            
            # Look for error headers
            if self.ERROR_HEADER_PATTERN.match(line):
                error = self._extract_error_details(i)
                if error:
                    errors.append(error)
                    i = error[1]  # Skip to end of this error
                    continue
            
            i += 1
            
        return [e[0] for e in errors if e]
    
    def _extract_error_details(self, start_idx: int) -> Optional[Tuple[TestError, int]]:
        """Extract error details starting from an error header."""
        i = start_idx + 1
        test_name = None
        error_type = None
        error_message = []
        traceback = []
        captured_output = []
        in_traceback = False
        in_captured = False
        
        # Extract test name from the header line
        header = self._lines[start_idx].strip()
        if "ERROR at" in header or "FAILED" in header:
            # Extract test name from header
            parts = header.split()
            for j, part in enumerate(parts):
                if part.startswith("test_"):
                    test_name = parts[j-1] if j > 0 else part
                    break
        
        while i < len(self._lines):
            line = self._lines[i]
            
            # Check for end of error section
            if line.startswith("=====") or line.startswith("-----"):
                if "Captured" in line:
                    in_captured = True
                    in_traceback = False
                else:
                    break
            
            # Parse content based on section
            if in_captured:
                captured_output.append(line)
            elif line.strip().startswith("E "):
                # Error message line
                error_message.append(line.strip()[2:])
                if not error_type and ":" in line:
                    error_type = line.split(":")[0].strip()[2:]
            elif line.strip() and (line.startswith(" ") or line.startswith(">")):
                traceback.append(line.rstrip())
            elif line.strip().endswith(".py:") or " in " in line:
                # Traceback location
                traceback.append(line.rstrip())
                in_traceback = True
            
            i += 1
        
        if test_name and error_type:
            return TestError(
                test_name=test_name,
                error_type=error_type,
                error_message="\n".join(error_message),
                traceback=traceback,
                captured_output="\n".join(captured_output) if captured_output else None
            ), i
        
        return None
    
    def get_failed_tests(self) -> List[str]:
        """Get list of failed test names."""
        results = self.parse_test_results()
        return [r.test_name for r in results if r.status in ('FAILED', 'ERROR')]
    
    def get_summary(self) -> Dict[str, any]:
        """Get a summary of the test run."""
        stats = self.parse_test_stats()
        coverage = self.parse_coverage()
        failed_tests = self.get_failed_tests()
        
        return {
            'total': sum(stats.values()) - stats['warnings'],
            'passed': stats['passed'],
            'failed': stats['failed'] + stats['error'],
            'skipped': stats['skipped'],
            'coverage': coverage,
            'failed_tests': failed_tests
        }