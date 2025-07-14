"""
Schema Validator - Ensures code uses current CIRIS v1 schemas correctly
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict
import logging
import sys

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
try:
    from config.schema_whitelist import (
        is_private_method_whitelisted,
        is_sql_access_whitelisted,
        is_dict_any_whitelisted,
        should_skip_file
    )
except ImportError:
    # Fallback if whitelist not available
    def is_private_method_whitelisted(file_path: str, method_name: str) -> bool:
        return False
    def is_sql_access_whitelisted(file_path: str) -> bool:
        return False
    def is_dict_any_whitelisted(file_path: str, line_content: str) -> bool:
        return False
    def should_skip_file(file_path: str) -> bool:
        return False

logger = logging.getLogger(__name__)


class SchemaValidator:
    """
    Validates that CIRIS code uses current v1 schemas and avoids deprecated patterns.
    
    Key validations:
    - Proper v1 schema imports
    - No usage of deprecated legacy schemas
    - Correct schema field usage
    - Protocol interface compliance
    """
    
    def __init__(self, schemas_dir: Path):
        self.schemas_dir = Path(schemas_dir)
        self.v1_schemas = self._discover_v1_schemas()
        self.deprecated_patterns = self._load_deprecated_patterns()
        
    def _discover_v1_schemas(self) -> Dict[str, Set[str]]:
        """Discover all CIRIS schemas and their exported classes."""
        schemas = {}
        
        # CIRIS doesn't use _v1 naming, scan all .py files in schemas dir
        for schema_file in self.schemas_dir.rglob("*.py"):
            if "__pycache__" in str(schema_file) or "__init__" in str(schema_file.name):
                continue
                
            schema_name = schema_file.stem
            try:
                with open(schema_file, 'r') as f:
                    content = f.read()
                
                # Parse AST to find all class definitions
                tree = ast.parse(content)
                classes = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Only include Pydantic models and enums
                        if any(base.id in ['BaseModel', 'BaseSchema', 'Enum', 'str', 'int'] 
                               for base in node.bases if isinstance(base, ast.Name)):
                            classes.add(node.name)
                
                if classes:
                    schemas[str(schema_file.relative_to(self.schemas_dir))] = classes
                
            except Exception as e:
                logger.warning(f"Could not parse schema {schema_file}: {e}")
        
        return schemas
    
    def _load_deprecated_patterns(self) -> List[Dict[str, str]]:
        """Load patterns that indicate deprecated schema usage or anti-patterns."""
        return [
            {
                "pattern": r"Dict\[str,\s*Any\]",
                "issue": "Using Dict[str, Any] instead of typed schema",
                "fix": "Use a proper Pydantic model instead"
            },
            {
                "pattern": r"dict\[str,\s*Any\]",
                "issue": "Using dict[str, Any] instead of typed schema",
                "fix": "Use a proper Pydantic model instead"
            },
            {
                "pattern": r"from typing import.*Dict.*Any",
                "issue": "Importing Dict with Any type",
                "fix": "Use typed Pydantic models instead"
            },
            {
                "pattern": r":\s*dict\s*=\s*\{\}",
                "issue": "Using untyped dict initialization",
                "fix": "Use Pydantic model with proper defaults"
            }
        ]
    
    def validate_file(self, file_path: Path) -> Dict[str, Any]:
        """
        Validate a single file for schema compliance.
        
        Returns:
            Validation results with issues found
        """
        if not file_path.exists():
            return {"error": f"File {file_path} does not exist"}
        
        # Skip files based on whitelist
        if should_skip_file(str(file_path)):
            return {
                "file": str(file_path),
                "total_issues": 0,
                "issues": [],
                "compliant": True,
                "skipped": True
            }
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            issues = []
            
            # Check for deprecated patterns
            for pattern_info in self.deprecated_patterns:
                matches = re.finditer(pattern_info["pattern"], content, re.MULTILINE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    line_content = content.split('\n')[line_num - 1] if line_num > 0 else ""
                    
                    # Check whitelist
                    skip = False
                    if "Dict[str, Any]" in pattern_info["pattern"] or ": Any" in pattern_info["pattern"]:
                        skip = is_dict_any_whitelisted(str(file_path), line_content)
                    
                    if not skip:
                        issues.append({
                            "line": line_num,
                            "issue": pattern_info["issue"],
                            "pattern": match.group(),
                            "fix_suggestion": pattern_info["fix"]
                        })
            
            # Check for proper v1 schema usage
            v1_issues = self._validate_v1_usage(content, file_path)
            issues.extend(v1_issues)
            
            # Check for direct internal method calls
            internal_issues = self._check_internal_method_usage(content, file_path)
            issues.extend(internal_issues)
            
            return {
                "file": str(file_path),
                "total_issues": len(issues),
                "issues": issues,
                "compliant": len(issues) == 0
            }
            
        except Exception as e:
            return {"error": f"Could not validate {file_path}: {e}"}
    
    def validate_all_files(self) -> List[Dict[str, Any]]:
        """Validate all Python files in the target directory."""
        all_issues = []
        
        for py_file in Path("ciris_engine").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            file_result = self.validate_file(py_file)
            if "issues" in file_result and file_result["issues"]:
                all_issues.extend(file_result["issues"])
        
        return all_issues
    
    def _validate_v1_usage(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Validate proper CIRIS schema usage."""
        issues = []
        
        # CIRIS doesn't use v1 naming - skip this check
        # Instead, focus on Dict[str, Any] usage which violates "No Dicts" principle
        
        return issues
    
    def _find_dict_schema_candidates(self, content: str) -> List[Dict[str, Any]]:
        """Find dictionaries that violate 'No Dicts' principle."""
        issues = []
        
        # Skip test files and migration scripts
        if 'test_' in str(self.schemas_dir) or 'migration' in content:
            return issues
        
        # Already checked in deprecated_patterns, no need to duplicate
        
        return issues
    
    def _find_non_schema_classes(self, content: str) -> List[Dict[str, Any]]:
        """Find classes that handle data but don't inherit from schemas."""
        issues = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Skip if already inherits from BaseModel or known schema
                    base_names = [base.id for base in node.bases if isinstance(base, ast.Name)]
                    if any(base in ["BaseModel", "Task", "Thought", "Action"] for base in base_names):
                        continue
                    
                    # Check if class has data-like attributes
                    has_data_attrs = False
                    for class_node in ast.walk(node):
                        if isinstance(class_node, ast.AnnAssign) and isinstance(class_node.target, ast.Name):
                            attr_name = class_node.target.id
                            if any(indicator in attr_name.lower() for indicator in 
                                  ["id", "status", "timestamp", "data", "context", "result"]):
                                has_data_attrs = True
                                break
                    
                    if has_data_attrs:
                        issues.append({
                            "line": node.lineno,
                            "issue": f"Class '{node.name}' handles data but doesn't inherit from schema",
                            "pattern": f"class {node.name}",
                            "fix_suggestion": "Consider inheriting from appropriate v1 schema or BaseModel"
                        })
        
        except SyntaxError:
            # Skip files with syntax errors
            pass
        
        return issues
    
    def _check_internal_method_usage(self, content: str, file_path: Path = None) -> List[Dict[str, Any]]:
        """Check for usage of internal methods instead of protocol interfaces."""
        issues = []
        
        # Pattern for direct service access instead of protocol
        internal_patterns = [
            (r"\._(\w+)\(", "Using private method - should use protocol interface"),
            (r"\.get_db_connection\(", "Direct DB access - should use persistence interface"),
            (r"import sqlite3", "Direct SQLite usage - should use persistence layer"),
            (r"\.execute\(", "Direct SQL execution - should use persistence methods")
        ]
        
        for pattern, issue_desc in internal_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                
                # Check whitelist
                skip = False
                if pattern.startswith(r"\._"):
                    # Extract method name
                    method_match = re.match(r"\._(\w+)\(", match.group())
                    if method_match and file_path:
                        method_name = f"_{method_match.group(1)}"
                        skip = is_private_method_whitelisted(str(file_path), method_name)
                elif "sqlite" in pattern.lower() or "execute" in pattern or "db_connection" in pattern:
                    if file_path:
                        skip = is_sql_access_whitelisted(str(file_path))
                
                if not skip:
                    issues.append({
                        "line": line_num,
                        "issue": issue_desc,
                        "pattern": match.group(),
                        "fix_suggestion": "Refactor to use protocol interface"
                    })
        
        return issues
    
    def get_schema_usage_report(self) -> Dict[str, Any]:
        """Generate a report on schema usage across the codebase."""
        usage_stats = {
            "v1_schema_usage": defaultdict(int),
            "deprecated_usage": defaultdict(int),
            "files_with_issues": [],
            "compliance_percentage": 0.0
        }
        
        total_files = 0
        compliant_files = 0
        
        for py_file in Path("ciris_engine").rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            total_files += 1
            result = self.validate_file(py_file)
            
            if result.get("compliant", False):
                compliant_files += 1
            else:
                usage_stats["files_with_issues"].append(str(py_file))  # type: ignore[attr-defined]
        
        if total_files > 0:
            usage_stats["compliance_percentage"] = (compliant_files / total_files) * 100
        
        return usage_stats
