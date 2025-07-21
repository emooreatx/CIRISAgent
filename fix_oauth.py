#!/usr/bin/env python3
"""Fix OAuth callback URL in auth.py"""

import os

# Read the file
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'r') as f:
    content = f.read()

# Fix the OAUTH_CALLBACK_PATH
old_line = 'OAUTH_CALLBACK_PATH = "/v1/auth/oauth/datum/{provider}/callback"'
new_lines = '''# Get agent ID from environment, default to 'datum' if not set
AGENT_ID = os.getenv("CIRIS_AGENT_ID", "datum")
OAUTH_CALLBACK_PATH = f"/v1/auth/oauth/{AGENT_ID}/{{provider}}/callback"'''

content = content.replace(old_line, new_lines)

# Fix the GUI callback URL
content = content.replace(
    'gui_callback_url = f"/oauth/datum/{provider}/callback"',
    'gui_callback_url = f"/oauth/{AGENT_ID}/{provider}/callback"'
)

# Write back
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'w') as f:
    f.write(content)

print("OAuth callback URLs fixed!")