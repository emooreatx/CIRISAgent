"""
Core CIRIS MyPy Toolkit - Main orchestrator for type safety and compliance
"""

import subprocess
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import logging

from .analyzers import SchemaValidator, ProtocolAnalyzer, UnusedCodeDetector
from .error_fixers import TypeAnnotationFixer, ProtocolComplianceFixer, SchemaAlignmentFixer

logger = logging.getLogger(__name__)


class CIRISMypyToolkit:
    """
    Main toolkit orchestrator for ensuring CIRIS schema and protocol compliance.
    
    This toolkit helps developers and agents building CIRIS adapters/modules
    ensure they follow proper schemas, protocols, and type safety.
    """
    
    def __init__(self, target_dir: str = "ciris_engine", schemas_dir: str = "ciris_engine/schemas"):
        self.target_dir = Path(target_dir)
        self.schemas_dir = Path(schemas_dir)
        
        # Initialize analyzers
        self.schema_validator = SchemaValidator(self.schemas_dir)
        self.protocol_analyzer = ProtocolAnalyzer(self.target_dir)
        self.unused_code_detector = UnusedCodeDetector(self.target_dir)
        
        # Initialize error fixers
        self.type_fixer = TypeAnnotationFixer(self.target_dir)
        self.protocol_fixer = ProtocolComplianceFixer(self.target_dir, self.schemas_dir)
        self.schema_fixer = SchemaAlignmentFixer(self.target_dir, self.schemas_dir)
        
        self.fixes_applied = 0
        
    def get_mypy_errors(self) -> List[Dict[str, Any]]:
        """Run mypy and parse errors with enhanced parsing."""
        cmd = f"python -m mypy {self.target_dir} --ignore-missing-imports --show-error-codes --no-error-summary"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        errors = []
        output = result.stderr
        
        for line in output.splitlines():
            # Enhanced error parsing
            match = re.search(r'^([^:]+):(\d+):(\d+):\s*error:\s*(.+?)\s*(?:\[([^\]]+)\])?', line)
            if match:
                errors.append({
                    'file': match.group(1),
                    'line': int(match.group(2)),
                    'col': int(match.group(3)),
                    'message': match.group(4).strip(),
                    'code': match.group(5).strip() if match.group(5) else 'unknown'
                })
        
        return errors
    
    def analyze_compliance(self) -> Dict[str, Any]:
        """
        Comprehensive compliance analysis for CIRIS codebase.
        
        Returns:
            Analysis report with schema, protocol, and type safety issues
        """
        logger.info("🔍 Starting CIRIS compliance analysis...")
        
        # Get mypy errors
        mypy_errors = self.get_mypy_errors()
        
        # Analyze schema compliance
        schema_issues = self.schema_validator.validate_all_files()
        
        # Analyze protocol usage
        protocol_issues = self.protocol_analyzer.analyze_protocol_usage()
        
        # Detect unused/uncalled code
        unused_code = self.unused_code_detector.find_unused_code()
        
        # Categorize mypy errors
        error_categories = self._categorize_errors(mypy_errors)
        
        report = {
            "total_mypy_errors": len(mypy_errors),
            "error_categories": error_categories,
            "schema_compliance": {
                "total_issues": len(schema_issues),
                "issues": schema_issues
            },
            "protocol_compliance": {
                "total_issues": len(protocol_issues),
                "issues": protocol_issues
            },
            "unused_code": {
                "total_items": len(unused_code),
                "items": unused_code
            },
            "recommendations": self._generate_recommendations(
                mypy_errors, schema_issues, protocol_issues, unused_code
            )
        }
        
        return report
    
    def fix_all_issues(self, categories: Optional[List[str]] = None) -> Dict[str, int]:
        """
        Fix all detected issues systematically.
        
        Args:
            categories: Specific categories to fix, or None for all
            
        Returns:
            Dictionary of fixes applied per category
        """
        logger.info("🛠️ Starting systematic issue fixing...")
        
        fixes_summary = {}
        
        # Default categories in order of safety/impact
        if categories is None:
            categories = [
                "type_annotations",
                "schema_alignment", 
                "protocol_compliance",
                "unused_code_removal"
            ]
        
        initial_errors = len(self.get_mypy_errors())
        
        for category in categories:
            logger.info(f"🎯 Fixing {category} issues...")
            
            if category == "type_annotations":
                fixes = self.type_fixer.fix_all_type_issues()
                fixes_summary["type_annotations"] = fixes
                
            elif category == "schema_alignment":
                fixes = self.schema_fixer.fix_schema_violations()
                fixes_summary["schema_alignment"] = fixes
                
            elif category == "protocol_compliance":
                fixes = self.protocol_fixer.fix_protocol_violations()
                fixes_summary["protocol_compliance"] = fixes
                
            elif category == "unused_code_removal":
                fixes = self.unused_code_detector.remove_unused_code()
                fixes_summary["unused_code_removal"] = fixes
        
        final_errors = len(self.get_mypy_errors())
        fixes_summary["total_errors_eliminated"] = initial_errors - final_errors
        
        return fixes_summary
    
    def validate_adapter_compliance(self, adapter_path: str) -> Dict[str, Any]:
        """
        Validate a specific adapter for CIRIS compliance.
        
        Args:
            adapter_path: Path to the adapter module
            
        Returns:
            Compliance report for the adapter
        """
        adapter_path = Path(adapter_path)
        
        if not adapter_path.exists():
            return {"error": f"Adapter path {adapter_path} does not exist"}
        
        # Validate adapter follows CIRIS patterns
        validation_results = {
            "schema_usage": self.schema_validator.validate_file(adapter_path),
            "protocol_implementation": self.protocol_analyzer.validate_adapter(adapter_path),
            "type_safety": self._check_adapter_types(adapter_path),
            "compliance_score": 0.0
        }
        
        # Calculate compliance score
        total_checks = 0
        passed_checks = 0
        
        for category, results in validation_results.items():
            if isinstance(results, dict) and "passed" in results:
                total_checks += results.get("total", 0)
                passed_checks += results.get("passed", 0)
        
        if total_checks > 0:
            validation_results["compliance_score"] = passed_checks / total_checks
        
        return validation_results
    
    def _categorize_errors(self, errors: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
        """Categorize mypy errors for systematic fixing."""
        categories = defaultdict(list)
        
        for error in errors:
            message = error['message']
            
            if "Function is missing" in message:
                categories["missing_type_annotations"].append(error)
            elif "has no attribute" in message:
                categories["attribute_access_errors"].append(error)
            elif "Incompatible types" in message:
                categories["type_mismatches"].append(error)
            elif "Returning Any" in message:
                categories["return_type_issues"].append(error)
            elif "Statement is unreachable" in message:
                categories["unreachable_code"].append(error)
            elif "union-attr" in error.get('code', ''):
                categories["union_attribute_access"].append(error)
            else:
                categories["other"].append(error)
        
        return dict(categories)
    
    def _generate_recommendations(self, mypy_errors, schema_issues, protocol_issues, unused_code) -> List[str]:
        """Generate actionable recommendations."""
        recommendations = []
        
        if len(mypy_errors) > 50:
            recommendations.append("High number of type errors detected. Consider running systematic fixing.")
        
        if len(schema_issues) > 0:
            recommendations.append("Schema compliance issues found. Update code to use current v1 schemas.")
        
        if len(protocol_issues) > 0:
            recommendations.append("Protocol violations detected. Refactor to use protocol interfaces only.")
        
        if len(unused_code) > 10:
            recommendations.append("Significant unused code detected. Consider cleanup to improve maintainability.")
        
        return recommendations
    
    def _check_adapter_types(self, adapter_path: Path) -> Dict[str, Any]:
        """Check type safety of an adapter."""
        # Run mypy specifically on this adapter
        cmd = f"python -m mypy {adapter_path} --ignore-missing-imports --show-error-codes"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        
        errors = []
        for line in result.stderr.splitlines():
            if "error:" in line:
                errors.append(line.strip())
        
        return {
            "total_errors": len(errors),
            "errors": errors,
            "type_safe": len(errors) == 0
        }
    
    def generate_compliance_report(self, output_file: Optional[str] = None) -> str:
        """Generate a comprehensive compliance report."""
        analysis = self.analyze_compliance()
        
        report_lines = [
            "# CIRIS Codebase Compliance Report",
            "=" * 50,
            "",
            f"## MyPy Type Safety",
            f"Total Errors: {analysis['total_mypy_errors']}",
            ""
        ]
        
        # Add error category breakdown
        for category, errors in analysis['error_categories'].items():
            report_lines.append(f"- {category}: {len(errors)} errors")
        
        report_lines.extend([
            "",
            f"## Schema Compliance",
            f"Issues Found: {analysis['schema_compliance']['total_issues']}",
            "",
            f"## Protocol Compliance", 
            f"Issues Found: {analysis['protocol_compliance']['total_issues']}",
            "",
            f"## Code Quality",
            f"Unused Code Items: {analysis['unused_code']['total_items']}",
            "",
            "## Recommendations"
        ])
        
        for rec in analysis['recommendations']:
            report_lines.append(f"- {rec}")
        
        report_content = "\n".join(report_lines)
        
        if output_file:
            with open(output_file, 'w') as f:
                f.write(report_content)
            logger.info(f"Compliance report written to {output_file}")
        
        return report_content