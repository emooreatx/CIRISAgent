#!/usr/bin/env python3
"""Simple OAuth fix - just use API callback URL"""

# Read the file
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'r') as f:
    lines = f.readlines()

# Find and fix the callback_url line
for i, line in enumerate(lines):
    if 'callback_url = ' in line and 'api_callback_url' in line:
        # Fix the broken line from previous attempt
        lines[i] = '        callback_url = f"{base_url}{OAUTH_CALLBACK_PATH.replace(\'{provider}\', provider)}"\n'
    elif 'callback_url = redirect_uri or' in line:
        # Fix the original line
        lines[i] = '        callback_url = f"{base_url}{OAUTH_CALLBACK_PATH.replace(\'{provider}\', provider)}"\n'
    elif 'state_encoded' in line and '"state":' in line:
        # Fix state_encoded references back to state
        lines[i] = line.replace('state_encoded', 'state')

# Write back
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'w') as f:
    f.writelines(lines)

print("OAuth fixed - using API callback URL")