# OAuth Authentication Endpoints

The CIRIS Agent provides comprehensive OAuth 2.0 authentication support for creating Wise Authority (WA) certificates through third-party providers.

## Base URL
```
http://localhost:8080/v1/auth
```

## Supported Providers
- Google
- Discord  
- GitHub
- Custom OIDC providers

## Authentication Flow

### 1. Configure OAuth Provider
Before using OAuth authentication, providers must be configured via the CLI:

```bash
ciris wa oauth add google
# Enter CLIENT_ID and CLIENT_SECRET when prompted
```

### 2. Initiate OAuth Flow
```http
GET /v1/auth/oauth/{provider}/login
```

Initiates the OAuth authentication flow for the specified provider.

**Path Parameters:**
- `provider` (string): OAuth provider name (google, discord, github, custom)

**Query Parameters:**
- `redirect_uri` (string, optional): Custom redirect URI after authentication
- `state` (string, optional): CSRF protection state parameter

**Response:**
```json
{
  "auth_url": "https://accounts.google.com/o/oauth2/v2/auth?client_id=...",
  "state": "random-state-token",
  "provider": "google"
}
```

**Example:**
```bash
curl http://localhost:8080/v1/auth/oauth/google/login
```

### 3. OAuth Callback
```http
GET /v1/auth/oauth/{provider}/callback
```

Handles the OAuth provider callback after user authorization.

**Path Parameters:**
- `provider` (string): OAuth provider name

**Query Parameters:**
- `code` (string, required): Authorization code from OAuth provider
- `state` (string, required): State parameter for CSRF validation
- `error` (string, optional): Error code if authorization failed
- `error_description` (string, optional): Human-readable error description

**Success Response:**
```json
{
  "status": "success",
  "wa_id": "wa-2025-06-15-OBS123",
  "provider": "google",
  "token": "eyJhbGciOiJIUzI1NiIs...",
  "user_info": {
    "id": "123456789",
    "email": "user@example.com",
    "name": "John Doe",
    "picture": "https://..."
  },
  "scopes": ["read:any", "write:message"]
}
```

**Error Response:**
```json
{
  "status": "error",
  "error": "access_denied",
  "error_description": "User denied access"
}
```

### 4. Get OAuth Session Info
```http
GET /v1/auth/session
Authorization: Bearer {jwt_token}
```

Retrieves information about the current OAuth session.

**Response:**
```json
{
  "wa_id": "wa-2025-06-15-OBS123",
  "name": "John Doe",
  "role": "observer",
  "provider": "google",
  "external_id": "123456789",
  "scopes": ["read:any", "write:message"],
  "token_type": "oauth",
  "expires_at": "2025-06-15T20:00:00Z"
}
```

## OAuth Provider Configuration

### Google OAuth Setup
1. Create a project at [Google Cloud Console](https://console.cloud.google.com)
2. Enable Google+ API
3. Create OAuth 2.0 credentials
4. Add redirect URI: `http://localhost:8080/v1/auth/oauth/google/callback`
5. Configure in CIRIS:
   ```bash
   ciris wa oauth add google
   ```

### Discord OAuth Setup
1. Create an application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Add OAuth2 redirect: `http://localhost:8080/v1/auth/oauth/discord/callback`
3. Required scopes: `identify`, `email`
4. Configure in CIRIS:
   ```bash
   ciris wa oauth add discord
   ```

### GitHub OAuth Setup
1. Register a new OAuth App in GitHub Settings
2. Authorization callback URL: `http://localhost:8080/v1/auth/oauth/github/callback`
3. Configure in CIRIS:
   ```bash
   ciris wa oauth add github
   ```

## OAuth WA Certificate Details

When a user successfully authenticates via OAuth, an observer-level WA certificate is automatically created with:

- **Role**: `observer`
- **Scopes**: `["read:any", "write:message"]`
- **Token Type**: `oauth`
- **Auto-minted**: `true`
- **Discord ID**: Automatically linked if using Discord OAuth

The certificate includes:
- OAuth provider name
- External user ID from the provider
- User profile information (name, email, avatar)
- Automatic session JWT valid for 8 hours

## Security Considerations

1. **CSRF Protection**: All OAuth flows include state parameter validation
2. **Token Storage**: OAuth tokens are never stored; only the external ID mapping
3. **Session Management**: JWT sessions expire after 8 hours
4. **Scope Limitations**: OAuth users start as observers; promotion requires WA approval
5. **Rate Limiting**: OAuth endpoints are rate-limited to prevent abuse

## Token Refresh

OAuth tokens are not automatically refreshed. When a session expires:
1. User must re-authenticate through the OAuth flow
2. Existing WA certificate is reactivated (not recreated)
3. New JWT session token is issued

## Revocation

To revoke OAuth access:
```bash
ciris wa revoke {wa_id}
```

This will:
- Mark the WA certificate as inactive
- Invalidate any active JWT sessions
- Prevent future OAuth logins from reactivating the certificate

## Custom OIDC Providers

For custom OpenID Connect providers:

```bash
ciris wa oauth add custom
# Provide:
# - Provider name
# - OIDC metadata URL
# - Client ID
# - Client secret
```

The system will auto-discover endpoints from the OIDC metadata.

## Error Codes

| Code | Description |
|------|-------------|
| `invalid_provider` | Unknown OAuth provider |
| `provider_not_configured` | OAuth provider not set up |
| `invalid_code` | Authorization code invalid or expired |
| `state_mismatch` | CSRF state validation failed |
| `token_exchange_failed` | Failed to exchange code for token |
| `profile_fetch_failed` | Could not retrieve user profile |
| `wa_creation_failed` | Failed to create WA certificate |

## Example Integration

```javascript
// 1. Redirect user to OAuth login
const response = await fetch('http://localhost:8080/v1/auth/oauth/google/login');
const { auth_url } = await response.json();
window.location.href = auth_url;

// 2. Handle callback (server-side)
app.get('/oauth/callback', async (req, res) => {
  const { code, state } = req.query;
  
  const response = await fetch(
    `http://localhost:8080/v1/auth/oauth/google/callback?code=${code}&state=${state}`
  );
  
  const result = await response.json();
  if (result.status === 'success') {
    // Store JWT token
    req.session.token = result.token;
    res.redirect('/dashboard');
  } else {
    res.redirect('/login?error=' + result.error);
  }
});

// 3. Use JWT for authenticated requests
const messages = await fetch('http://localhost:8080/v1/messages', {
  headers: {
    'Authorization': `Bearer ${session.token}`
  }
});
```