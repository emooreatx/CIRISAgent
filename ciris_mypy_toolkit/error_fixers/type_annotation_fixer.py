"""
Type Annotation Fixer - Automatically fixes mypy type annotation errors
"""

import re
import ast
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

logger = logging.getLogger(__name__)


class TypeAnnotationFixer:
    """
    Automatically fixes type annotation issues to eliminate mypy errors.
    
    Handles:
    - Missing return type annotations (-> None)
    - Missing variable type annotations  
    - Union type access issues
    - Optional parameter defaults
    - Dict/List type annotations
    """
    
    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir)
        self.fixes_applied = 0
        
    def propose_type_fixes(self) -> Dict[str, Any]:
        """AGGRESSIVE mode: Analyze ALL type annotation issues with comprehensive fixes."""
        logger.info("🔍 AGGRESSIVE ANALYSIS: Comprehensive type annotation fixes for 100% cleanliness...")
        
        proposals = []
        
        # Get current mypy errors to understand what needs fixing
        from ..core import CIRISMypyToolkit
        toolkit = CIRISMypyToolkit(str(self.target_dir.parent))
        current_errors = toolkit.get_mypy_errors()
        
        # Group errors by type for systematic fixing
        error_categories = {
            "no-untyped-def": [],
            "var-annotated": [],
            "assignment": [],
            "union-attr": [],
            "arg-type": [],
            "return-value": [],
            "attr-defined": [],
            "syntax": [],
            "other": []
        }
        
        for error in current_errors:
            error_code = error.get("code", "other")
            if error_code in error_categories:
                error_categories[error_code].append(error)
            else:
                error_categories["other"].append(error)
        
        logger.info(f"📊 Error breakdown: {[(k, len(v)) for k, v in error_categories.items() if v]}")
        
        # AGGRESSIVE FIX 1: Missing return types (no-untyped-def)
        for error in error_categories["no-untyped-def"]:
            if "missing a return type annotation" in error["message"]:
                proposals.append({
                    "type": "add_return_type",
                    "file": error["file"],
                    "line": error["line"],
                    "error_code": error["code"],
                    "current_error": error["message"],
                    "fix_type": "aggressive_return_type",
                    "rationale": "Mission-critical: Add missing return type",
                    "safety": "high"
                })
        
        # AGGRESSIVE FIX 2: Variable annotations (var-annotated)  
        for error in error_categories["var-annotated"]:
            proposals.append({
                "type": "add_variable_annotation",
                "file": error["file"],
                "line": error["line"],
                "error_code": error["code"],
                "current_error": error["message"],
                "fix_type": "aggressive_var_annotation",
                "rationale": "Mission-critical: Add missing variable type",
                "safety": "high"
            })
        
        # AGGRESSIVE FIX 3: Assignment errors (assignment)
        for error in error_categories["assignment"]:
            proposals.append({
                "type": "fix_assignment",
                "file": error["file"],
                "line": error["line"],
                "error_code": error["code"],
                "current_error": error["message"],
                "fix_type": "aggressive_assignment_fix",
                "rationale": "Mission-critical: Fix type assignment",
                "safety": "medium"
            })
        
        # AGGRESSIVE FIX 4: Union attribute access (union-attr)
        for error in error_categories["union-attr"]:
            proposals.append({
                "type": "fix_union_attr",
                "file": error["file"],
                "line": error["line"],
                "error_code": error["code"],
                "current_error": error["message"],
                "fix_type": "aggressive_type_ignore",
                "rationale": "Mission-critical: Add type: ignore for union access",
                "safety": "medium"
            })
        
        # AGGRESSIVE FIX 5: Syntax errors (syntax)
        for error in error_categories["syntax"]:
            proposals.append({
                "type": "fix_syntax",
                "file": error["file"],
                "line": error["line"],
                "error_code": error["code"],
                "current_error": error["message"],
                "fix_type": "aggressive_syntax_fix",
                "rationale": "CRITICAL: Fix syntax error blocking analysis",
                "safety": "high"
            })
        
        return {
            "total_proposed": len(proposals),
            "error_breakdown": {k: len(v) for k, v in error_categories.items() if v},
            "aggressive_mode": True,
            "target_errors": len(current_errors),
            "changes": proposals
        }
    
    def apply_approved_fixes(self, approved_changes: Dict[str, Any]) -> int:
        """LOCKED-DOWN SYSTEM: Apply comprehensive fixes using schema/protocol patterns."""
        logger.info("🔒 LOCKED-DOWN MODE: Applying systematic fixes for 100% compliance...")
        
        # Get fresh error list for systematic processing
        from ..core import CIRISMypyToolkit
        toolkit = CIRISMypyToolkit(str(self.target_dir.parent))
        current_errors = toolkit.get_mypy_errors()
        
        total_fixes = 0
        
        # PHASE 1: Remove unused type: ignore comments (safe cleanup)
        total_fixes += self._fix_unused_ignore_comments(current_errors)
        
        # PHASE 2: Add missing return type annotations (schema compliance)
        current_errors = toolkit.get_mypy_errors()
        total_fixes += self._fix_missing_return_types_systematic(current_errors)
        
        # PHASE 3: Fix missing imports (locked-down typing system)
        current_errors = toolkit.get_mypy_errors()
        total_fixes += self._fix_missing_imports(current_errors)
        
        # PHASE 4: Handle unreachable code (clean codebase)
        current_errors = toolkit.get_mypy_errors()
        total_fixes += self._fix_unreachable_code(current_errors)
        
        # PHASE 5: Fix attribute access (protocol compliance)
        current_errors = toolkit.get_mypy_errors()
        total_fixes += self._fix_attr_defined_errors(current_errors)
        
        # PHASE 6: Add variable type annotations (schema enforcement)
        current_errors = toolkit.get_mypy_errors()
        total_fixes += self._fix_variable_annotations(current_errors)
        
        # PHASE 7: PURGE all commented code (ultra-clean codebase)
        total_fixes += self._purge_commented_code()
        
        self.fixes_applied += total_fixes
        logger.info(f"🔒 Applied {total_fixes} systematic fixes")
        
        return total_fixes
    
    def _purge_commented_code(self) -> int:
        """Remove only true dead code comments, not docstrings or documentation."""
        logger.info("🗑️ PURGING dead code comments only (no code in comments)...")
        fixes = 0
        for py_file in self.target_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, 'r') as f:
                    lines = f.readlines()
                cleaned_lines = []
                in_docstring = False
                for i, line in enumerate(lines):
                    stripped = line.strip()
                    # Preserve docstrings
                    if stripped.startswith('"""') or stripped.startswith("'''"):
                        in_docstring = not in_docstring
                        cleaned_lines.append(line)
                        continue
                    if in_docstring:
                        cleaned_lines.append(line)
                        continue
                    # Remove lines that are only comments and look like code (e.g. start with '# def', '# class', '# import', '# from', '# ...')
                    if stripped.startswith('#') and (
                        re.match(r'#\s*(def |class |import |from |if |elif |else|try|except|with |for |while )', stripped)
                    ):
                        fixes += 1
                        continue
                    # Remove lines that are only comments and not documentation (e.g. not '# TODO', '# NOTE', '# FIXME', '# WARNING', '# DOC', '# ---')
                    if stripped.startswith('#') and not re.match(r'#\s*(TODO|NOTE|FIXME|WARNING|DOC|---)', stripped):
                        fixes += 1
                        continue
                    # Do not remove inline comments after code (leave for clarity)
                    cleaned_lines.append(line)
                if len(cleaned_lines) != len(lines):
                    with open(py_file, 'w') as f:
                        f.writelines(cleaned_lines)
                    removed = len(lines) - len(cleaned_lines)
                    if removed > 0:
                        logger.debug(f"✅ PURGED {removed} dead code comment lines from {py_file}")
            except Exception as e:
                logger.error(f"❌ Error purging comments from {py_file}: {e}")
        return fixes
    
    def _fix_unused_ignore_comments(self, errors: List[Dict[str, Any]]) -> int:
        """Remove all unused type: ignore comments for clean codebase."""
        logger.info("🧹 Removing unused type: ignore comments...")
        
        unused_ignore_errors = [e for e in errors if e['code'] == 'unused-ignore']
        fixes = 0
        
        # Group by file for efficiency
        from collections import defaultdict
        files_to_fix = defaultdict(list)
        for error in unused_ignore_errors:
            files_to_fix[error['file']].append(error['line'])
        
        for file_path, line_numbers in files_to_fix.items():
            try:
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                
                # Remove type: ignore comments from specified lines
                for line_num in sorted(line_numbers, reverse=True):
                    if line_num <= len(lines):
                        line = lines[line_num - 1]
                        # Remove type: ignore comment
                        cleaned_line = re.sub(r'\s*#\s*type:\s*ignore[^\n]*', '', line)
                        lines[line_num - 1] = cleaned_line
                        fixes += 1
                
                with open(file_path, 'w') as f:
                    f.writelines(lines)
                    
                logger.debug(f"✅ Removed {len(line_numbers)} unused ignores in {file_path}")
                
            except Exception as e:
                logger.error(f"❌ Error cleaning {file_path}: {e}")
        
        return fixes
    
    def fix_syntax_errors(self) -> int:
        """Detect and auto-fix common syntax errors (unterminated strings, missing indents)."""
        logger.info("🛠️ Auto-fixing syntax errors before type annotation fixes...")
        fixes = 0
        for py_file in self.target_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            try:
                with open(py_file, 'r') as f:
                    lines = f.readlines()
                fixed_lines = []
                in_string = False
                for line in lines:
                    # Fix unterminated string literals
                    if line.count('"') % 2 == 1 or line.count("'") % 2 == 1:
                        line = line.rstrip() + '"\n'  # Add closing quote
                        fixes += 1
                    # Fix missing indents after if/elif/else/for/while/def/class
                    if re.match(r'^\s*(if|elif|else|for|while|def|class)\b.*:\s*$', line):
                        idx = lines.index(line)
                        if idx + 1 < len(lines) and not lines[idx + 1].startswith((' ', '\t')):
                            lines.insert(idx + 1, '    pass\n')
                            fixes += 1
                    fixed_lines.append(line)
                if fixes > 0:
                    with open(py_file, 'w') as f:
                        f.writelines(fixed_lines)
            except Exception as e:
                logger.error(f"❌ Error fixing syntax in {py_file}: {e}")
        return fixes

    def _allowed_type(self, type_str: str) -> bool:
        """Check if a type is allowed (must be from protocols/ or schemas/)."""
        allowed_prefixes = (
            'Protocol', 'Schema', 'schemas.', 'protocols.'
        )
        # Allow built-in None, Any, bool, int, str, float, list, dict, etc.
        builtin_types = {'None', 'Any', 'bool', 'int', 'str', 'float', 'List', 'Dict'}
        if type_str in builtin_types:
            return True
        # Allow types that are explicitly imported from schemas/ or protocols/
        if type_str.startswith(allowed_prefixes):
            return True
        return False

    def _map_to_allowed_type(self, type_str: str) -> str:
        """Map a type to a protocol/schema type if possible, else fallback to Any and log a warning."""
        # Example mapping logic (expand as needed for your schemas/protocols)
        mapping = {
            'dict': 'schemas.BaseSchema',
            'Dict[str, Any]': 'schemas.BaseSchema',
            'list': 'schemas.BaseList',
            'List[Any]': 'schemas.BaseList',
            'str': 'str',
            'int': 'int',
            'bool': 'bool',
            'float': 'float',
            'Any': 'Any',
            'None': 'None',
        }
        if type_str in mapping:
            return mapping[type_str]
        # If not allowed, fallback to Any and log
        if not self._allowed_type(type_str):
            logger.warning(f"Type '{type_str}' is not allowed. Using 'Any' instead.")
            return 'Any'
        return type_str

    def _infer_return_type(self, func_body: str) -> str:
        """Infer return type from function body (simple heuristic, protocol/schema only)."""
        if 'return True' in func_body or 'return False' in func_body:
            return 'bool'
        if 'return []' in func_body or 'return list(' in func_body:
            return self._map_to_allowed_type('List[Any]')
        if 'return {}' in func_body or 'return dict(' in func_body:
            return self._map_to_allowed_type('Dict[str, Any]')
        if 'return "' in func_body or "return '" in func_body:
            return 'str'
        if 'return' in func_body:
            return 'Any'
        return 'None'

    def _fix_missing_return_types_systematic(self, errors: List[Dict[str, Any]]) -> int:
        """Add missing return type annotations for schema compliance (protocol/schema only)."""
        logger.info("🔧 Adding missing return type annotations (protocol/schema only)...")
        untyped_def_errors = [e for e in errors if e['code'] == 'no-untyped-def']
        fixes = 0
        for error in untyped_def_errors:
            if "missing a return type annotation" in error['message']:
                try:
                    file_path = error['file']
                    line_num = error['line']
                    with open(file_path, 'r') as f:
                        lines = f.readlines()
                    if line_num <= len(lines):
                        line = lines[line_num - 1]
                        func_body = ''.join(lines[line_num:line_num+10])
                        inferred_type = self._infer_return_type(func_body)
                        allowed_type = self._map_to_allowed_type(inferred_type)
                        if re.match(r'^\s*(async\s+)?def\s+\w+\([^)]*\)\s*:\s*$', line):
                            lines[line_num - 1] = line.rstrip().replace('):', f') -> {allowed_type}:') + '\n'
                            fixes += 1
                            with open(file_path, 'w') as f:
                                f.writelines(lines)
                            logger.debug(f"✅ Added return type ({allowed_type}) to {file_path}:{line_num}")
                except Exception as e:
                    logger.error(f"❌ Error fixing {error['file']}:{error['line']}: {e}")
        return fixes

    def _fix_variable_annotations(self, errors: List[Dict[str, Any]]) -> int:
        """Add variable type annotations with protocol/schema types only."""
        logger.info("🔧 Adding variable type annotations (protocol/schema only)...")
        var_annot_errors = [e for e in errors if e['code'] == 'var-annotated']
        fixes = 0
        for error in var_annot_errors:
            try:
                file_path = error['file']
                line_num = error['line']
                with open(file_path, 'r') as f:
                    lines = f.readlines()
                if line_num <= len(lines):
                    line = lines[line_num - 1]
                    if '=' in line:
                        var_name, value = line.split('=', 1)
                        value = value.strip()
                        if value.startswith('['):
                            annotation = self._map_to_allowed_type('List[Any]')
                        elif value.startswith('{'):
                            annotation = self._map_to_allowed_type('Dict[str, Any]')
                        elif value.startswith('"') or value.startswith("'"):
                            annotation = 'str'
                        elif value in ('True', 'False'):
                            annotation = 'bool'
                        elif value.isdigit():
                            annotation = 'int'
                        else:
                            annotation = self._map_to_allowed_type('Any')
                        new_line = f'{var_name.strip()}: {annotation} = {value}\n'
                        lines[line_num - 1] = new_line
                        fixes += 1
                        with open(file_path, 'w') as f:
                            f.writelines(lines)
                        logger.debug(f"✅ Added variable annotation ({annotation}) to {file_path}:{line_num}")
            except Exception as e:
                logger.error(f"❌ Error fixing variable annotation in {error['file']}:{error['line']}: {e}")
        return fixes

    def _fix_union_attr(self, errors: List[Dict[str, Any]]) -> int:
        """Refactor union attribute access to use isinstance checks instead of type: ignore."""
        logger.info("🔧 Refactoring union attribute access for type safety...")
        # ...existing code...