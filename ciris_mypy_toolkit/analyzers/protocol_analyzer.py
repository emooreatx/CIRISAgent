"""
Protocol Analyzer - Ensures code uses protocol interfaces instead of internal methods
"""

import ast
import re
from pathlib import Path
from typing import Dict, List, Any, Set
import logging

logger = logging.getLogger(__name__)


class ProtocolAnalyzer:
    """
    Analyzes CIRIS code to ensure it uses protocol interfaces instead of internal methods.
    
    Key analysis:
    - Direct internal method calls vs protocol interface usage
    - Proper service registry usage
    - Protocol interface implementations
    - Adapter compliance with protocols
    """
    
    def __init__(self, target_dir: Path):
        self.target_dir = Path(target_dir)
        self.protocol_interfaces = self._discover_protocols()
        self.service_patterns = self._load_service_patterns()
        
    def _discover_protocols(self) -> Dict[str, Set[str]]:
        """Discover all protocol interfaces defined in the protocols directory."""
        protocols = {}
        protocols_dir = self.target_dir / "protocols"
        
        if not protocols_dir.exists():
            return protocols
        
        for protocol_file in protocols_dir.glob("*.py"):
            try:
                with open(protocol_file, 'r') as f:
                    content = f.read()
                
                tree = ast.parse(content)
                protocol_methods = set()
                
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        # Check if it's a protocol (has @protocol decorator or inherits from Protocol)
                        is_protocol = any(
                            (isinstance(decorator, ast.Name) and decorator.id == 'protocol') or
                            (isinstance(base, ast.Name) and 'Protocol' in base.id)
                            for decorator in node.decorator_list
                            for base in node.bases
                        )
                        
                        if is_protocol:
                            for class_node in node.body:
                                if isinstance(class_node, ast.FunctionDef):
                                    protocol_methods.add(class_node.name)
                
                if protocol_methods:
                    protocols[protocol_file.stem] = protocol_methods
                    
            except Exception as e:
                logger.warning(f"Could not parse protocol {protocol_file}: {e}")
        
        return protocols
    
    def _load_service_patterns(self) -> List[Dict[str, str]]:
        """Load patterns that indicate improper service usage."""
        return [
            {
                "pattern": r"\.get_db_connection\(",
                "issue": "Direct database connection access",
                "protocol": "PersistenceInterface",
                "fix": "Use persistence service methods"
            },
            {
                "pattern": r"sqlite3\.",
                "issue": "Direct SQLite usage",
                "protocol": "PersistenceInterface", 
                "fix": "Use persistence interface methods"
            },
            {
                "pattern": r"\._\w+\(",
                "issue": "Private method access",
                "protocol": "ServiceInterface",
                "fix": "Use public service interface methods"
            },
            {
                "pattern": r"\.execute\(",
                "issue": "Direct SQL execution",
                "protocol": "PersistenceInterface",
                "fix": "Use persistence service query methods"
            },
            {
                "pattern": r"openai\.Client\(",
                "issue": "Direct OpenAI client instantiation",
                "protocol": "LLMInterface",
                "fix": "Use LLM service from registry"
            },
            {
                "pattern": r"discord\.Client\(",
                "issue": "Direct Discord client instantiation", 
                "protocol": "CommunicationInterface",
                "fix": "Use communication service from registry"
            }
        ]
    
    def analyze_protocol_usage(self) -> List[Dict[str, Any]]:
        """Analyze protocol usage across the entire codebase."""
        all_issues = []
        
        for py_file in self.target_dir.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
                
            file_issues = self.analyze_file_protocols(py_file)
            all_issues.extend(file_issues)
        
        return all_issues
    
    def analyze_file_protocols(self, file_path: Path) -> List[Dict[str, Any]]:
        """Analyze protocol usage in a specific file."""
        if not file_path.exists():
            return []
        
        try:
            with open(file_path, 'r') as f:
                content = f.read()
            
            issues = []
            
            # Check for service pattern violations
            for pattern_info in self.service_patterns:
                matches = re.finditer(pattern_info["pattern"], content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    issues.append({
                        "file": str(file_path),
                        "line": line_num,
                        "issue": pattern_info["issue"],
                        "pattern": match.group(),
                        "recommended_protocol": pattern_info["protocol"],
                        "fix_suggestion": pattern_info["fix"]
                    })
            
            # Check for proper service registry usage
            registry_issues = self._check_service_registry_usage(content, file_path)
            issues.extend(registry_issues)
            
            # Check for protocol implementation compliance
            impl_issues = self._check_protocol_implementations(content, file_path)
            issues.extend(impl_issues)
            
            return issues
            
        except Exception as e:
            logger.warning(f"Could not analyze {file_path}: {e}")
            return []
    
    def _check_service_registry_usage(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Check if file properly uses service registry for service access."""
        issues = []
        
        # If file imports services but doesn't use registry
        has_service_imports = bool(re.search(r"from.*adapters.*import", content))
        has_registry_usage = bool(re.search(r"service_registry\.|ServiceRegistry", content))
        
        if has_service_imports and not has_registry_usage and "registry" not in str(file_path):
            issues.append({
                "file": str(file_path),
                "line": 1,
                "issue": "Imports services but doesn't use service registry",
                "pattern": "Direct service imports",
                "recommended_protocol": "ServiceRegistry",
                "fix_suggestion": "Access services through service registry"
            })
        
        # Check for hardcoded service instantiation
        instantiation_patterns = [
            r"LocalGraphMemoryService\(",
            r"LocalAuditLog\(",
            r"OpenAICompatibleLLM\(",
            r"DiscordAdapter\("
        ]
        
        for pattern in instantiation_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                line_num = content[:match.start()].count('\n') + 1
                issues.append({
                    "file": str(file_path),
                    "line": line_num,
                    "issue": "Hardcoded service instantiation",
                    "pattern": match.group(),
                    "recommended_protocol": "ServiceRegistry",
                    "fix_suggestion": "Get service from registry instead"
                })
        
        return issues
    
    def _check_protocol_implementations(self, content: str, file_path: Path) -> List[Dict[str, Any]]:
        """Check if classes properly implement required protocols."""
        issues = []
        
        try:
            tree = ast.parse(content)
            
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Check if class should implement protocol based on naming
                    class_name = node.name
                    
                    if any(suffix in class_name for suffix in ["Adapter", "Service", "Handler"]):
                        # Check if it inherits from appropriate base class
                        base_names = [base.id for base in node.bases if isinstance(base, ast.Name)]
                        
                        expected_base = None
                        if "Adapter" in class_name:
                            expected_base = "BaseAdapter"
                        elif "Service" in class_name:
                            expected_base = "Service" 
                        elif "Handler" in class_name:
                            expected_base = "BaseHandler"
                        
                        if expected_base and expected_base not in base_names:
                            issues.append({
                                "file": str(file_path),
                                "line": node.lineno,
                                "issue": f"Class '{class_name}' should inherit from {expected_base}",
                                "pattern": f"class {class_name}",
                                "recommended_protocol": expected_base,
                                "fix_suggestion": f"Inherit from {expected_base} to ensure protocol compliance"
                            })
        
        except SyntaxError:
            # Skip files with syntax errors
            pass
        
        return issues
    
    def validate_adapter(self, adapter_path: Path) -> Dict[str, Any]:
        """Validate a specific adapter for protocol compliance."""
        if not adapter_path.exists():
            return {"error": f"Adapter {adapter_path} does not exist"}
        
        issues = self.analyze_file_protocols(adapter_path)
        
        # Additional adapter-specific checks
        adapter_issues = self._check_adapter_specific_patterns(adapter_path)
        issues.extend(adapter_issues)
        
        return {
            "adapter": str(adapter_path),
            "total_issues": len(issues),
            "issues": issues,
            "protocol_compliant": len(issues) == 0,
            "recommendations": self._generate_adapter_recommendations(issues)
        }
    
    def _check_adapter_specific_patterns(self, adapter_path: Path) -> List[Dict[str, Any]]:
        """Check adapter-specific protocol compliance patterns."""
        issues = []
        
        try:
            with open(adapter_path, 'r') as f:
                content = f.read()
            
            # Adapters should not directly access internal implementation details
            problematic_patterns = [
                (r"from ciris_engine\.persistence\.db", "Adapter accessing internal persistence implementation"),
                (r"from ciris_engine\.adapters\..*\._", "Adapter accessing private internal methods"),
                (r"\.db_path", "Adapter directly accessing database path"),
                (r"conn\.execute", "Adapter executing raw SQL")
            ]
            
            for pattern, issue_desc in problematic_patterns:
                matches = re.finditer(pattern, content)
                for match in matches:
                    line_num = content[:match.start()].count('\n') + 1
                    issues.append({
                        "file": str(adapter_path),
                        "line": line_num,
                        "issue": issue_desc,
                        "pattern": match.group(),
                        "fix_suggestion": "Use protocol interface instead of internal implementation"
                    })
        
        except Exception as e:
            logger.warning(f"Could not check adapter patterns for {adapter_path}: {e}")
        
        return issues
    
    def _generate_adapter_recommendations(self, issues: List[Dict[str, Any]]) -> List[str]:
        """Generate specific recommendations for adapter compliance."""
        recommendations = []
        
        issue_types = set(issue["issue"] for issue in issues)
        
        if any("Direct database" in issue_type for issue_type in issue_types):
            recommendations.append("Use PersistenceInterface instead of direct database access")
        
        if any("Private method" in issue_type for issue_type in issue_types):
            recommendations.append("Access services through public protocol interfaces only")
        
        if any("service registry" in issue_type for issue_type in issue_types):
            recommendations.append("Obtain services from ServiceRegistry rather than direct instantiation")
        
        if any("protocol compliance" in issue_type for issue_type in issue_types):
            recommendations.append("Ensure adapter inherits from BaseAdapter and implements required methods")
        
        return recommendations
    
    def generate_protocol_report(self) -> Dict[str, Any]:
        """Generate comprehensive protocol usage report."""
        all_issues = self.analyze_protocol_usage()
        
        issue_categories = {}
        for issue in all_issues:
            category = issue.get("recommended_protocol", "Unknown")
            if category not in issue_categories:
                issue_categories[category] = []
            issue_categories[category].append(issue)
        
        return {
            "total_protocol_violations": len(all_issues),
            "violations_by_protocol": {
                category: len(issues) for category, issues in issue_categories.items()
            },
            "most_violated_protocols": sorted(
                issue_categories.items(), 
                key=lambda x: len(x[1]), 
                reverse=True
            )[:5],
            "detailed_issues": all_issues
        }