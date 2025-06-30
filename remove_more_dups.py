# Remove the first get_metric_detail function
with open('ciris_engine/logic/adapters/api/routes/telemetry.py', 'r') as f:
    lines = f.readlines()

print(f"Before: {len(lines)} lines")

# Delete lines 274-355 (0-based)
del lines[274:356]

print(f"After: {len(lines)} lines")
print(f"Removed {356-274} lines")

with open('ciris_engine/logic/adapters/api/routes/telemetry.py', 'w') as f:
    f.writelines(lines)
    
print("Done\!")
