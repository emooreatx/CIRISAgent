# OAuth Setup Guide for CIRIS API v2.0

This guide explains how to configure OAuth providers (Google and Discord) for CIRIS API authentication.

## Overview

CIRIS API v2.0 supports OAuth authentication with the following providers:
- Google
- Discord
- GitHub (optional)

OAuth users are automatically assigned the `OBSERVER` role, which allows read-only access to the API.

## Prerequisites

1. CIRIS API running with v2.0
2. OAuth application credentials from your provider
3. Access to CIRIS configuration

## Setting Up OAuth Providers

### 1. Google OAuth Setup

First, create a Google OAuth application:

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URIs:
   - `http://localhost:8080/v2/auth/oauth/google/callback`
   - `https://your-domain.com/v2/auth/oauth/google/callback`

Then configure in CIRIS:

```python
# Add to your CIRIS configuration
oauth_providers = {
    "google": {
        "client_id": "YOUR_GOOGLE_CLIENT_ID",
        "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
        "scopes": "openid email profile"
    }
}
```

### 2. Discord OAuth Setup

Create a Discord application:

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Go to OAuth2 section
4. Add redirects:
   - `http://localhost:8080/v2/auth/oauth/discord/callback`
   - `https://your-domain.com/v2/auth/oauth/discord/callback`
5. Copy Client ID and Client Secret

Configure in CIRIS:

```python
# Add to your CIRIS configuration
oauth_providers = {
    "discord": {
        "client_id": "YOUR_DISCORD_CLIENT_ID",
        "client_secret": "YOUR_DISCORD_CLIENT_SECRET",
        "scopes": "identify email"
    }
}
```

### 3. Store Configuration

Using CIRIS config API (requires ADMIN role):

```bash
# Set OAuth configuration
curl -X POST http://localhost:8080/v2/config \
  -H "Authorization: Bearer YOUR_ADMIN_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "key": "oauth_providers",
    "value": {
      "google": {
        "client_id": "YOUR_GOOGLE_CLIENT_ID",
        "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
        "scopes": "openid email profile"
      },
      "discord": {
        "client_id": "YOUR_DISCORD_CLIENT_ID",
        "client_secret": "YOUR_DISCORD_CLIENT_SECRET",
        "scopes": "identify email"
      }
    }
  }'
```

## Using OAuth Authentication

### 1. Initiate OAuth Flow

Direct users to the OAuth start endpoint:

```
GET /v2/auth/oauth/{provider}/start
```

Examples:
- Google: `http://localhost:8080/v2/auth/oauth/google/start`
- Discord: `http://localhost:8080/v2/auth/oauth/discord/start`

This will redirect users to the provider's authorization page.

### 2. Handle Callback

After authorization, the provider redirects back to:

```
GET /v2/auth/oauth/{provider}/callback?code=AUTH_CODE&state=STATE
```

The API automatically:
1. Validates the authorization code
2. Exchanges it for access token
3. Fetches user profile
4. Creates/updates user account
5. Generates API key
6. Returns the API key to the user

### 3. Response Format

Successful authentication returns:

```json
{
  "access_token": "ciris_discord_AbCdEf123456...",
  "token_type": "Bearer",
  "expires_in": 2592000,
  "role": "OBSERVER",
  "user_id": "discord:123456789",
  "provider": "discord",
  "email": "user@example.com",
  "name": "Username"
}
```

### 4. Using the API Key

Include the API key in subsequent requests:

```bash
curl http://localhost:8080/v2/agent/identity \
  -H "Authorization: Bearer ciris_discord_AbCdEf123456..."
```

## Frontend Integration Example

### JavaScript/React Example

```javascript
// OAuth login button
function OAuthLogin({ provider }) {
  const handleLogin = () => {
    // Redirect to OAuth start endpoint
    window.location.href = `/v2/auth/oauth/${provider}/start`;
  };

  return (
    <button onClick={handleLogin}>
      Login with {provider}
    </button>
  );
}

// Handle callback (on callback page)
async function handleOAuthCallback() {
  const params = new URLSearchParams(window.location.search);
  const error = params.get('error');

  if (error) {
    console.error('OAuth error:', error);
    return;
  }

  // The API handles the callback automatically
  // The response includes the API key
  const response = await fetch(window.location.href);
  const data = await response.json();

  if (data.access_token) {
    // Store the API key
    localStorage.setItem('api_key', data.access_token);
    localStorage.setItem('user_role', data.role);

    // Redirect to app
    window.location.href = '/dashboard';
  }
}
```

### Python SDK Example

```python
import webbrowser
from ciris_sdk import CIRISClient

# Initiate OAuth login
def login_with_oauth(provider='google'):
    auth_url = f"http://localhost:8080/v2/auth/oauth/{provider}/start"
    webbrowser.open(auth_url)

    # After user completes OAuth flow, they'll get an API key
    api_key = input("Enter your API key: ")

    # Create client with API key
    client = CIRISClient(
        base_url="http://localhost:8080",
        api_key=api_key
    )

    return client
```

## Security Considerations

1. **HTTPS Required**: Always use HTTPS in production
2. **State Validation**: The API validates OAuth state parameter to prevent CSRF
3. **Token Storage**: Store API keys securely (not in browser localStorage for production)
4. **Scope Limitations**: OAuth users get OBSERVER role only
5. **Key Rotation**: Implement API key rotation for long-lived applications

## Troubleshooting

### Common Issues

1. **"OAuth provider not configured"**
   - Ensure OAuth provider config is stored in CIRIS config
   - Check client_id and client_secret are correct

2. **"Invalid redirect URI"**
   - Ensure callback URL matches exactly in provider settings
   - Include protocol (http/https) and port

3. **"State mismatch"**
   - OAuth state expired (10 minute timeout)
   - User took too long to authorize

4. **"Failed to fetch user profile"**
   - Check OAuth scopes include profile access
   - Verify provider API is accessible

## Role Upgrade

OAuth users start with OBSERVER role. To upgrade:

1. Contact a user with AUTHORITY role
2. Request role upgrade with justification
3. AUTHORITY user creates new API key with higher role

Example (AUTHORITY user):
```bash
curl -X POST http://localhost:8080/v2/auth/apikeys \
  -H "Authorization: Bearer AUTHORITY_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "role": "ADMIN",
    "description": "Promoted OAuth user for system management",
    "expires_in_days": 90
  }'
```

## API Endpoints Reference

- `GET /v2/auth/oauth/{provider}/start` - Start OAuth flow
- `GET /v2/auth/oauth/{provider}/callback` - OAuth callback (automatic)
- `POST /v2/auth/apikeys` - Create API key (ADMIN+)
- `GET /v2/auth/apikeys` - List API keys (ADMIN+)
- `DELETE /v2/auth/apikeys/{key_id}` - Revoke API key (ADMIN+)
- `GET /v2/auth/me` - Get current user info
