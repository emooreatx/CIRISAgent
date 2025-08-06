#!/usr/bin/env python3
"""Analyze SVG positions."""
import re

with open("timeline_test.svg", "r") as f:
    svg_content = f.read()

# Extract circle positions
circles = re.findall(r'<circle[^>]*cx="([^"]+)"[^>]*cy="([^"]+)"', svg_content)

if circles:
    x_positions = {}
    for x, y in circles:
        x = float(x)
        if x not in x_positions:
            x_positions[x] = 0
        x_positions[x] += 1

    print(f"Found {len(circles)} nodes")
    print("\nX-position distribution:")
    for x in sorted(x_positions.keys()):
        print(f"  x={x}: {x_positions[x]} nodes")

    print(f"\nUnique x-positions: {len(x_positions)}")
    print(f"X-range: {min(x_positions.keys())} to {max(x_positions.keys())}")
else:
    print("No circles found in SVG")
