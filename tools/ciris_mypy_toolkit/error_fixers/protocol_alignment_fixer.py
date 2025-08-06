"""
Protocol Alignment Fixer - Ensures 100% protocol-implementation alignment

This fixer:
1. Compares protocol signatures with implementation signatures
2. Updates protocols to match implementations (or vice versa)
3. Ensures parameter names, types, and defaults match exactly
"""

import ast
from pathlib import Path
from typing import Any, Dict, List, Optional

import astor


class ProtocolAlignmentFixer:
    """Fixes protocol-implementation mismatches."""

    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.protocols_path = self.project_root / "protocols"
        self.fixes_applied = 0

    def fix_all_protocols(self) -> Dict[str, Any]:
        """Fix all protocol alignment issues."""
        results = {
            "protocols_fixed": 0,
            "methods_aligned": 0,
            "parameters_fixed": 0,
            "files_modified": [],
            "errors": [],
        }

        # First, find all protocol-implementation pairs
        pairs = self._find_protocol_implementation_pairs()

        for protocol_name, impl_info in pairs.items():
            try:
                fixes = self._fix_protocol_alignment(protocol_name, impl_info)
                if fixes["changes_made"]:
                    results["protocols_fixed"] += 1
                    results["methods_aligned"] += fixes["methods_aligned"]
                    results["parameters_fixed"] += fixes["parameters_fixed"]
                    results["files_modified"].extend(fixes["files_modified"])
            except Exception as e:
                results["errors"].append({"protocol": protocol_name, "error": str(e)})

        return results

    def _find_protocol_implementation_pairs(self) -> Dict[str, Dict[str, Any]]:
        """Find all protocol-implementation pairs."""
        pairs = {}

        # Map of protocol names to their implementations
        known_mappings = {
            "TelemetryServiceProtocol": "TelemetryService",
            "AuditServiceProtocol": "AuditService",
            "MemoryServiceProtocol": "MemoryService",
            "LLMServiceProtocol": "LLMService",
            "TimeServiceProtocol": "TimeService",
            "ShutdownServiceProtocol": "ShutdownService",
            "RuntimeControlServiceProtocol": "RuntimeControlService",
            # Add more mappings as needed
        }

        for protocol_name, impl_name in known_mappings.items():
            protocol_info = self._find_protocol(protocol_name)
            impl_info = self._find_implementation(impl_name)

            if protocol_info and impl_info:
                pairs[protocol_name] = {"protocol": protocol_info, "implementation": impl_info}

        return pairs

    def _fix_protocol_alignment(self, protocol_name: str, info: Dict[str, Any]) -> Dict[str, Any]:
        """Fix alignment between a protocol and its implementation."""
        results = {"changes_made": False, "methods_aligned": 0, "parameters_fixed": 0, "files_modified": []}

        protocol_info = info["protocol"]
        impl_info = info["implementation"]

        # Compare methods
        protocol_methods = protocol_info["methods"]
        impl_methods = impl_info["methods"]

        # Find methods in implementation but not in protocol
        extra_methods = set(impl_methods.keys()) - set(protocol_methods.keys())

        # Find methods with mismatched signatures
        for method_name in protocol_methods:
            if method_name in impl_methods:
                protocol_sig = protocol_methods[method_name]
                impl_sig = impl_methods[method_name]

                if not self._signatures_match(protocol_sig, impl_sig):
                    # Fix the protocol to match implementation
                    if self._update_protocol_method(protocol_info["file_path"], method_name, impl_sig):
                        results["parameters_fixed"] += 1
                        results["changes_made"] = True

        # Add missing methods to protocol
        if extra_methods:
            public_extras = [m for m in extra_methods if not m.startswith("_")]
            if public_extras and self._add_methods_to_protocol(protocol_info["file_path"], public_extras, impl_info):
                results["methods_aligned"] += len(public_extras)
                results["changes_made"] = True

        if results["changes_made"]:
            results["files_modified"].append(str(protocol_info["file_path"]))

        return results

    def _signatures_match(self, protocol_sig: Dict, impl_sig: Dict) -> bool:
        """Check if two method signatures match."""
        # Check parameters
        if len(protocol_sig["params"]) != len(impl_sig["params"]):
            return False

        for p1, p2 in zip(protocol_sig["params"], impl_sig["params"]):
            if p1["name"] != p2["name"]:
                return False
            if p1.get("type") != p2.get("type"):
                return False
            if p1.get("default") != p2.get("default"):
                return False

        # Check return type
        if protocol_sig.get("return_type") != impl_sig.get("return_type"):
            return False

        return True

    def _update_protocol_method(self, file_path: Path, method_name: str, new_signature: Dict) -> bool:
        """Update a method signature in the protocol."""
        try:
            content = file_path.read_text()
            tree = ast.parse(content)

            class MethodUpdater(ast.NodeTransformer):
                def __init__(self, method_name: str, new_sig: Dict):
                    self.method_name = method_name
                    self.new_sig = new_sig
                    self.updated = False

                def visit_FunctionDef(self, node):
                    if node.name == self.method_name:
                        # Update parameters
                        new_args = []
                        for param in self.new_sig["params"]:
                            arg = ast.arg(arg=param["name"], annotation=None)
                            if param.get("type"):
                                # Add type annotation
                                arg.annotation = ast.parse(param["type"]).body[0].value
                            new_args.append(arg)

                        # Handle defaults
                        defaults = []
                        for param in self.new_sig["params"]:
                            if param.get("default"):
                                defaults.append(ast.parse(param["default"]).body[0].value)

                        node.args.args = new_args
                        node.args.defaults = defaults

                        # Update return type
                        if self.new_sig.get("return_type"):
                            node.returns = ast.parse(self.new_sig["return_type"]).body[0].value

                        self.updated = True

                    return node

                def visit_AsyncFunctionDef(self, node):
                    return self.visit_FunctionDef(node)

            updater = MethodUpdater(method_name, new_signature)
            new_tree = updater.visit(tree)

            if updater.updated:
                new_content = astor.to_source(new_tree)
                file_path.write_text(new_content)
                return True

        except Exception as e:
            print(f"Error updating {method_name} in {file_path}: {e}")

        return False

    def _add_methods_to_protocol(self, file_path: Path, methods: List[str], impl_info: Dict) -> bool:
        """Add missing methods to protocol."""
        try:
            content = file_path.read_text()
            lines = content.split("\n")

            # Find the class definition
            class_line = -1
            indent = ""
            for i, line in enumerate(lines):
                if "class " in line and "Protocol" in line:
                    class_line = i
                    # Find the indentation of the next line
                    for j in range(i + 1, len(lines)):
                        if lines[j].strip():
                            indent = lines[j][: len(lines[j]) - len(lines[j].lstrip())]
                            break
                    break

            if class_line == -1:
                return False

            # Find where to insert (before the last line of the class)
            insert_line = len(lines) - 1
            for i in range(len(lines) - 1, class_line, -1):
                if lines[i].strip() and not lines[i].startswith(indent):
                    insert_line = i
                    break

            # Build method stubs
            new_methods = []
            for method_name in methods:
                if method_name in impl_info["implementation"]["methods"]:
                    method_info = impl_info["implementation"]["methods"][method_name]

                    # Build method stub
                    stub = f"\n{indent}@abstractmethod"
                    if method_info.get("is_async"):
                        stub += f"\n{indent}async def {method_name}(self"
                    else:
                        stub += f"\n{indent}def {method_name}(self"

                    # Add parameters
                    for param in method_info["params"][1:]:  # Skip self
                        stub += f", {param['name']}"
                        if param.get("type"):
                            stub += f": {param['type']}"
                        if param.get("default"):
                            stub += f" = {param['default']}"

                    stub += ")"

                    # Add return type
                    if method_info.get("return_type"):
                        stub += f" -> {method_info['return_type']}"

                    stub += ":"
                    stub += f'\n{indent}    """TODO: Document {method_name}."""'
                    stub += f"\n{indent}    ..."

                    new_methods.append(stub)

            # Insert new methods
            if new_methods:
                lines.insert(insert_line, "\n".join(new_methods))
                file_path.write_text("\n".join(lines))
                return True

        except Exception as e:
            print(f"Error adding methods to {file_path}: {e}")

        return False

    def _find_protocol(self, protocol_name: str) -> Optional[Dict[str, Any]]:
        """Find a protocol and extract its methods."""
        for file_path in self.protocols_path.rglob("*.py"):
            try:
                tree = ast.parse(file_path.read_text())
                for node in ast.walk(tree):
                    if isinstance(node, ast.ClassDef) and node.name == protocol_name:
                        methods = {}
                        for item in node.body:
                            if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                methods[item.name] = self._extract_signature(item)

                        return {"file_path": file_path, "methods": methods}
            except:
                continue

        return None

    def _find_implementation(self, impl_name: str) -> Optional[Dict[str, Any]]:
        """Find an implementation and extract its methods."""
        search_paths = [
            self.project_root / "logic" / "services",
            self.project_root / "logic" / "services" / "graph",
            self.project_root / "logic" / "services" / "lifecycle",
            self.project_root / "logic" / "services" / "infrastructure",
            self.project_root / "logic" / "services" / "core",
            self.project_root / "logic" / "services" / "runtime",
        ]

        for path in search_paths:
            if path.exists():
                for file_path in path.rglob("*.py"):
                    try:
                        tree = ast.parse(file_path.read_text())
                        for node in ast.walk(tree):
                            if isinstance(node, ast.ClassDef) and node.name == impl_name:
                                methods = {}
                                for item in node.body:
                                    if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                                        if not item.name.startswith("_"):  # Only public methods
                                            methods[item.name] = self._extract_signature(item)

                                return {"file_path": file_path, "methods": methods}
                    except:
                        continue

        return None

    def _extract_signature(self, node: ast.FunctionDef) -> Dict[str, Any]:
        """Extract method signature details."""
        sig = {"is_async": isinstance(node, ast.AsyncFunctionDef), "params": [], "return_type": None}

        # Extract parameters
        for i, arg in enumerate(node.args.args):
            param = {"name": arg.arg}

            # Get type annotation
            if arg.annotation:
                param["type"] = astor.to_source(arg.annotation).strip()

            # Get default value
            default_offset = len(node.args.args) - len(node.args.defaults)
            if i >= default_offset:
                default_idx = i - default_offset
                if default_idx < len(node.args.defaults):
                    param["default"] = astor.to_source(node.args.defaults[default_idx]).strip()

            sig["params"].append(param)

        # Get return type
        if node.returns:
            sig["return_type"] = astor.to_source(node.returns).strip()

        return sig
