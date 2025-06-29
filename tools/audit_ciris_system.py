#!/usr/bin/env python3
"""
CIRIS Complete System Auditor

This tool performs a comprehensive audit of the entire CIRIS codebase to:
1. Categorize every file into its proper category
2. Identify duplicates and conflicts
3. Verify inheritance chains
4. Find orphaned code
5. Check protocol compliance
"""
import ast
import os
import json
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple, Any
from collections import defaultdict
import re

class CIRISSystemAuditor:
    """Complete system auditor for CIRIS codebase."""
    
    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root)
        self.ciris_root = self.project_root / "ciris_engine"
        
        # Component categories
        self.categories = {
            "services_bussed": {
                "communication": [],
                "memory": [],
                "tool": [],
                "audit": [],
                "telemetry": [],
                "llm": [],
                "secrets": [],
                "runtime_control": [],
                "wise_authority": []
            },
            "services_unbussed": {
                "configuration": [],
                "filter": [],
                "utility": [],
                "monitoring": []
            },
            "adapters": {
                "platform": [],
                "communication": []
            },
            "processors": {
                "main": [],
                "task": [],
                "specialized": []
            },
            "handlers": {
                "external_actions": [],
                "control_actions": [],
                "memory_actions": [],
                "terminal_actions": []
            },
            "dmas": {
                "ethical": [],
                "common_sense": [],
                "domain_specific": [],
                "action_selection": []
            },
            "faculties": {
                "cognitive": []
            },
            "guardrails": {
                "input": [],
                "output": [],
                "process": []
            },
            "runtime": {
                "core": [],
                "initialization": [],
                "management": []
            },
            "infrastructure": {
                "buses": [],
                "registry": [],
                "persistence": [],
                "schemas": [],
                "utilities": []
            },
            "uncategorized": []
        }
        
        # Track all findings
        self.findings = {
            "duplicate_functionality": [],
            "missing_protocols": [],
            "incorrect_inheritance": [],
            "orphaned_code": [],
            "misplaced_files": [],
            "protocol_mismatches": [],
            "untyped_usage": []
        }
        
        # Class information
        self.all_classes = {}
        self.inheritance_map = {}
        self.protocol_map = {}
        self.import_map = defaultdict(set)
        
    def audit(self) -> Dict[str, Any]:
        """Run complete system audit."""
        print("🔍 Starting CIRIS Complete System Audit...\n")
        
        # Phase 1: Scan all Python files
        self._scan_all_files()
        
        # Phase 2: Categorize components
        self._categorize_components()
        
        # Phase 3: Check inheritance
        self._check_inheritance_chains()
        
        # Phase 4: Find duplicates
        self._find_duplicates()
        
        # Phase 5: Check protocol compliance
        self._check_protocol_compliance()
        
        # Phase 6: Find orphaned code
        self._find_orphaned_code()
        
        # Phase 7: Generate report
        return self._generate_report()
    
    def _scan_all_files(self):
        """Scan all Python files and extract class information."""
        print("📂 Scanning all Python files...")
        
        for file_path in self.ciris_root.rglob("*.py"):
            if file_path.name.startswith("_") or "test" in str(file_path):
                continue
                
            try:
                content = file_path.read_text()
                tree = ast.parse(content)
                
                # Extract classes
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef):
                        class_info = {
                            "name": node.name,
                            "file": str(file_path.relative_to(self.project_root)),
                            "line": node.lineno,
                            "bases": [],
                            "methods": [],
                            "is_protocol": False,
                            "is_abstract": False,
                            "decorators": [],
                            "docstring": ast.get_docstring(node) or ""
                        }
                        
                        # Get base classes
                        for base in node.bases:
                            if isinstance(base, ast.Name):
                                class_info["bases"].append(base.id)
                                if "Protocol" in base.id:
                                    class_info["is_protocol"] = True
                            elif isinstance(base, ast.Attribute):
                                class_info["bases"].append(base.attr)
                        
                        # Get methods
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                method_info = {
                                    "name": item.name,
                                    "is_async": isinstance(item, ast.AsyncFunctionDef),
                                    "is_abstract": any(isinstance(d, ast.Name) and d.id == "abstractmethod" 
                                                     for d in item.decorator_list),
                                    "is_private": item.name.startswith("_"),
                                    "line": item.lineno
                                }
                                class_info["methods"].append(method_info)
                        
                        # Check decorators
                        class_info["decorators"] = [d.id if isinstance(d, ast.Name) else str(d) 
                                                   for d in node.decorator_list]
                        
                        self.all_classes[node.name] = class_info
                        
                    # Track imports
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            self.import_map[str(file_path)].add(alias.name)
                    elif isinstance(node, ast.ImportFrom):
                        if node.module:
                            self.import_map[str(file_path)].add(node.module)
                            
            except Exception as e:
                print(f"  ⚠️  Error scanning {file_path}: {e}")
        
        print(f"  ✓ Found {len(self.all_classes)} classes")
    
    def _categorize_components(self):
        """Categorize each component into its proper category."""
        print("\n📊 Categorizing components...")
        
        for class_name, class_info in self.all_classes.items():
            file_path = class_info["file"]
            categorized = False
            
            # Skip test and private classes
            if "test" in file_path.lower() or class_name.startswith("_"):
                continue
            
            # Categorize based on name and location patterns
            
            # Services (Bussed)
            if "Service" in class_name and any(base in ["Service", "BaseService"] for base in class_info["bases"]):
                if "memory" in file_path.lower() or "Memory" in class_name:
                    self.categories["services_bussed"]["memory"].append(class_name)
                elif "telemetry" in file_path.lower() or "Telemetry" in class_name:
                    self.categories["services_bussed"]["telemetry"].append(class_name)
                elif "audit" in file_path.lower() or "Audit" in class_name:
                    self.categories["services_bussed"]["audit"].append(class_name)
                elif "secret" in file_path.lower() or "Secret" in class_name:
                    self.categories["services_bussed"]["secrets"].append(class_name)
                elif "llm" in file_path.lower() or "LLM" in class_name:
                    self.categories["services_bussed"]["llm"].append(class_name)
                elif "tool" in file_path.lower() or "Tool" in class_name:
                    self.categories["services_bussed"]["tool"].append(class_name)
                elif "runtime" in file_path.lower() or "RuntimeControl" in class_name:
                    self.categories["services_bussed"]["runtime_control"].append(class_name)
                elif "wa" in file_path.lower() or "WA" in class_name or "WiseAuthority" in class_name:
                    self.categories["services_bussed"]["wise_authority"].append(class_name)
                else:
                    # Check if it's unbussed
                    if "config" in class_name.lower() or "configuration" in file_path.lower():
                        self.categories["services_unbussed"]["configuration"].append(class_name)
                    elif "filter" in class_name.lower():
                        self.categories["services_unbussed"]["filter"].append(class_name)
                    elif "monitor" in class_name.lower():
                        self.categories["services_unbussed"]["monitoring"].append(class_name)
                    else:
                        self.categories["services_unbussed"]["utility"].append(class_name)
                categorized = True
                
            # Adapters
            elif "Adapter" in class_name or "adapter" in file_path:
                if any(x in file_path for x in ["api", "cli", "discord"]):
                    self.categories["adapters"]["platform"].append(class_name)
                else:
                    self.categories["adapters"]["communication"].append(class_name)
                categorized = True
                
            # Processors
            elif "Processor" in class_name or "processor" in file_path:
                if "Main" in class_name or "Agent" in class_name:
                    self.categories["processors"]["main"].append(class_name)
                elif "Task" in class_name:
                    self.categories["processors"]["task"].append(class_name)
                else:
                    self.categories["processors"]["specialized"].append(class_name)
                categorized = True
                
            # Handlers
            elif "Handler" in class_name or "handler" in file_path:
                if any(x in class_name for x in ["Speak", "Tool", "Observe"]):
                    self.categories["handlers"]["external_actions"].append(class_name)
                elif any(x in class_name for x in ["Ponder", "Defer", "Reject"]):
                    self.categories["handlers"]["control_actions"].append(class_name)
                elif any(x in class_name for x in ["Memorize", "Recall", "Forget"]):
                    self.categories["handlers"]["memory_actions"].append(class_name)
                elif "TaskComplete" in class_name:
                    self.categories["handlers"]["terminal_actions"].append(class_name)
                else:
                    self.categories["handlers"]["external_actions"].append(class_name)
                categorized = True
                
            # DMAs
            elif "DMA" in class_name or "dma" in file_path:
                if "Ethical" in class_name or "PDMA" in class_name:
                    self.categories["dmas"]["ethical"].append(class_name)
                elif "CSDMA" in class_name:
                    self.categories["dmas"]["common_sense"].append(class_name)
                elif "DSDMA" in class_name:
                    self.categories["dmas"]["domain_specific"].append(class_name)
                elif "ActionSelection" in class_name:
                    self.categories["dmas"]["action_selection"].append(class_name)
                else:
                    self.categories["dmas"]["ethical"].append(class_name)
                categorized = True
                
            # Faculties
            elif "Faculty" in class_name or "faculty" in file_path:
                self.categories["faculties"]["cognitive"].append(class_name)
                categorized = True
                
            # Guardrails
            elif "Guardrail" in class_name or "guardrail" in file_path:
                self.categories["guardrails"]["process"].append(class_name)
                categorized = True
                
            # Runtime
            elif "runtime" in file_path:
                if "Runtime" in class_name and not "Control" in class_name:
                    self.categories["runtime"]["core"].append(class_name)
                elif "Initializer" in class_name:
                    self.categories["runtime"]["initialization"].append(class_name)
                else:
                    self.categories["runtime"]["management"].append(class_name)
                categorized = True
                
            # Infrastructure
            elif "Bus" in class_name or "bus" in file_path:
                self.categories["infrastructure"]["buses"].append(class_name)
                categorized = True
            elif "Registry" in class_name or "registry" in file_path:
                self.categories["infrastructure"]["registry"].append(class_name)
                categorized = True
            elif "persistence" in file_path or "Persistence" in class_name:
                self.categories["infrastructure"]["persistence"].append(class_name)
                categorized = True
            elif "schema" in file_path and (class_info["bases"] and any("Model" in b for b in class_info["bases"])):
                self.categories["infrastructure"]["schemas"].append(class_name)
                categorized = True
            elif "utils" in file_path or "utility" in file_path:
                self.categories["infrastructure"]["utilities"].append(class_name)
                categorized = True
                
            # Protocols
            elif class_info["is_protocol"]:
                # Protocols are metadata, not components
                self.protocol_map[class_name] = class_info
                categorized = True
                
            # Uncategorized
            if not categorized:
                self.categories["uncategorized"].append(class_name)
    
    def _check_inheritance_chains(self):
        """Verify inheritance chains are correct."""
        print("\n🔗 Checking inheritance chains...")
        
        # Expected inheritance patterns
        expected_patterns = {
            "Service": ["BaseService", "Service"],
            "Handler": ["BaseHandler"],
            "DMA": ["BaseDMA"],
            "Adapter": ["BaseAdapter", "PlatformAdapter"],
            "Processor": ["BaseProcessor"]
        }
        
        for class_name, class_info in self.all_classes.items():
            if class_info["is_protocol"]:
                continue
                
            # Check if inheritance matches expected patterns
            bases = class_info["bases"]
            category = self._get_component_category(class_name)
            
            if category:
                expected_bases = expected_patterns.get(category.split("_")[0].title(), [])
                if expected_bases and not any(base in bases for base in expected_bases):
                    self.findings["incorrect_inheritance"].append({
                        "class": class_name,
                        "file": class_info["file"],
                        "bases": bases,
                        "expected": expected_bases,
                        "category": category
                    })
    
    def _find_duplicates(self):
        """Find duplicate functionality."""
        print("\n🔍 Finding duplicate functionality...")
        
        # Group by similar names
        name_groups = defaultdict(list)
        for class_name in self.all_classes:
            # Normalize name for comparison
            normalized = class_name.lower().replace("_", "").replace("-", "")
            name_groups[normalized].append(class_name)
        
        # Find potential duplicates
        for normalized, classes in name_groups.items():
            if len(classes) > 1:
                # Check if they have similar methods
                method_sets = []
                for class_name in classes:
                    methods = set(m["name"] for m in self.all_classes[class_name]["methods"] 
                                if not m["is_private"])
                    method_sets.append(methods)
                
                # Calculate similarity
                if len(method_sets) >= 2:
                    intersection = method_sets[0]
                    for ms in method_sets[1:]:
                        intersection = intersection.intersection(ms)
                    
                    if len(intersection) > 2:  # Significant overlap
                        self.findings["duplicate_functionality"].append({
                            "classes": classes,
                            "shared_methods": list(intersection),
                            "similarity": len(intersection)
                        })
    
    def _check_protocol_compliance(self):
        """Check if modules comply with their protocols."""
        print("\n📋 Checking protocol compliance...")
        
        # Match protocols to implementations
        for protocol_name, protocol_info in self.protocol_map.items():
            # Find potential implementations
            base_name = protocol_name.replace("Protocol", "").replace("Interface", "")
            
            # Look for implementations
            implementations = []
            for class_name, class_info in self.all_classes.items():
                if (base_name in class_name or 
                    protocol_name in class_info["bases"] or
                    any(base_name in base for base in class_info["bases"])):
                    implementations.append(class_name)
            
            if not implementations:
                self.findings["missing_protocols"].append({
                    "protocol": protocol_name,
                    "file": protocol_info["file"],
                    "methods": [m["name"] for m in protocol_info["methods"]]
                })
            else:
                # Check method compliance
                protocol_methods = set(m["name"] for m in protocol_info["methods"])
                
                for impl_name in implementations:
                    impl_info = self.all_classes.get(impl_name)
                    if impl_info:
                        impl_methods = set(m["name"] for m in impl_info["methods"] 
                                         if not m["is_private"])
                        
                        missing = protocol_methods - impl_methods
                        extra = impl_methods - protocol_methods
                        
                        if missing or extra:
                            self.findings["protocol_mismatches"].append({
                                "protocol": protocol_name,
                                "implementation": impl_name,
                                "missing_methods": list(missing),
                                "extra_methods": list(extra)
                            })
    
    def _find_orphaned_code(self):
        """Find code that isn't used anywhere."""
        print("\n🗑️  Finding orphaned code...")
        
        # Build usage map
        used_classes = set()
        
        for file_path, imports in self.import_map.items():
            # Parse imports to find used classes
            for imp in imports:
                if "ciris_engine" in imp:
                    # Extract potential class names from import
                    parts = imp.split(".")
                    if parts:
                        used_classes.add(parts[-1])
        
        # Check which classes are never imported
        for class_name, class_info in self.all_classes.items():
            if (class_name not in used_classes and 
                not class_info["is_protocol"] and
                class_name not in ["CIRISRuntime", "main"]):  # Entry points
                
                self.findings["orphaned_code"].append({
                    "class": class_name,
                    "file": class_info["file"],
                    "line": class_info["line"]
                })
    
    def _get_component_category(self, class_name: str) -> Optional[str]:
        """Get the category for a component."""
        for cat, subcats in self.categories.items():
            if isinstance(subcats, dict):
                for subcat, items in subcats.items():
                    if class_name in items:
                        return f"{cat}_{subcat}"
            elif class_name in subcats:
                return cat
        return None
    
    def _generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive audit report."""
        print("\n📊 Generating audit report...")
        
        # Count totals
        total_categorized = sum(
            len(subcat) if isinstance(subcat, list) else 
            sum(len(v) for v in subcat.values())
            for subcat in self.categories.values()
        )
        
        report = {
            "summary": {
                "total_classes": len(self.all_classes),
                "total_protocols": len(self.protocol_map),
                "categorized": total_categorized - len(self.categories["uncategorized"]),
                "uncategorized": len(self.categories["uncategorized"]),
                "duplicate_groups": len(self.findings["duplicate_functionality"]),
                "missing_implementations": len(self.findings["missing_protocols"]),
                "incorrect_inheritance": len(self.findings["incorrect_inheritance"]),
                "protocol_mismatches": len(self.findings["protocol_mismatches"]),
                "orphaned_classes": len(self.findings["orphaned_code"])
            },
            "categories": self.categories,
            "findings": self.findings,
            "all_classes": self.all_classes,
            "protocol_map": self.protocol_map
        }
        
        # Print summary
        print("\n" + "="*60)
        print("🔍 CIRIS System Audit Summary")
        print("="*60)
        print(f"\n📊 Component Distribution:")
        print(f"   Total Classes: {report['summary']['total_classes']}")
        print(f"   Total Protocols: {report['summary']['total_protocols']}")
        print(f"   ✅ Categorized: {report['summary']['categorized']}")
        print(f"   ❓ Uncategorized: {report['summary']['uncategorized']}")
        
        print(f"\n⚠️  Issues Found:")
        print(f"   Duplicate Functionality Groups: {report['summary']['duplicate_groups']}")
        print(f"   Missing Protocol Implementations: {report['summary']['missing_implementations']}")
        print(f"   Incorrect Inheritance: {report['summary']['incorrect_inheritance']}")
        print(f"   Protocol Mismatches: {report['summary']['protocol_mismatches']}")
        print(f"   Orphaned Classes: {report['summary']['orphaned_classes']}")
        
        print(f"\n📁 Category Breakdown:")
        for cat, subcats in self.categories.items():
            if cat == "uncategorized":
                continue
            if isinstance(subcats, dict):
                total = sum(len(v) for v in subcats.values())
                print(f"   {cat}: {total}")
                for subcat, items in subcats.items():
                    if items:
                        print(f"      - {subcat}: {len(items)}")
        
        return report
    
    def save_report(self, filename: str = "ciris_audit_report.json"):
        """Save the audit report to a file."""
        report = self.audit()
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)
        print(f"\n💾 Detailed report saved to {filename}")
        
        # Also save a markdown summary
        self._save_markdown_summary(report, filename.replace(".json", ".md"))
    
    def _save_markdown_summary(self, report: Dict[str, Any], filename: str):
        """Save a human-readable markdown summary."""
        with open(filename, "w") as f:
            f.write("# CIRIS System Audit Report\n\n")
            
            # Summary
            f.write("## Summary\n\n")
            for key, value in report["summary"].items():
                f.write(f"- **{key.replace('_', ' ').title()}**: {value}\n")
            
            # Issues
            f.write("\n## Critical Issues\n\n")
            
            if report["findings"]["duplicate_functionality"]:
                f.write("### Duplicate Functionality\n\n")
                for dup in report["findings"]["duplicate_functionality"]:
                    f.write(f"- Classes: {', '.join(dup['classes'])}\n")
                    f.write(f"  - Shared methods: {', '.join(dup['shared_methods'][:5])}\n")
            
            if report["findings"]["missing_protocols"]:
                f.write("\n### Missing Protocol Implementations\n\n")
                for miss in report["findings"]["missing_protocols"][:10]:
                    f.write(f"- **{miss['protocol']}**\n")
                    f.write(f"  - Required methods: {', '.join(miss['methods'][:5])}\n")
            
            if report["findings"]["incorrect_inheritance"]:
                f.write("\n### Incorrect Inheritance\n\n")
                for inc in report["findings"]["incorrect_inheritance"][:10]:
                    f.write(f"- **{inc['class']}**\n")
                    f.write(f"  - Current bases: {', '.join(inc['bases'])}\n")
                    f.write(f"  - Expected: {', '.join(inc['expected'])}\n")
            
            # Component listing
            f.write("\n## Component Categorization\n\n")
            for cat, subcats in report["categories"].items():
                if cat == "uncategorized":
                    continue
                if isinstance(subcats, dict):
                    for subcat, items in subcats.items():
                        if items:
                            f.write(f"\n### {cat.replace('_', ' ').title()} - {subcat.replace('_', ' ').title()}\n\n")
                            for item in items[:10]:
                                class_info = report["all_classes"].get(item, {})
                                f.write(f"- **{item}** ({class_info.get('file', 'unknown')})\n")
            
            # Uncategorized
            if report["categories"]["uncategorized"]:
                f.write("\n### ❓ Uncategorized Components\n\n")
                for item in report["categories"]["uncategorized"][:20]:
                    class_info = report["all_classes"].get(item, {})
                    f.write(f"- **{item}** ({class_info.get('file', 'unknown')})\n")
        
        print(f"📝 Markdown summary saved to {filename}")


if __name__ == "__main__":
    auditor = CIRISSystemAuditor()
    auditor.save_report()
