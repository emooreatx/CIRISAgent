"""
Schema Validator Whitelist Configuration

This module defines patterns that should be excluded from schema compliance checks.
These are legitimate patterns that don't violate CIRIS principles.
"""

from typing import Dict, List, Pattern, Set
import re

# Private methods that are legitimately called within their own classes
INTERNAL_PRIVATE_METHODS: Set[str] = {
    # Base class methods commonly overridden/called
    "_initialize", "_cleanup", "_validate", "_check_dependencies",
    "_get_metadata", "_get_actions", "_get_capabilities",
    "_collect_custom_metrics", "_handle_error", "_track_error",
    
    # Time service methods
    "_now", "_get_time_service", "_calculate_uptime",
    
    # Authentication methods
    "_hash_password", "_verify_password", "_encode_public_key",
    "_decode_public_key", "_store_wa_certificate",
    
    # Audit/logging methods
    "_audit_log", "_log_access", "_record_event", "_emit_telemetry",
    "_update_trace_correlation",
    
    # Configuration methods
    "_get_config_manager", "_ensure_config", "_register_config_listener",
    
    # Service management
    "_register_dependencies", "_register_adapter_services",
    "_get_audit_service", "_get_memory_service",
    
    # Utility methods
    "_deserialize_datetime", "_serialize_datetime",
    "_create_symlink", "_map_log_level_to_severity", "_calculate_urgency",
    "_save_incident_to_graph",
    
    # Async execution
    "_execute_async_handlers", "_request_shutdown_sync",
}

# File patterns where private method usage is expected
FILE_PATTERNS_ALLOW_PRIVATE: List[Pattern[str]] = [
    # Base classes define private methods for subclasses
    re.compile(r"base_.*\.py$"),
    re.compile(r".*_base\.py$"),
    
    # Test files can test private methods
    re.compile(r"test_.*\.py$"),
    re.compile(r".*_test\.py$"),
    
    # Internal utility modules
    re.compile(r"utils/.*\.py$"),
    re.compile(r"infrastructure/.*\.py$"),
]

# Patterns for SQL/database access that are legitimate
SQL_WHITELIST_PATTERNS: List[Pattern[str]] = [
    # Persistence layer is allowed direct SQL
    re.compile(r"persistence/.*\.py$"),
    
    # Database maintenance service needs SQL
    re.compile(r"database_maintenance.*\.py$"),
    
    # Migration scripts
    re.compile(r"migrations?/.*\.py$"),
]

def is_private_method_whitelisted(file_path: str, method_name: str) -> bool:
    """
    Check if a private method call should be whitelisted.
    
    Args:
        file_path: Path to the file containing the call
        method_name: Name of the private method (including underscore)
        
    Returns:
        True if this usage should be whitelisted
    """
    # Remove leading underscore(s) for lookup
    clean_method = method_name.lstrip('_')
    
    # Check if method is in whitelist
    if clean_method in INTERNAL_PRIVATE_METHODS:
        return True
    
    # Check if file pattern allows private methods
    for pattern in FILE_PATTERNS_ALLOW_PRIVATE:
        if pattern.search(file_path):
            return True
    
    # Special case: __init__ is always allowed
    if method_name == "__init__":
        return True
    
    # Special case: private methods called within same file are usually OK
    # (This would require more context to check properly)
    
    return False

def is_sql_access_whitelisted(file_path: str) -> bool:
    """
    Check if SQL/database access in a file should be whitelisted.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if SQL access should be whitelisted for this file
    """
    for pattern in SQL_WHITELIST_PATTERNS:
        if pattern.search(file_path):
            return True
    
    return False

def is_dict_any_whitelisted(file_path: str, line_content: str) -> bool:
    """
    Check if Dict[str, Any] usage should be whitelisted.
    
    Args:
        file_path: Path to the file
        line_content: The line containing Dict[str, Any]
        
    Returns:
        True if this usage should be whitelisted
    """
    # Test files can use Dict[str, Any] for test data
    if "test_" in file_path or "_test.py" in file_path:
        return True
    
    # Type stubs and protocol definitions might need Any
    if ".pyi" in file_path or "typing" in line_content:
        return True
    
    # Already handled by protocol whitelist
    if "decorator" in line_content.lower():
        return True
    
    return False

def should_skip_file(file_path: str) -> bool:
    """
    Check if a file should be skipped entirely for schema validation.
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if this file should be skipped
    """
    path_str = str(file_path).lower()
    
    # Skip test files
    if "/tests/" in path_str or "test_" in path_str or "_test.py" in path_str:
        return True
    
    # Skip migration files
    if "/migrations/" in path_str or "migration" in path_str:
        return True
    
    # Skip example/demo files
    if "/examples/" in path_str or "example" in path_str or "demo" in path_str:
        return True
    
    # Skip setup files
    if "setup.py" in path_str or "setup_" in path_str:
        return True
    
    # Skip type stub files
    if path_str.endswith(".pyi"):
        return True
    
    return False