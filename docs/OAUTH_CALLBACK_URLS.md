# OAuth Callback URLs - CRITICAL DOCUMENTATION

## Production OAuth Callback URL Format

**NEVER FORGET THIS FORMAT:**

```
https://agents.ciris.ai/v1/auth/oauth/{agent_id}/{provider}/callback
```

Where:
- `{agent_id}` = The agent ID (e.g., `datum`, `scout`)
- `{provider}` = The OAuth provider (e.g., `google`, `discord`)

## Examples

### For Datum Agent:
- **Google OAuth**: `https://agents.ciris.ai/v1/auth/oauth/datum/google/callback`
- **Discord OAuth**: `https://agents.ciris.ai/v1/auth/oauth/datum/discord/callback`

### For Scout Agent:
- **Google OAuth**: `https://agents.ciris.ai/v1/auth/oauth/scout/google/callback`
- **Discord OAuth**: `https://agents.ciris.ai/v1/auth/oauth/scout/discord/callback`

## IMPORTANT NOTES

1. **The agent ID comes BEFORE the provider** in the URL path
2. **The /v1/ is at the root level**, not after /api/
3. **This is the DEFAULT nginx route** - it proxies to the Datum agent by default
4. **Multi-agent routes** use `/api/{agent}/v1/...` format but OAuth uses the default route

## Why This Format?

- The API defines the route as `/auth/oauth/{provider}/callback` in auth.py
- But the OAUTH_CALLBACK_PATH in the code is `/v1/auth/oauth/datum/{provider}/callback`
- The nginx default route handles `/v1/*` requests and sends them to Datum
- This allows OAuth to work without specifying the agent in the initial path

## Google Console Configuration

When setting up Google OAuth, add these **Authorized redirect URIs**:
- `https://agents.ciris.ai/v1/auth/oauth/datum/google/callback`
- `https://agents.ciris.ai/v1/auth/oauth/scout/google/callback` (if using Scout)

## Common Mistakes to Avoid

❌ `https://agents.ciris.ai/oauth/datum/callback` - This is the GUI callback page
❌ `https://agents.ciris.ai/api/datum/v1/auth/oauth/google/callback` - Wrong path structure
❌ `https://agents.ciris.ai/v1/auth/oauth/google/datum/callback` - Agent ID in wrong position

✅ `https://agents.ciris.ai/v1/auth/oauth/datum/google/callback` - CORRECT FORMAT
