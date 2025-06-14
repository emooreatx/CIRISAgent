"""
Schema Validator - Ensures code uses current CIRIS v1 schemas correctly
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Set
from collections import defaultdict
import logging

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
        """Discover all v1 schemas and their exported classes."""
        v1_schemas = {}
        
        for schema_file in self.schemas_dir.glob("*_v1.py"):
            schema_name = schema_file.stem
            try:
                with open(schema_file, 'r') as f:
                    content = f.read()
                
                # Parse AST to find all class definitions
                tree = ast.parse(content)
                classes = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        classes.add(node.name)
                
                v1_schemas[schema_name] = classes
                
            except Exception as e:
                logger.warning(f"Could not parse schema {schema_file}: {e}")
        
        return v1_schemas
    
    def _load_deprecated_patterns(self) -> List[Dict[str, str]]:
        """Load patterns that indicate deprecated schema usage."""
        return [
            {
                "pattern": r"from\s+\w+\.schemas\.\w+\s+import.*(?<!_v1)",
                "issue": "Using non-v1 schema import",
                "fix": "Update to use _v1 schema imports"
            },
            {
                "pattern": r"\.processing_context",
                "issue": "Using deprecated processing_context field",
                "fix": "Use v1 schema fields instead"
            },
            {
                "pattern": r"legacy_\w+",
                "issue": "Using legacy field names",
                "fix": "Update to use v1 field names"
            },
            {
                "pattern": r"from.*schemas import (?!.*_v1)",
                "issue": "Non-v1 schema import detected",
                "fix": "Import from *_v1 schema modules"
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
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            issues = []
            
            # Check for deprecated patterns
            for pattern_info in self.deprecated_patterns:
                matches = re.finditer(pattern_info["pattern"], content, re.MULTILINE)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
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
            internal_issues = self._check_internal_method_usage(content)
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
        """Validate proper v1 schema usage."""
        issues = []
        
        # Check if file should be using schemas but isn't
        if "schemas/" not in str(file_path) and any(
            keyword in content for keyword in ["Task", "Thought", "Action", "Context"]
        ):
            # Check for proper v1 imports
            if not re.search(r"from.*schemas.*_v1.*import", content):
                issues.append({
                    "line": 1,
                    "issue": "File uses schema concepts but no v1 schema imports found",
                    "fix_suggestion": "Add proper v1 schema imports"
                })
        
        # Check for dict/object usage that should be schemas
        schema_candidates = self._find_dict_schema_candidates(content)
        issues.extend(schema_candidates)
        
        return issues
    
    def _find_dict_schema_candidates(self, content: str) -> List[Dict[str, Any]]:
        """Find dictionaries and objects that should probably be schemas."""
        issues = []
        lines = content.split('\n')
        
        # Patterns that suggest a dict should be a schema
        schema_indicators = [
            # Dict literals with schema-like field names
            (r'\{\s*["\'](?:task_id|thought_id|action_type|status|timestamp|context)["\']', 
             "Dict with schema-like fields should use proper schema class"),
            
            # Function parameters that look like they should be schemas
            (r'def\s+\w+\([^)]*\w+:\s*Dict\[str,\s*Any\][^)]*\).*(?:task|thought|action|result)', 
             "Function parameter typed as Dict[str, Any] should use schema class"),
            
            # Return types that should be schemas
            (r'->\s*Dict\[str,\s*Any\].*(?:task|thought|action|result)', 
             "Return type Dict[str, Any] should use schema class"),
            
            # Variable assignments that create data structures
            (r'\w+\s*=\s*\{[^}]*["\'](?:id|type|status|timestamp)["\']', 
             "Data structure creation should use schema class"),
            
            # JSON-like structures that could be schemas
            (r'\{[^}]*["\'](?:created_at|updated_at|task_id|thought_id)["\']', 
             "JSON structure matches schema pattern - consider using schema class"),
            
            # Context dictionaries
            (r'context\s*=\s*\{', 
             "Context dict should potentially use ContextSchema"),
            
            # Result dictionaries  
            (r'result\s*=\s*\{[^}]*["\'](?:status|success|error|data)["\']', 
             "Result dict should potentially use result schema"),
             
            # Config dictionaries
            (r'config\s*=\s*\{[^}]*["\'](?:settings|options|parameters)["\']', 
             "Config dict should potentially use config schema")
        ]
        
        for i, line in enumerate(lines, 1):
            for pattern, issue_desc in schema_indicators:
                if re.search(pattern, line, re.IGNORECASE):
                    issues.append({
                        "line": i,
                        "issue": issue_desc,
                        "pattern": line.strip(),
                        "fix_suggestion": "Replace dict usage with appropriate v1 schema class"
                    })
        
        # Check for class definitions that might need schema inheritance
        class_issues = self._find_non_schema_classes(content)
        issues.extend(class_issues)
        
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
    
    def _check_internal_method_usage(self, content: str) -> List[Dict[str, Any]]:
        """Check for usage of internal methods instead of protocol interfaces."""
        issues = []
        
        # Pattern for direct service access instead of protocol
        internal_patterns = [
            (r"\._\w+\(", "Using private method - should use protocol interface"),
            (r"\.get_db_connection\(", "Direct DB access - should use persistence interface"),
            (r"import sqlite3", "Direct SQLite usage - should use persistence layer"),
            (r"\.execute\(", "Direct SQL execution - should use persistence methods")
        ]
        
        for pattern, issue_desc in internal_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
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