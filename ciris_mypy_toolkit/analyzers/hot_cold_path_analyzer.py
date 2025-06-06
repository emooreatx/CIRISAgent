"""
hot_cold_path_analyzer.py

Analyzer for generating a hot/cold path availability map for schema/protocol objects in each module.
- Hot: Object is directly available (imported, argument, protocol return)
- Cold: Object is only available via context/persistence/indirect fetch

Outputs a per-module map for use by fixers and reporting.
"""

import ast
import os
from typing import Dict, List, Tuple, Set

class HotColdPathAnalyzer:
    def __init__(self, root_dir: str, protocols_dir: str, schemas_dir: str):
        self.root_dir = root_dir
        self.protocols_dir = protocols_dir
        self.schemas_dir = schemas_dir
        self.protocol_types = self._discover_protocol_types()
        self.schema_types = self._discover_schema_types()

    def _discover_protocol_types(self) -> Set[str]:
        types = set()
        for fname in os.listdir(self.protocols_dir):
            if fname.endswith('.py'):
                with open(os.path.join(self.protocols_dir, fname), 'r') as f:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            types.add(node.name)
        return types

    def _discover_schema_types(self) -> Set[str]:
        types = set()
        for fname in os.listdir(self.schemas_dir):
            if fname.endswith('.py'):
                with open(os.path.join(self.schemas_dir, fname), 'r') as f:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.ClassDef):
                            types.add(node.name)
        return types

    def analyze_module(self, module_path: str) -> Dict[str, Dict]:
        """Analyze a single module and return a map of schema/protocol objects and their path type."""
        with open(module_path, 'r') as f:
            tree = ast.parse(f.read())
        imported = set()
        hot = set()
        cold = set()
        lines = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                for n in node.names:
                    if n.name in self.protocol_types or n.name in self.schema_types:
                        imported.add(n.name)
                        hot.add(n.name)
                        lines[n.name] = node.lineno
            if isinstance(node, ast.arg):
                if node.annotation and hasattr(node.annotation, 'id'):
                    t = node.annotation.id
                    if t in self.protocol_types or t in self.schema_types:
                        hot.add(t)
                        lines[t] = node.lineno
            if isinstance(node, ast.AnnAssign):
                if hasattr(node.annotation, 'id'):
                    t = node.annotation.id
                    if t in self.protocol_types or t in self.schema_types:
                        hot.add(t)
                        lines[t] = node.lineno
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr') and node.func.attr in ('get_context', 'fetch', 'fetch_message'):
                    # Heuristic: context/persistence fetch
                    for a in node.args:
                        if hasattr(a, 'id') and (a.id in self.protocol_types or a.id in self.schema_types):
                            cold.add(a.id)
                            lines[a.id] = node.lineno
        # Anything not hot but used as cold
        cold = cold - hot
        result = {}
        for t in hot:
            result[t] = {'path': 'hot', 'line': lines[t]}
        for t in cold:
            result[t] = {'path': 'cold', 'line': lines[t]}
        return result

    def analyze_all(self) -> Dict[str, Dict[str, Dict]]:
        """Analyze all modules under root_dir and return a map: module -> {type -> {path, line}}"""
        result = {}
        for dirpath, _, filenames in os.walk(self.root_dir):
            for fname in filenames:
                if fname.endswith('.py'):
                    fpath = os.path.join(dirpath, fname)
                    mod_result = self.analyze_module(fpath)
                    if mod_result:
                        result[fpath] = mod_result
        return result

# Entrypoint for toolkit integration
def generate_hot_cold_path_map(root_dir, protocols_dir, schemas_dir, output_path):
    analyzer = HotColdPathAnalyzer(root_dir, protocols_dir, schemas_dir)
    result = analyzer.analyze_all()
    import json
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    return output_path
