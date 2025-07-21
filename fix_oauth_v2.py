#!/usr/bin/env python3
"""Fix OAuth to use correct API callback URL"""

import re

# Read the file
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'r') as f:
    content = f.read()

# Fix the callback URL logic - always use the API callback for OAuth provider
old_line = '        callback_url = redirect_uri or f"{base_url}{OAUTH_CALLBACK_PATH.replace(\'{provider}\', provider)}"'
new_line = '        callback_url = f"{base_url}{OAUTH_CALLBACK_PATH.replace(\'{provider}\', provider)}"'

content = content.replace(old_line, new_line)

# Write back
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'w') as f:
    f.write(content)

print("OAuth callback URL fixed to always use API callback!")