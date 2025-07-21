#!/usr/bin/env python3
"""Fix OAuth to use HTTPS in callback URL"""

# Read the file
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'r') as f:
    content = f.read()

# Find the base_url construction and ensure it uses HTTPS in production
old_base_url = '''        base_url = os.getenv("OAUTH_CALLBACK_BASE_URL")
        if not base_url:
            # Construct from request headers
            base_url = f"{request.url.scheme}://{request.headers.get('host', 'localhost')}"'''

new_base_url = '''        base_url = os.getenv("OAUTH_CALLBACK_BASE_URL", "https://agents.ciris.ai")'''

content = content.replace(old_base_url, new_base_url)

# Write back
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'w') as f:
    f.write(content)

print("OAuth fixed - using HTTPS base URL")