# OAuth Configuration Guide for CIRIS Agents

This guide helps CIRISManager administrators configure OAuth authentication for CIRIS agents.

## Overview

CIRIS agents support OAuth authentication through a shared configuration file. OAuth credentials are stored in `/home/ciris/shared/oauth/oauth.json` and mounted into agent containers.

## Required Environment Variables

Each agent needs these environment variables:

```bash
OAUTH_CALLBACK_BASE_URL=https://agents.ciris.ai  # Your domain
CIRIS_AGENT_ID=datum                             # Agent identifier
```

## OAuth Configuration File Structure

Create `/home/ciris/shared/oauth/oauth.json`:

```json
{
  "google": {
    "client_id": "YOUR_GOOGLE_CLIENT_ID",
    "client_secret": "YOUR_GOOGLE_CLIENT_SECRET",
    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
    "token_uri": "https://oauth2.googleapis.com/token"
  },
  "discord": {
    "client_id": "YOUR_DISCORD_CLIENT_ID",
    "client_secret": "YOUR_DISCORD_CLIENT_SECRET",
    "auth_uri": "https://discord.com/oauth2/authorize",
    "token_uri": "https://discord.com/api/oauth2/token"
  },
  "github": {
    "client_id": "YOUR_GITHUB_CLIENT_ID",
    "client_secret": "YOUR_GITHUB_CLIENT_SECRET",
    "auth_uri": "https://github.com/login/oauth/authorize",
    "token_uri": "https://github.com/login/oauth/access_token"
  }
}
```

## Provider-Specific Setup

### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Create OAuth 2.0 credentials
5. Add authorized redirect URI:
   ```
   https://agents.ciris.ai/v1/auth/oauth/{agent_id}/google/callback
   ```
   Example: `https://agents.ciris.ai/v1/auth/oauth/datum/google/callback`

### Discord OAuth

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a new application
3. Navigate to OAuth2 settings
4. Add redirect URL:
   ```
   https://agents.ciris.ai/v1/auth/oauth/{agent_id}/discord/callback
   ```
5. Copy Client ID and Client Secret

### GitHub OAuth

1. Go to GitHub Settings → Developer settings → OAuth Apps
2. Click "New OAuth App"
3. Set Authorization callback URL:
   ```
   https://agents.ciris.ai/v1/auth/oauth/{agent_id}/github/callback
   ```
4. Copy Client ID and Client Secret

## Docker Compose Configuration

Ensure your agent mounts the OAuth configuration:

```yaml
services:
  agent-datum:
    volumes:
      - oauth_shared:/home/ciris/.ciris

volumes:
  oauth_shared:
    driver: local
    driver_opts:
      type: none
      o: bind
      device: /home/ciris/shared/oauth
```

## Security Considerations

1. **File Permissions**: Set restrictive permissions on oauth.json
   ```bash
   chmod 600 /home/ciris/shared/oauth/oauth.json
   chown ciris:ciris /home/ciris/shared/oauth/oauth.json
   ```

2. **Never commit OAuth credentials** to version control

3. **Use HTTPS only** for callback URLs

4. **Rotate credentials regularly**

## Testing OAuth

After configuration:

1. Visit: `https://agents.ciris.ai/api/{agent_id}/v1/auth/oauth/{provider}/authorize`
2. Complete OAuth flow
3. Check agent logs for successful authentication

## Troubleshooting

**Common Issues:**

1. **"Provider not configured"**: Check oauth.json exists and is readable
2. **Invalid redirect URI**: Ensure callback URL matches exactly in provider settings
3. **Permission denied**: Check file permissions and volume mounts

**Debug Commands:**
```bash
# Check if OAuth config is mounted
docker exec ciris-agent-datum ls -la /home/ciris/.ciris/

# View OAuth providers
curl https://agents.ciris.ai/api/datum/v1/auth/oauth/providers

# Check agent logs
docker logs ciris-agent-datum
```

## CIRISManager Integration

When creating agents through CIRISManager:

1. OAuth configuration is automatically mounted from shared volume
2. Set `OAUTH_CALLBACK_BASE_URL` in agent environment
3. Ensure `CIRIS_AGENT_ID` matches the agent identifier

The shared OAuth configuration allows all agents to use the same OAuth apps, simplifying management.
