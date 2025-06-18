"""API Authentication endpoints for OAuth and WA management."""
import logging
import json
from aiohttp import web
from typing import Any, Dict, Optional
from urllib.parse import urlencode
from datetime import datetime, timezone

logger = logging.getLogger(__name__)


class APIAuthRoutes:
    """Authentication routes for OAuth and WA management."""
    
    def __init__(self, runtime: Any) -> None:
        self.runtime = runtime
        self.auth_service: Optional[Any] = None
        self.oauth_service: Optional[Any] = None
        
    async def _ensure_services(self) -> bool:
        """Ensure auth services are available."""
        if not self.auth_service and hasattr(self.runtime, 'wa_auth_system'):
            wa_auth_system = self.runtime.wa_auth_system
            if wa_auth_system:
                self.auth_service = wa_auth_system.get_auth_service()
                self.oauth_service = wa_auth_system.get_oauth_service()
        
        return self.auth_service is not None and self.oauth_service is not None
    
    def register(self, app: web.Application) -> None:
        """Register auth routes with the application."""
        # OAuth endpoints
        app.router.add_get('/v1/auth/oauth/{provider}/start', self._handle_oauth_start)
        app.router.add_get('/v1/auth/oauth/{provider}/callback', self._handle_oauth_callback)
        
        # WA management endpoints
        app.router.add_post('/v1/auth/login', self._handle_login)
        app.router.add_get('/v1/auth/verify', self._handle_verify_token)
        app.router.add_post('/v1/wa/link-discord', self._handle_link_discord)
        
        # Agent creation endpoints
        app.router.add_post('/v1/agents/create', self._handle_create_agent)
        app.router.add_post('/v1/agents/{agent_id}/initialize', self._handle_initialize_agent)
        
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
            if not self.oauth_service:
                return web.json_response({
                    "error": "OAuth service not available"
                }, status=503)
            
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
            
            if not self.oauth_service:
                return web.json_response({
                    "error": "OAuth service not available"
                }, status=503)
            
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
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
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
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
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
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
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
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
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
    
    async def _handle_create_agent(self, request: web.Request) -> web.Response:
        """Create a new CIRIS agent (WA-only endpoint)."""
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Verify caller is a WA
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return web.json_response({
                    "error": "Authorization required"
                }, status=401)
            
            token = auth_header[7:]
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
            claims = await self.auth_service.verify_token(token)
            
            if not claims:
                return web.json_response({
                    "error": "Invalid or expired token"
                }, status=401)
            
            # Check if caller has wa:mint scope (for creating agents)
            scopes = claims.get('scope', '').split()
            if 'wa:mint' not in scopes:
                return web.json_response({
                    "error": "Insufficient permissions - wa:mint scope required"
                }, status=403)
            
            creator_wa_id = claims.get('sub')
            
            # Get request data
            data = await request.json()
            
            # Validate required fields
            required_fields = ['name', 'purpose', 'description', 'profile_template']
            missing_fields = [f for f in required_fields if not data.get(f)]
            if missing_fields:
                return web.json_response({
                    "error": f"Missing required fields: {', '.join(missing_fields)}"
                }, status=400)
            
            # Extract agent details
            agent_config = {
                "name": data['name'],
                "purpose": data['purpose'],
                "description": data['description'],
                "profile_template": data['profile_template'],  # Profile YAML as string
                "domain_specific_knowledge": data.get('domain_specific_knowledge', {}),
                "permitted_actions": data.get('permitted_actions', [
                    "OBSERVE", "SPEAK", "TOOL", "REJECT", "PONDER", "DEFER",
                    "MEMORIZE", "RECALL", "FORGET", "TASK_COMPLETE"
                ]),
                "creation_justification": data.get('creation_justification', 
                    f"Created by WA {creator_wa_id} via API"),
                "expected_capabilities": data.get('expected_capabilities', [
                    "communication", "memory", "observation", "tool_use",
                    "ethical_reasoning", "self_modification", "task_management"
                ]),
                "ethical_considerations": data.get('ethical_considerations',
                    "Agent will operate under CIRIS Covenant ethical framework")
            }
            
            # Generate unique agent ID
            import hashlib
            from datetime import datetime, timezone
            
            timestamp = datetime.now(timezone.utc)
            agent_id_base = f"{agent_config['name']}-{timestamp.isoformat()}"
            agent_id = hashlib.sha256(agent_id_base.encode()).hexdigest()[:12]
            full_agent_id = f"{agent_config['name'].lower()}-{agent_id}"
            
            # Create identity root structure
            from ciris_engine.schemas.identity_schemas_v1 import (
                AgentIdentityRoot, CoreProfile, IdentityMetadata
            )
            from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
            
            identity_hash = hashlib.sha256(
                f"{full_agent_id}:{agent_config['purpose']}:{agent_config['description']}".encode()
            ).hexdigest()
            
            identity_root = AgentIdentityRoot(
                agent_id=full_agent_id,
                identity_hash=identity_hash,
                core_profile=CoreProfile(
                    description=agent_config['description'],
                    role_description=agent_config['purpose'],
                    domain_specific_knowledge=agent_config['domain_specific_knowledge'],
                    dsdma_prompt_template=None,  # Optional field, can be customized later
                    last_shutdown_memory=None
                ),
                identity_metadata=IdentityMetadata(
                    created_at=timestamp.isoformat(),
                    last_modified=timestamp.isoformat(),
                    modification_count=0,
                    creator_agent_id=creator_wa_id,
                    lineage_trace=[creator_wa_id],
                    approval_required=True,
                    approved_by=creator_wa_id,  # WA self-approves
                    approval_timestamp=timestamp.isoformat()
                ),
                permitted_actions=[HandlerActionType(cap) for cap in agent_config['expected_capabilities']],
                restricted_capabilities=[
                    "identity_change_without_approval",
                    "profile_switching",
                    "unauthorized_data_access"
                ]
            )
            
            # Create database directory for new agent
            import os
            from pathlib import Path
            
            data_dir = Path(os.environ.get('CIRIS_DATA_DIR', './data'))
            agent_db_dir = data_dir / 'databases' / full_agent_id
            agent_db_dir.mkdir(parents=True, exist_ok=True)
            
            # Save profile template for initial creation
            profile_path = agent_db_dir / 'initial_profile.yaml'
            profile_path.write_text(agent_config['profile_template'])
            
            # Save identity metadata
            identity_path = agent_db_dir / 'identity_metadata.json'
            identity_path.write_text(json.dumps({
                "identity_root": identity_root.model_dump(),
                "creation_ceremony": {
                    "creator_wa_id": creator_wa_id,
                    "timestamp": timestamp.isoformat(),
                    "justification": agent_config['creation_justification'],
                    "api_created": True
                }
            }, indent=2))
            
            # Create response
            response = {
                "status": "success",
                "agent_id": full_agent_id,
                "identity_hash": identity_hash,
                "database_path": str(agent_db_dir),
                "creation_ceremony": {
                    "timestamp": timestamp.isoformat(),
                    "creator_wa_id": creator_wa_id,
                    "approved": True
                },
                "next_steps": [
                    f"Initialize agent with POST /v1/agents/{full_agent_id}/initialize",
                    "Start agent runtime with appropriate profile",
                    "Agent will create identity graph on first run"
                ],
                "profile_path": str(profile_path),
                "identity_metadata_path": str(identity_path)
            }
            
            # Log creation event
            logger.info(f"Agent {full_agent_id} created by WA {creator_wa_id} via API")
            
            return web.json_response(response)
            
        except Exception as e:
            logger.error(f"Agent creation error: {e}", exc_info=True)
            return web.json_response({
                "error": str(e)
            }, status=500)
    
    async def _handle_initialize_agent(self, request: web.Request) -> web.Response:
        """Initialize a newly created agent (creates identity in graph)."""
        agent_id = request.match_info['agent_id']
        
        if not await self._ensure_services():
            return web.json_response({
                "error": "Authentication services not available"
            }, status=503)
        
        try:
            # Verify caller is a WA
            auth_header = request.headers.get('Authorization', '')
            if not auth_header.startswith('Bearer '):
                return web.json_response({
                    "error": "Authorization required"
                }, status=401)
            
            token = auth_header[7:]
            if not self.auth_service:
                return web.json_response({
                    "error": "Auth service not available"
                }, status=503)
            
            claims = await self.auth_service.verify_token(token)
            
            if not claims or 'wa:mint' not in claims.get('scope', '').split():
                return web.json_response({
                    "error": "Insufficient permissions"
                }, status=403)
            
            # Check if agent metadata exists
            from pathlib import Path
            import os
            
            data_dir = Path(os.environ.get('CIRIS_DATA_DIR', './data'))
            agent_db_dir = data_dir / 'databases' / agent_id
            identity_path = agent_db_dir / 'identity_metadata.json'
            
            if not identity_path.exists():
                return web.json_response({
                    "error": f"Agent {agent_id} not found or not created via API"
                }, status=404)
            
            # Load identity metadata
            identity_data = json.loads(identity_path.read_text())
            
            # Mark as initialized
            identity_data['initialized'] = True
            identity_data['initialization_timestamp'] = datetime.now(timezone.utc).isoformat()
            
            # Save updated metadata
            identity_path.write_text(json.dumps(identity_data, indent=2))
            
            return web.json_response({
                "status": "success",
                "agent_id": agent_id,
                "initialized": True,
                "message": "Agent initialized and ready to start",
                "startup_command": f"python main.py --profile {agent_id} --modes api,discord"
            })
            
        except Exception as e:
            logger.error(f"Agent initialization error: {e}", exc_info=True)
            return web.json_response({
                "error": str(e)
            }, status=500)