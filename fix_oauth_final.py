#!/usr/bin/env python3
"""Fix OAuth to use correct callback URLs"""

# Read the file
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'r') as f:
    content = f.read()

# The callback URL sent to Google MUST be the API callback, not the GUI callback
# The redirect_uri parameter from the GUI should be stored and used AFTER OAuth completes

# Find and replace the callback URL logic
old_logic = '''        callback_url = redirect_uri or f"{base_url}{OAUTH_CALLBACK_PATH.replace('{provider}', provider)}"'''

new_logic = '''        # ALWAYS use API callback for OAuth provider - this is what's registered in Google Console
        api_callback_url = f"{base_url}{OAUTH_CALLBACK_PATH.replace('{provider}', provider)}"
        
        # Store the GUI redirect URI in state if provided
        state_data = {"csrf": state}
        if redirect_uri:
            state_data["gui_callback"] = redirect_uri
        
        # Encode state data
        import base64
        state_encoded = base64.b64encode(json.dumps(state_data).encode()).decode()
        
        callback_url = api_callback_url'''

content = content.replace(old_logic, new_logic)

# Also need to update the params to use state_encoded
content = content.replace('"state": state,', '"state": state_encoded,')
content = content.replace('"state": state\n', '"state": state_encoded\n')

# Write back
with open('/app/ciris_engine/logic/adapters/api/routes/auth.py', 'w') as f:
    f.write(content)

print("OAuth fixed! API callback URL will always be used for OAuth providers.")