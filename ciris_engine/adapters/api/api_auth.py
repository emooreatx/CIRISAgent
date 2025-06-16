"""API Authentication endpoints for OAuth and WA management."""
import logging
import json
from aiohttp import web
from typing import Any, Dict, Optional
from urllib.parse import urlencode

logger = logging.getLogger(__name__)


class APIAuthRoutes:
    """Authentication routes for OAuth and WA management."""
    
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.auth_service = None
        self.oauth_service = None
        
    async def _ensure_services(self) -> bool:
        """Ensure auth services are available."""
        if not self.auth_service and hasattr(self.runtime, 'wa_auth_system'):
            wa_auth_system = self.runtime.wa_auth_system
            if wa_auth_system:
                self.auth_service = wa_auth_system.get_auth_service()
                self.oauth_service = wa_auth_system.get_oauth_service()
        
        return bool(self.auth_service and self.oauth_service)
    
    def register(self, app: web.Application) -> None:
        """Register auth routes with the application."""
        # OAuth endpoints
        app.router.add_get('/v1/auth/oauth/{provider}/start', self._handle_oauth_start)
        app.router.add_get('/v1/auth/oauth/{provider}/callback', self._handle_oauth_callback)
        
        # WA management endpoints
        app.router.add_post('/v1/auth/login', self._handle_login)
        app.router.add_get('/v1/auth/verify', self._handle_verify_token)
        app.router.add_post('/v1/wa/link-discord', self._handle_link_discord)
        
    async def _handle_oauth_start(self, request: web.Request) -> web.Response:
        """Start OAuth flow for a provider."""
        provider = request.match_info['provider']
        
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Get the redirect URI from query params or use default
            redirect_uri = request.query.get('redirect_uri')
            if not redirect_uri:
                # Default to the callback endpoint
                scheme = request.scheme
                host = request.host
                redirect_uri = f"{scheme}://{host}/v1/auth/oauth/{provider}/callback"
            
            # Get provider config
            provider_config = await self.oauth_service.get_provider_config(provider)
            if not provider_config:
                return web.json_response({
                    "error": f"OAuth provider '{provider}' not configured"
                }, status=400)
            
            # Generate state for CSRF protection
            import secrets
            state = secrets.token_urlsafe(32)
            
            # Store state in session or cache (simplified - in production use proper session management)
            # For now, we'll pass it through and validate on return
            
            # Build authorization URL
            auth_params = {
                'client_id': provider_config['client_id'],
                'redirect_uri': redirect_uri,
                'response_type': 'code',
                'state': state,
                'scope': provider_config.get('scopes', '').replace(',', ' ')
            }
            
            # Add provider-specific parameters
            if provider == 'discord':
                auth_params['prompt'] = 'consent'
            elif provider == 'google':
                auth_params['access_type'] = 'offline'
                auth_params['prompt'] = 'consent'
            
            auth_url = f"{provider_config['auth_url']}?{urlencode(auth_params)}"
            
            return web.json_response({
                "auth_url": auth_url,
                "state": state,
                "provider": provider
            })
            
        except Exception as e:
            logger.error(f"OAuth start error for {provider}: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def _handle_oauth_callback(self, request: web.Request) -> web.Response:
        """Handle OAuth callback from provider."""
        provider = request.match_info['provider']
        
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Extract callback parameters
            code = request.query.get('code')
            state = request.query.get('state')
            error = request.query.get('error')
            error_description = request.query.get('error_description')
            
            if error:
                return web.json_response({
                    "error": error,
                    "description": error_description or "OAuth authorization failed"
                }, status=400)
            
            if not code:
                return web.json_response({
                    "error": "No authorization code received"
                }, status=400)
            
            # In production, validate state against stored value
            # For now, we'll proceed with the exchange
            
            # Exchange code for tokens
            callback_data = {
                'code': code,
                'state': state
            }
            
            result = await self.oauth_service.handle_oauth_callback(provider, callback_data)
            
            if result['status'] == 'success':
                # OAuth successful - return JWT and WA info
                wa_cert = result['wa_cert']
                token = result['token']
                
                return web.json_response({
                    "status": "success",
                    "token": token,
                    "wa_id": wa_cert['wa_id'],
                    "name": wa_cert['name'],
                    "role": wa_cert['role'],
                    "scopes": wa_cert['scopes'],
                    "provider": provider,
                    "external_id": wa_cert.get('oauth_external_id'),
                    "discord_id": wa_cert.get('discord_id')
                })
            else:
                return web.json_response({
                    "error": result.get('error', 'OAuth exchange failed')
                }, status=400)
                
        except Exception as e:
            logger.error(f"OAuth callback error for {provider}: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def _handle_login(self, request: web.Request) -> web.Response:
        """Handle traditional WA login."""
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            data = await request.json()
            wa_id = data.get('wa_id')
            password = data.get('password')
            
            if not wa_id or not password:
                return web.json_response({
                    "error": "wa_id and password required"
                }, status=400)
            
            # Authenticate and get token
            token = await self.auth_service.authenticate_password(wa_id, password)
            
            if token:
                # Get WA details
                wa_cert = await self.auth_service.get_wa_by_id(wa_id)
                
                return web.json_response({
                    "status": "success",
                    "token": token,
                    "wa_id": wa_cert.wa_id,
                    "name": wa_cert.name,
                    "role": wa_cert.role,
                    "scopes": json.loads(wa_cert.scopes_json)
                })
            else:
                return web.json_response({
                    "error": "Invalid credentials"
                }, status=401)
                
        except Exception as e:
            logger.error(f"Login error: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def _handle_verify_token(self, request: web.Request) -> web.Response:
        """Verify a JWT token."""
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Get token from Authorization header
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return web.json_response({
                    "error": "Invalid authorization header"
                }, status=401)
            
            token = auth_header[7:]  # Remove 'Bearer ' prefix
            
            # Verify token
            claims = await self.auth_service.verify_token(token)
            
            if claims:
                return web.json_response({
                    "valid": True,
                    "claims": claims
                })
            else:
                return web.json_response({
                    "valid": False,
                    "error": "Invalid or expired token"
                }, status=401)
                
        except Exception as e:
            logger.error(f"Token verification error: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def _handle_link_discord(self, request: web.Request) -> web.Response:
        """Link Discord ID to WA certificate."""
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Verify caller has wa:admin scope
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return web.json_response({
                    "error": "Authorization required"
                }, status=401)
            
            token = auth_header[7:]
            claims = await self.auth_service.verify_token(token)
            
            if not claims or 'wa:admin' not in claims.get('scope', '').split():
                return web.json_response({
                    "error": "Insufficient permissions"
                }, status=403)
            
            # Get request data
            data = await request.json()
            wa_id = data.get('wa_id')
            discord_id = data.get('discord_id')
            
            if not wa_id or not discord_id:
                return web.json_response({
                    "error": "wa_id and discord_id required"
                }, status=400)
            
            # Update WA certificate
            success = await self.auth_service.link_discord(wa_id, discord_id)
            
            if success:
                return web.json_response({
                    "status": "success",
                    "message": f"Discord ID {discord_id} linked to WA {wa_id}"
                })
            else:
                return web.json_response({
                    "error": "Failed to link Discord ID"
                }, status=500)
                
        except Exception as e:
            logger.error(f"Discord link error: {e}")
            return web.json_response({
                "error": str(e)
            }, status=500)