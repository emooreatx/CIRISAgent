"""
Engine Simplifier: Uses the hot/cold path map to refactor engine modules for strict protocol/schema-only compliance.
Splits logic for clarity and maintainability.
"""

import ast
import json
import os
from typing import Dict, List


class EngineSimplifier:
    def __init__(self, engine_root: str, hot_cold_map_path: str):
        self.engine_root = engine_root
        with open(hot_cold_map_path, "r") as f:
            self.hot_cold_map = json.load(f)

    def analyze_module(self, module_path: str) -> List[Dict]:
        """Analyze a module and propose refactors for non-hot type usage."""
        basename = os.path.relpath(module_path, self.engine_root)
        hot_types = set(self.hot_cold_map.get(module_path, {}))
        proposals = []
        with open(module_path, "r") as f:
            tree = ast.parse(f.read())
        for node in ast.walk(tree):
            # Flag Any, dict, or types not in hot_types
            if isinstance(node, ast.AnnAssign):
                if hasattr(node.annotation, "id"):
                    t = node.annotation.id
                    if t not in hot_types:
                        proposals.append(
                            {
                                "module": module_path,
                                "line": node.lineno,
                                "action": "refactor_type",
                                "from_type": t,
                                "to_type": list(hot_types)[0] if hot_types else None,
                            }
                        )
            if isinstance(node, ast.Assign):
                # Heuristic: assignment to dict or ambiguous type
                if hasattr(node.value, "func") and getattr(node.value.func, "id", None) == "dict":
                    proposals.append(
                        {
                            "module": module_path,
                            "line": node.lineno,
                            "action": "replace_dict",
                            "to_type": list(hot_types)[0] if hot_types else None,
                        }
                    )
        return proposals

    def analyze_all(self) -> List[Dict]:
        """Analyze all engine modules and collect proposals."""
        proposals = []
        for dirpath, _, filenames in os.walk(self.engine_root):
            for fname in filenames:
                if fname.endswith(".py"):
                    fpath = os.path.join(dirpath, fname)
                    proposals.extend(self.analyze_module(fpath))
        return proposals

    def write_proposals(self, output_path: str) -> None:
        proposals = self.analyze_all()
        with open(output_path, "w") as f:
            json.dump(proposals, f, indent=2)


# Entrypoint for CLI integration
def generate_engine_simplification_proposals(engine_root, hot_cold_map_path, output_path):
    simplifier = EngineSimplifier(engine_root, hot_cold_map_path)
    simplifier.write_proposals(output_path)
    return output_path
