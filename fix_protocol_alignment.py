#!/usr/bin/env python3
"""
Fix protocol alignment issues in CIRIS codebase.

This script identifies and fixes mismatches between protocols and implementations.
"""

import ast
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional

class ProtocolAlignmentFixer:
    def __init__(self):
        self.project_root = Path("ciris_engine")
        self.protocols_path = self.project_root / "protocols"
        self.issues_found = []
        self.fixes_proposed = []
        
    def analyze_telemetry_service(self):
        """Analyze TelemetryService specifically for handler_name issue."""
        print("\n=== Analyzing TelemetryService Protocol Alignment ===\n")
        
        # Find protocol
        protocol_path = self.protocols_path / "services" / "graph" / "telemetry.py"
        impl_path = self.project_root / "logic" / "services" / "graph" / "telemetry_service.py"
        
        # Parse protocol
        protocol_methods = self._parse_protocol(protocol_path)
        impl_methods = self._parse_implementation(impl_path)
        
        # Compare record_metric specifically
        if "record_metric" in protocol_methods and "record_metric" in impl_methods:
            proto_sig = protocol_methods["record_metric"]
            impl_sig = impl_methods["record_metric"]
            
            print("Protocol record_metric signature:")
            print(f"  Parameters: {proto_sig['params']}")
            print(f"  Return: {proto_sig['return_type']}")
            
            print("\nImplementation record_metric signature:")
            print(f"  Parameters: {impl_sig['params']}")
            print(f"  Return: {impl_sig['return_type']}")
            
            # Check for handler_name parameter
            proto_params = {p['name'] for p in proto_sig['params']}
            impl_params = {p['name'] for p in impl_sig['params']}
            
            missing_in_protocol = impl_params - proto_params
            if missing_in_protocol:
                print(f"\n❌ Parameters in implementation but not in protocol: {missing_in_protocol}")
                self._propose_protocol_fix(protocol_path, "record_metric", impl_sig)
            else:
                print("\n✅ Parameters match!")
                
    def _parse_protocol(self, path: Path) -> Dict[str, Dict]:
        """Parse protocol file and extract method signatures."""
        methods = {}
        
        if not path.exists():
            return methods
            
        tree = ast.parse(path.read_text())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Protocol" in node.name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        methods[item.name] = self._extract_signature(item)
                        
        return methods
        
    def _parse_implementation(self, path: Path) -> Dict[str, Dict]:
        """Parse implementation file and extract method signatures."""
        methods = {}
        
        if not path.exists():
            return methods
            
        tree = ast.parse(path.read_text())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and "Service" in node.name:
                for item in node.body:
                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        if not item.name.startswith('_'):  # Public methods only
                            methods[item.name] = self._extract_signature(item)
                            
        return methods
        
    def _extract_signature(self, node: ast.FunctionDef) -> Dict:
        """Extract method signature details."""
        sig = {
            "is_async": isinstance(node, ast.AsyncFunctionDef),
            "params": [],
            "return_type": "Any"  # Default
        }
        
        # Extract parameters
        for i, arg in enumerate(node.args.args):
            param = {"name": arg.arg, "type": "Any", "default": None}
            
            # Get type annotation
            if arg.annotation:
                param["type"] = self._ast_to_string(arg.annotation)
            
            # Get default value
            default_offset = len(node.args.args) - len(node.args.defaults)
            if i >= default_offset:
                default_idx = i - default_offset
                if default_idx < len(node.args.defaults):
                    param["default"] = self._ast_to_string(node.args.defaults[default_idx])
            
            sig["params"].append(param)
        
        # Get return type
        if node.returns:
            sig["return_type"] = self._ast_to_string(node.returns)
        
        return sig
        
    def _ast_to_string(self, node) -> str:
        """Convert AST node to string representation."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Constant):
            return repr(node.value)
        elif isinstance(node, ast.Attribute):
            return f"{self._ast_to_string(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript):
            return f"{self._ast_to_string(node.value)}[{self._ast_to_string(node.slice)}]"
        elif isinstance(node, ast.Index):
            return self._ast_to_string(node.value)
        elif isinstance(node, ast.Tuple):
            return f"({', '.join(self._ast_to_string(e) for e in node.elts)})"
        else:
            return "Any"
            
    def _propose_protocol_fix(self, protocol_path: Path, method_name: str, impl_sig: Dict):
        """Propose a fix for the protocol."""
        print(f"\n📝 Proposed fix for {protocol_path}:")
        print(f"\nUpdate {method_name} in protocol to match implementation:")
        
        # Build method signature
        params = []
        for param in impl_sig['params']:
            p = param['name']
            if param['type'] != 'Any':
                p += f": {param['type']}"
            if param['default']:
                p += f" = {param['default']}"
            params.append(p)
            
        async_prefix = "async " if impl_sig['is_async'] else ""
        return_type = f" -> {impl_sig['return_type']}" if impl_sig['return_type'] else ""
        
        print(f"\n    @abstractmethod")
        print(f"    {async_prefix}def {method_name}({', '.join(params)}){return_type}:")
        print(f'        """Record a telemetry metric."""')
        print(f"        ...")
        
    def check_all_protocols(self):
        """Check all protocol alignments."""
        print("\n=== Checking All Protocol Alignments ===\n")
        
        # Known protocol-implementation mappings
        mappings = {
            "TelemetryServiceProtocol": ("services/graph/telemetry.py", "logic/services/graph/telemetry_service.py"),
            "AuditServiceProtocol": ("services/graph/audit.py", "logic/services/graph/audit_service.py"),
            "TimeServiceProtocol": ("services/lifecycle/time.py", "logic/services/lifecycle/time_service.py"),
            "ShutdownServiceProtocol": ("services/lifecycle/shutdown.py", "logic/services/lifecycle/shutdown_service.py"),
            "RuntimeControlServiceProtocol": ("services/runtime/runtime_control.py", "logic/services/runtime/runtime_control_service.py"),
        }
        
        misaligned = []
        
        for protocol_name, (proto_path, impl_path) in mappings.items():
            proto_full = self.protocols_path / proto_path
            impl_full = self.project_root / impl_path
            
            if proto_full.exists() and impl_full.exists():
                proto_methods = self._parse_protocol(proto_full)
                impl_methods = self._parse_implementation(impl_full)
                
                # Find extra methods
                proto_names = set(proto_methods.keys())
                impl_names = set(impl_methods.keys())
                extra = impl_names - proto_names
                
                if extra:
                    misaligned.append({
                        "protocol": protocol_name,
                        "extra_methods": list(extra),
                        "proto_path": proto_path,
                        "impl_path": impl_path
                    })
                    
        # Report findings
        if misaligned:
            print(f"Found {len(misaligned)} protocols with alignment issues:\n")
            for issue in misaligned:
                print(f"❌ {issue['protocol']}:")
                print(f"   Extra methods in implementation: {', '.join(issue['extra_methods'])}")
                print(f"   Protocol: {issue['proto_path']}")
                print(f"   Implementation: {issue['impl_path']}\n")
        else:
            print("✅ All checked protocols are aligned!")
            
        return misaligned


def main():
    """Main entry point."""
    fixer = ProtocolAlignmentFixer()
    
    # Analyze TelemetryService specifically
    fixer.analyze_telemetry_service()
    
    # Check all protocols
    print("\n" + "="*60)
    misaligned = fixer.check_all_protocols()
    
    print("\n=== Summary ===")
    print(f"Total protocols checked: 5")
    print(f"Misaligned protocols: {len(misaligned)}")
    
    if misaligned:
        print("\nTo fix these issues:")
        print("1. Add missing methods to protocols")
        print("2. Or make extra methods private (prefix with _)")
        print("3. Update method signatures to match exactly")


if __name__ == "__main__":
    main()