#!/usr/bin/env python3
"""Analyze SVG positions."""
import re

with open('timeline_test2.svg', 'r') as f:
    svg_content = f.read()

# Extract circle positions
circles = re.findall(r'<circle[^>]*cx="([^"]+)"[^>]*cy="([^"]+)"', svg_content)

if circles:
    x_positions = {}
    for x, y in circles:
        x = round(float(x))  # Round to nearest pixel
        if x not in x_positions:
            x_positions[x] = 0
        x_positions[x] += 1
    
    print(f"Found {len(circles)} nodes")
    print(f"\nX-position distribution (rounded to nearest pixel):")
    
    # Group by ranges
    ranges = {}
    for x, count in x_positions.items():
        range_key = (x // 100) * 100  # Group by 100-pixel ranges
        if range_key not in ranges:
            ranges[range_key] = 0
        ranges[range_key] += count
    
    for r in sorted(ranges.keys()):
        print(f"  x={r}-{r+99}: {ranges[r]} nodes")
    
    print(f"\nUnique x-positions: {len(x_positions)}")
    print(f"X-range: {min(x_positions.keys())} to {max(x_positions.keys())}")
else:
    print("No circles found in SVG")