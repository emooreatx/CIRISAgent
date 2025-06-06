#!/usr/bin/env python3
"""
Standalone script to run engine simplification automation using the hot/cold path map.
"""
from ciris_mypy_toolkit.analyzers.engine_simplifier import generate_engine_simplification_proposals

def main():
    engine_root = "ciris_engine"
    hot_cold_map_path = "ciris_mypy_toolkit/reports/hot_cold_path_map.json"
    output_path = "ciris_mypy_toolkit/reports/engine_simplification_proposals.json"
    generate_engine_simplification_proposals(engine_root, hot_cold_map_path, output_path)
    print(f"Engine simplification proposals written to {output_path}")

if __name__ == "__main__":
    main()
