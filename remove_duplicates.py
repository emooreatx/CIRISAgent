#\!/usr/bin/env python3
import sys

# Line ranges to remove (0-based, end inclusive)
ranges_to_remove = [
    # Duplicate /resources routes
    (630, 707),    # 631-708 in 1-based
    (1209, 1286),  # 1210-1287
    (1459, 1536),  # 1460-1537
    (1538, 1621),  # 1539-1622
    (1707, 1784),  # 1708-1785
    (1954, 2030),  # 1955-2031
    
    # Duplicate /metrics/{metric_name} routes
    (546, 629),    # 547-630
    (1125, 1208),  # 1126-1209
    (1375, 1458),  # 1376-1459
    (1623, 1706),  # 1624-1707
    (1870, 1953),  # 1871-1954
]

# Sort ranges by start line (descending) to remove from bottom to top
ranges_to_remove.sort(key=lambda x: x[0], reverse=True)

# Read the file
with open('ciris_engine/logic/adapters/api/routes/telemetry.py', 'r') as f:
    lines = f.readlines()

print(f"Original file has {len(lines)} lines")

# Remove ranges
removed_count = 0
for start, end in ranges_to_remove:
    if start < len(lines) and end < len(lines):
        del lines[start:end+1]
        removed_count += (end - start + 1)
        print(f"Removed lines {start+1}-{end+1} ({end-start+1} lines)")

print(f"\nTotal removed: {removed_count} lines")
print(f"New file has {len(lines)} lines")

# Write the cleaned file
with open('ciris_engine/logic/adapters/api/routes/telemetry.py', 'w') as f:
    f.writelines(lines)

print("\nFile cleaned successfully\!")
