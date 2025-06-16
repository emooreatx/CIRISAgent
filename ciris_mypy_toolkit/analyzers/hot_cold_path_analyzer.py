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
        telemetry_points = set()  # Track telemetry recording points
        critical_paths = set()    # Track mission-critical code paths
        
        for node in ast.walk(tree):
            # Direct imports are HOT
            if isinstance(node, ast.ImportFrom):
                for n in node.names:
                    if n.name in self.protocol_types or n.name in self.schema_types:
                        imported.add(n.name)
                        hot.add(n.name)
                        lines[n.name] = node.lineno
            
            # Function arguments are HOT
            if isinstance(node, ast.arg):
                if node.annotation and hasattr(node.annotation, 'id'):
                    t = node.annotation.id
                    if t in self.protocol_types or t in self.schema_types:
                        hot.add(t)
                        lines[t] = node.lineno
            
            # Variable annotations are HOT
            if isinstance(node, ast.AnnAssign):
                if hasattr(node.annotation, 'id'):
                    t = node.annotation.id
                    if t in self.protocol_types or t in self.schema_types:
                        hot.add(t)
                        lines[t] = node.lineno
            
            # Detect telemetry recording points
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'attr'):
                    # Track telemetry calls
                    if node.func.attr in ('record_metric', 'record_event', 'track_performance'):
                        telemetry_points.add(node.lineno)
                    
                    # Context/persistence fetches are COLD
                    if node.func.attr in ('get_context', 'fetch', 'fetch_message', 'get_service'):
                        for a in node.args:
                            if hasattr(a, 'id') and (a.id in self.protocol_types or a.id in self.schema_types):
                                cold.add(a.id)
                                lines[a.id] = node.lineno
            
            # Detect critical paths (error handling, audit, security)
            if isinstance(node, ast.FunctionDef):
                func_name = node.name.lower()
                if any(critical in func_name for critical in ['audit', 'security', 'auth', 'error', 'critical', 'emergency']):
                    critical_paths.add(node.lineno)
        
        # Anything not hot but used as cold
        cold = cold - hot
        
        result = {
            'types': {},
            'telemetry': {
                'recording_points': list(telemetry_points),
                'density': len(telemetry_points) / max(1, len(tree.body)),
                'critical_paths': list(critical_paths)
            }
        }
        
        for t in hot:
            result['types'][t] = {'path': 'hot', 'line': lines.get(t, 0), 'telemetry_required': False}
        
        for t in cold:
            result['types'][t] = {'path': 'cold', 'line': lines.get(t, 0), 'telemetry_required': True}
        
        # Mark types used in critical paths as requiring telemetry
        for t, info in result['types'].items():
            if info['line'] in critical_paths:
                info['telemetry_required'] = True
                info['critical'] = True
        
        return result

    def analyze_all(self) -> Dict[str, Dict[str, Dict]]:
        """Analyze all modules under root_dir and return a comprehensive hot/cold path map with telemetry insights."""
        result = {
            'modules': {},
            'summary': {
                'total_modules': 0,
                'modules_with_telemetry': 0,
                'critical_modules': [],
                'telemetry_coverage': 0.0,
                'hot_types': set(),
                'cold_types': set(),
                'recommendations': []
            }
        }
        
        for dirpath, _, filenames in os.walk(self.root_dir):
            for fname in filenames:
                if fname.endswith('.py') and not fname.startswith('test_'):
                    fpath = os.path.join(dirpath, fname)
                    mod_result = self.analyze_module(fpath)
                    if mod_result and mod_result.get('types'):
                        result['modules'][fpath] = mod_result
                        result['summary']['total_modules'] += 1
                        
                        # Track telemetry coverage
                        if mod_result['telemetry']['recording_points']:
                            result['summary']['modules_with_telemetry'] += 1
                        
                        # Track critical modules
                        if mod_result['telemetry']['critical_paths']:
                            result['summary']['critical_modules'].append(fpath)
                        
                        # Aggregate hot/cold types
                        for type_name, info in mod_result['types'].items():
                            if info['path'] == 'hot':
                                result['summary']['hot_types'].add(type_name)
                            else:
                                result['summary']['cold_types'].add(type_name)
        
        # Calculate telemetry coverage
        if result['summary']['total_modules'] > 0:
            result['summary']['telemetry_coverage'] = (
                result['summary']['modules_with_telemetry'] / result['summary']['total_modules']
            )
        
        # Generate recommendations
        result['summary']['recommendations'] = self._generate_telemetry_recommendations(result)
        
        # Convert sets to lists for JSON serialization
        result['summary']['hot_types'] = list(result['summary']['hot_types'])
        result['summary']['cold_types'] = list(result['summary']['cold_types'])
        
        return result
    
    def _generate_telemetry_recommendations(self, analysis_result: Dict) -> List[str]:
        """Generate telemetry recommendations based on hot/cold path analysis."""
        recommendations = []
        
        # Low telemetry coverage
        coverage = analysis_result['summary']['telemetry_coverage']
        if coverage < 0.3:
            recommendations.append(
                f"CRITICAL: Low telemetry coverage ({coverage:.1%}). Add telemetry to hot paths for better observability."
            )
        
        # Critical modules without telemetry
        critical_without_telemetry = []
        for module in analysis_result['summary']['critical_modules']:
            mod_data = analysis_result['modules'].get(module, {})
            if not mod_data.get('telemetry', {}).get('recording_points'):
                critical_without_telemetry.append(module)
        
        if critical_without_telemetry:
            recommendations.append(
                f"HIGH: {len(critical_without_telemetry)} critical modules lack telemetry. Add monitoring to: " +
                ", ".join(os.path.basename(m) for m in critical_without_telemetry[:3]) + 
                ("..." if len(critical_without_telemetry) > 3 else "")
            )
        
        # Cold types that should be monitored
        cold_types = analysis_result['summary']['cold_types']
        important_cold_types = [t for t in cold_types if any(critical in t.lower() for critical in ['auth', 'audit', 'security', 'error'])]
        if important_cold_types:
            recommendations.append(
                f"MEDIUM: Monitor cold path access for critical types: {', '.join(important_cold_types[:5])}"
            )
        
        # Hot path optimization opportunities
        hot_types = analysis_result['summary']['hot_types']
        if len(hot_types) > 50:
            recommendations.append(
                f"INFO: {len(hot_types)} hot types detected. Consider caching frequently accessed types for performance."
            )
        
        return recommendations

# Entrypoint for toolkit integration
def generate_hot_cold_path_map(root_dir, protocols_dir, schemas_dir, output_path):
    analyzer = HotColdPathAnalyzer(root_dir, protocols_dir, schemas_dir)
    result = analyzer.analyze_all()
    import json
    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2)
    return output_path
