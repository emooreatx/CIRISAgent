"""Pytest command builder with various options."""

from typing import Optional, List
from pathlib import Path


class PytestCommand:
    """Builds pytest commands with various options."""
    
    def __init__(self):
        self.base_cmd = "pytest -xvs --tb=short"
        self.options = []
        
    def with_coverage(self, cov_path: Optional[str] = None) -> 'PytestCommand':
        """Add coverage reporting.
        
        Args:
            cov_path: Specific path to measure coverage for. If None, covers all ciris_engine.
        """
        cov_target = cov_path or "ciris_engine"
        self.options.append(f"--cov={cov_target} --cov-report=term-missing --cov-report=html")
        return self
    
    def with_filter(self, pattern: str) -> 'PytestCommand':
        """Add -k filter pattern."""
        self.options.append(f"-k '{pattern}'")
        return self
    
    def with_specific_test(self, test_path: str) -> 'PytestCommand':
        """Run a specific test file or test."""
        # Remove any existing test paths
        self.base_cmd = f"pytest -xvs --tb=short {test_path}"
        return self
    
    def with_markers(self, markers: List[str]) -> 'PytestCommand':
        """Add marker filters."""
        for marker in markers:
            self.options.append(f"-m {marker}")
        return self
    
    def with_timeout(self, seconds: int) -> 'PytestCommand':
        """Add timeout for tests."""
        self.options.append(f"--timeout={seconds}")
        return self
    
    def with_parallel(self, workers: int = 4) -> 'PytestCommand':
        """Run tests in parallel."""
        self.options.append(f"-n {workers}")
        return self
    
    def with_verbose(self, level: int = 2) -> 'PytestCommand':
        """Set verbosity level."""
        v_flags = "v" * level
        self.base_cmd = self.base_cmd.replace("-xvs", f"-x{v_flags}s")
        return self
    
    def with_failfast(self, enabled: bool = True) -> 'PytestCommand':
        """Stop on first failure."""
        if not enabled:
            self.base_cmd = self.base_cmd.replace("-x", "")
        return self
    
    def with_last_failed(self) -> 'PytestCommand':
        """Run only last failed tests."""
        self.options.append("--lf")
        return self
    
    def with_failed_first(self) -> 'PytestCommand':
        """Run failed tests first, then others."""
        self.options.append("--ff")
        return self
    
    def build(self) -> str:
        """Build the final pytest command."""
        if self.options:
            return f"{self.base_cmd} {' '.join(self.options)}"
        return self.base_cmd
    

def build_pytest_command(
    coverage: bool = False,
    coverage_path: Optional[str] = None,
    filter_pattern: Optional[str] = None,
    test_path: Optional[str] = None,
    markers: Optional[List[str]] = None,
    timeout: Optional[int] = None,
    parallel: Optional[int] = None,
    verbose: int = 1,
    failfast: bool = True,
    last_failed: bool = False,
    failed_first: bool = False
) -> str:
    """
    Build a pytest command with the given options.
    
    This is a convenience function that builds common pytest commands.
    """
    builder = PytestCommand()
    
    if test_path:
        builder.with_specific_test(test_path)
    
    if coverage:
        builder.with_coverage(coverage_path)
    
    if filter_pattern:
        builder.with_filter(filter_pattern)
    
    if markers:
        builder.with_markers(markers)
    
    if timeout:
        builder.with_timeout(timeout)
    
    if parallel:
        builder.with_parallel(parallel)
    
    if verbose != 1:
        builder.with_verbose(verbose)
    
    if not failfast:
        builder.with_failfast(False)
    
    if last_failed:
        builder.with_last_failed()
    
    if failed_first:
        builder.with_failed_first()
    
    return builder.build()