"""WA Authentication Service - Core authentication logic implementation."""

import json
import os
import sqlite3
import hashlib
import secrets
import base64
import time
import asyncio
import functools
import inspect
import logging
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, timezone
from pathlib import Path

import jwt
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.exceptions import InvalidSignature

from ciris_engine.schemas.wa_schemas_v1 import (
    WACertificate, ChannelIdentity, 
    AuthorizationContext, WARole, TokenType, JWTSubType
)
from ciris_engine.protocols.wa_auth_interface import (
    WAStore, JWTService, WACrypto, WAAuthMiddleware
)

logger = logging.getLogger(__name__)


class WAAuthService(WAStore, JWTService, WACrypto, WAAuthMiddleware):
    """Comprehensive WA Authentication Service implementing all auth protocols."""
    
    def __init__(self, db_path: str, key_dir: Optional[str] = None):
        """Initialize the WA Authentication Service.
        
        Args:
            db_path: Path to SQLite database
            key_dir: Directory for key storage (defaults to ~/.ciris/)
        """
        self.db_path = db_path
        self.key_dir = Path(key_dir or os.path.expanduser("~/.ciris"))
        self.key_dir.mkdir(mode=0o700, exist_ok=True)
        
        # Initialize gateway secret
        self.gateway_secret = self._get_or_create_gateway_secret()
        
        # Cache for tokens and WAs
        self._token_cache: Dict[str, AuthorizationContext] = {}
        self._channel_token_cache: Dict[str, str] = {}
        
        # Initialize database
        self._init_database()
    
    @staticmethod
    def _encode_public_key(pubkey_bytes: bytes) -> str:
        """Encode public key using base64url without padding."""
        return base64.urlsafe_b64encode(pubkey_bytes).decode().rstrip('=')
    
    @staticmethod
    def _decode_public_key(pubkey_str: str) -> bytes:
        """Decode base64url encoded public key, adding padding if needed."""
        # Add padding if necessary
        padding = 4 - (len(pubkey_str) % 4)
        if padding != 4:
            pubkey_str += '=' * padding
        return base64.urlsafe_b64decode(pubkey_str)
    
    def _get_or_create_gateway_secret(self) -> bytes:
        """Get or create the gateway secret for JWT signing."""
        secret_path = self.key_dir / "gateway.secret"
        
        if secret_path.exists():
            return secret_path.read_bytes()
        
        # Generate new 32-byte secret
        secret = secrets.token_bytes(32)
        secret_path.write_bytes(secret)
        secret_path.chmod(0o600)
        return secret
    
    def _init_database(self) -> None:
        """Initialize database tables if needed."""
        # Import the table definition
        from ciris_engine.schemas.db_tables_v1 import wa_cert_table_v1
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA foreign_keys = ON")
            conn.executescript(wa_cert_table_v1)
            conn.commit()
    
    # WAStore Protocol Implementation
    
    async def get_wa(self, wa_id: str) -> Optional[WACertificate]:
        """Get WA certificate by ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM wa_cert WHERE wa_id = ? AND active = 1", 
                (wa_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return WACertificate(**dict(row))
            return None
    
    async def get_wa_by_kid(self, jwt_kid: str) -> Optional[WACertificate]:
        """Get WA certificate by JWT key ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM wa_cert WHERE jwt_kid = ? AND active = 1", 
                (jwt_kid,)
            )
            row = cursor.fetchone()
            
            if row:
                return WACertificate(**dict(row))
            return None
    
    async def get_wa_by_oauth(self, provider: str, external_id: str) -> Optional[WACertificate]:
        """Get WA certificate by OAuth identity."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM wa_cert WHERE oauth_provider = ? AND oauth_external_id = ? AND active = 1",
                (provider, external_id)
            )
            row = cursor.fetchone()
            
            if row:
                return WACertificate(**dict(row))
            return None
    
    async def get_wa_by_adapter(self, adapter_id: str) -> Optional[WACertificate]:
        """Get WA certificate by adapter ID."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM wa_cert WHERE adapter_id = ? AND active = 1",
                (adapter_id,)
            )
            row = cursor.fetchone()
            
            if row:
                return WACertificate(**dict(row))
            return None
    
    async def create_wa(self, wa: WACertificate) -> None:
        """Store new WA certificate."""
        with sqlite3.connect(self.db_path) as conn:
            # Convert WA to dict for insertion
            wa_dict = wa.model_dump()
            wa_dict['created'] = wa_dict['created'].isoformat() if isinstance(wa_dict['created'], datetime) else wa_dict['created']
            if wa_dict.get('last_login'):
                wa_dict['last_login'] = wa_dict['last_login'].isoformat() if isinstance(wa_dict['last_login'], datetime) else wa_dict['last_login']
            
            # Convert boolean to integer for SQLite
            wa_dict['active'] = int(wa_dict['active'])
            wa_dict['auto_minted'] = int(wa_dict['auto_minted'])
            
            columns = ', '.join(wa_dict.keys())
            placeholders = ', '.join(['?' for _ in wa_dict])
            
            conn.execute(
                f"INSERT INTO wa_cert ({columns}) VALUES ({placeholders})",
                list(wa_dict.values())
            )
            conn.commit()
    
    async def create_adapter_observer(self, adapter_id: str, name: str) -> WACertificate:
        """Create or reactivate adapter observer WA."""
        # Check if observer already exists
        existing = await self.get_wa_by_adapter(adapter_id)
        if existing:
            # Reactivate if needed
            if not existing.active:
                await self.update_wa(existing.wa_id, active=True)
                existing.active = True
            return existing
        
        # Generate new observer WA
        private_key, public_key = self.generate_keypair()
        timestamp = datetime.now(timezone.utc)
        wa_id = self.generate_wa_id(timestamp)
        jwt_kid = f"wa-jwt-{wa_id[-6:].lower()}"
        
        observer = WACertificate(
            wa_id=wa_id,
            name=name,
            role=WARole.OBSERVER,
            pubkey=self._encode_public_key(public_key),
            jwt_kid=jwt_kid,
            scopes_json='["read:any", "write:message"]',
            adapter_id=adapter_id,
            token_type=TokenType.CHANNEL,
            created=timestamp,
            active=True
        )
        
        await self.create_wa(observer)
        return observer
    
    
    async def update_wa(self, wa_id: str, **updates: Any) -> None:
        """Update WA certificate fields."""
        if not updates:
            return
        
        # Handle datetime fields
        for key, value in updates.items():
            if isinstance(value, datetime):
                updates[key] = value.isoformat()
        
        set_clause = ', '.join([f"{key} = ?" for key in updates.keys()])
        values = list(updates.values()) + [wa_id]
        
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                f"UPDATE wa_cert SET {set_clause} WHERE wa_id = ?",
                values
            )
            conn.commit()
    
    async def revoke_wa(self, wa_id: str, revoked_by: str, reason: str) -> None:
        """Revoke WA certificate."""
        await self.update_wa(wa_id, active=False)
        # TODO: Add audit log entry for revocation using revoked_by and reason
        _ = (revoked_by, reason)  # Parameters reserved for audit logging
    
    async def list_all_was(self, active_only: bool = True) -> List[WACertificate]:
        """List all WA certificates."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            
            query = "SELECT * FROM wa_cert"
            params: List[Any] = []
            
            if active_only:
                query += " WHERE active = 1"
            
            query += " ORDER BY created DESC"
            
            cursor = conn.execute(query, params)
            rows = cursor.fetchall()
            
            return [WACertificate(**dict(row)) for row in rows]
    
    async def update_last_login(self, wa_id: str) -> None:
        """Update last login timestamp."""
        await self.update_wa(wa_id, last_login=datetime.now(timezone.utc))
    
    # JWTService Protocol Implementation
    
    def create_channel_token(self, wa: WACertificate) -> str:
        """Create non-expiring channel observer token."""
        payload = {
            'sub': wa.wa_id,
            'sub_type': JWTSubType.ANON.value,
            'name': wa.name,
            'scope': wa.scopes,
            'iat': int(time.time()),
            'adapter': wa.adapter_id
        }
        
        return jwt.encode(
            payload,
            self.gateway_secret,
            algorithm='HS256',
            headers={'kid': wa.jwt_kid}
        )
    
    def create_gateway_token(self, wa: WACertificate, expires_hours: int = 8) -> str:
        """Create gateway-signed token (OAuth/password auth)."""
        now = int(time.time())
        
        payload = {
            'sub': wa.wa_id,
            'sub_type': JWTSubType.OAUTH.value if wa.oauth_provider else JWTSubType.USER.value,
            'name': wa.name,
            'scope': wa.scopes,
            'iat': now,
            'exp': now + (expires_hours * 3600)
        }
        
        if wa.oauth_provider:
            payload['oauth_provider'] = wa.oauth_provider
        
        return jwt.encode(
            payload,
            self.gateway_secret,
            algorithm='HS256',
            headers={'kid': wa.jwt_kid}
        )
    
    def create_authority_token(self, wa: WACertificate, private_key: bytes) -> str:
        """Create WA-signed authority token."""
        now = int(time.time())
        
        payload = {
            'sub': wa.wa_id,
            'sub_type': JWTSubType.AUTHORITY.value,
            'name': wa.name,
            'scope': wa.scopes,
            'iat': now,
            'exp': now + (24 * 3600)  # 24 hours
        }
        
        # Load Ed25519 private key
        signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        
        return jwt.encode(
            payload,
            signing_key,
            algorithm='EdDSA',
            headers={'kid': wa.jwt_kid}
        )
    
    async def verify_token(self, token: str) -> Optional[AuthorizationContext]:
        """Verify any JWT token and return auth context."""
        try:
            # Decode header to get kid
            header = jwt.get_unverified_header(token)
            kid = header.get('kid')
            
            if not kid:
                return None
            
            # Get WA by kid
            wa = await self.get_wa_by_kid(kid)
            if not wa:
                return None
            
            # Determine verification key based on token type
            payload = jwt.decode(token, options={"verify_signature": False})
            sub_type = payload.get('sub_type')
            
            if sub_type in [JWTSubType.ANON.value, JWTSubType.OAUTH.value, JWTSubType.USER.value]:
                # Gateway-signed tokens
                decoded = jwt.decode(token, self.gateway_secret, algorithms=['HS256'])
            elif sub_type == JWTSubType.AUTHORITY.value:
                # WA-signed tokens - need to load public key
                public_key_bytes = self._decode_public_key(wa.pubkey)
                public_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
                decoded = jwt.decode(token, public_key, algorithms=['EdDSA'])
            else:
                return None
            
            # Create authorization context
            context = AuthorizationContext(
                wa_id=decoded['sub'],
                name=decoded['name'],
                role=wa.role,
                scopes=decoded['scope'],
                token_type=JWTSubType(decoded['sub_type']),
                channel_id=decoded.get('channel'),
                oauth_provider=decoded.get('oauth_provider')
            )
            
            # Update last login
            await self.update_last_login(wa.wa_id)
            
            return context
            
        except jwt.InvalidTokenError:
            return None
        except Exception:
            return None
    
    # WACrypto Protocol Implementation
    
    def generate_keypair(self) -> tuple[bytes, bytes]:
        """Generate Ed25519 keypair (private, public)."""
        private_key = ed25519.Ed25519PrivateKey.generate()
        public_key = private_key.public_key()
        
        private_bytes = private_key.private_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PrivateFormat.Raw,
            encryption_algorithm=serialization.NoEncryption()
        )
        
        public_bytes = public_key.public_bytes(
            encoding=serialization.Encoding.Raw,
            format=serialization.PublicFormat.Raw
        )
        
        return private_bytes, public_bytes
    
    def sign_data(self, data: bytes, private_key: bytes) -> str:
        """Sign data with Ed25519 private key."""
        signing_key = ed25519.Ed25519PrivateKey.from_private_bytes(private_key)
        signature = signing_key.sign(data)
        return base64.b64encode(signature).decode()
    
    def verify_signature(self, data: bytes, signature: str, public_key: str) -> bool:
        """Verify Ed25519 signature."""
        try:
            public_key_bytes = self._decode_public_key(public_key)
            verify_key = ed25519.Ed25519PublicKey.from_public_bytes(public_key_bytes)
            signature_bytes = base64.b64decode(signature)
            
            verify_key.verify(signature_bytes, data)
            return True
        except (InvalidSignature, Exception):
            return False
    
    def generate_wa_id(self, timestamp: datetime) -> str:
        """Generate deterministic WA ID."""
        date_str = timestamp.strftime("%Y-%m-%d")
        random_suffix = secrets.token_hex(3).upper()
        return f"wa-{date_str}-{random_suffix}"
    
    def hash_password(self, password: str) -> str:
        """Hash password using PBKDF2."""
        salt = secrets.token_bytes(32)
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        return base64.b64encode(salt + key).decode()
    
    def verify_password(self, password: str, hash: str) -> bool:
        """Verify password against hash."""
        try:
            decoded = base64.b64decode(hash)
            salt = decoded[:32]
            stored_key = decoded[32:]
            
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=salt,
                iterations=100000,
            )
            key = kdf.derive(password.encode())
            return key == stored_key
        except Exception:
            return False
    
    def generate_api_key(self, wa_id: str) -> str:
        """Generate API key for WA."""
        # Include wa_id in key derivation for uniqueness
        key_material = f"{wa_id}:{secrets.token_hex(32)}"
        return hashlib.sha256(key_material.encode()).hexdigest()
    
    # WAAuthMiddleware Protocol Implementation
    
    async def authenticate(self, token: Optional[str]) -> Optional[AuthorizationContext]:
        """Authenticate request and return auth context."""
        if not token:
            return None
        
        # Check cache first
        if token in self._token_cache:
            return self._token_cache[token]
        
        # Verify token
        context = await self.verify_token(token)
        
        # Cache valid tokens
        if context:
            self._token_cache[token] = context
        
        return context
    
    def require_scope(self, scope: str) -> Any:
        """Decorator to require specific scope for endpoint."""
        def decorator(func: Any) -> Any:
            def wrapper(*args: Any, **kwargs: Any) -> Any:
                # This would be implemented in the actual middleware
                # For now, it's a placeholder
                return func(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_wa_auth(self, scope: str) -> Any:
        """Decorator to require WA authentication with specific scope.
        
        This decorator checks for authentication tokens in the following order:
        1. 'token' parameter in the function arguments
        2. 'auth_context' in the function arguments
        3. Token from the context (if available)
        
        Args:
            scope: The required scope for accessing the decorated function
            
        Returns:
            Decorated function that enforces authentication
        """
        def decorator(func: Any) -> Any:
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # Extract token from various sources
                token = None
                auth_context = None
                
                # Check if 'token' is in kwargs
                if 'token' in kwargs:
                    token = kwargs.get('token')
                
                # Check if 'auth_context' is already provided
                if 'auth_context' in kwargs:
                    auth_context = kwargs.get('auth_context')
                
                # If no auth context yet, try to verify the token
                if not auth_context and token:
                    auth_context = await self.verify_token(token)
                
                # Check if authentication succeeded
                if not auth_context:
                    raise ValueError("Authentication required: No valid token provided")
                
                # Verify the required scope
                if not auth_context.has_scope(scope):
                    raise ValueError(
                        f"Insufficient permissions: Requires scope '{scope}', "
                        f"but user has scopes: {auth_context.scopes}"
                    )
                
                # Check if the function accepts auth_context parameter
                sig = inspect.signature(func)
                
                # If function has **kwargs or auth_context parameter, pass it
                if 'auth_context' in sig.parameters or any(
                    p.kind == inspect.Parameter.VAR_KEYWORD 
                    for p in sig.parameters.values()
                ):
                    kwargs['auth_context'] = auth_context
                
                # Call the original function
                return await func(*args, **kwargs)
            
            def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
                # For synchronous functions, we need to handle auth differently
                # This is a simplified version that expects auth_context to be pre-verified
                auth_context = kwargs.get('auth_context')
                
                if not auth_context:
                    raise ValueError("Authentication required: No auth_context provided")
                
                # Verify the required scope
                if not hasattr(auth_context, 'has_scope') or not auth_context.has_scope(scope):
                    raise ValueError(
                        f"Insufficient permissions: Requires scope '{scope}'"
                    )
                
                return func(*args, **kwargs)
            
            # Preserve function metadata and check if the function is async
            if asyncio.iscoroutinefunction(func):
                wrapper = functools.wraps(func)(async_wrapper)
            else:
                wrapper = functools.wraps(func)(sync_wrapper)
            
            # Add metadata to indicate this function requires authentication
            setattr(wrapper, '_requires_wa_auth', True)
            setattr(wrapper, '_required_scope', scope)
            
            return wrapper
        return decorator
    
    def get_adapter_token(self, adapter_id: str) -> Optional[str]:
        """Get cached adapter token."""
        return self._channel_token_cache.get(adapter_id)
    
    # Additional helper methods
    
    async def bootstrap_if_needed(self) -> None:
        """Bootstrap the system if no WAs exist."""
        was = await self.list_all_was()
        if not was:
            # Load and insert root certificate
            seed_path = Path(__file__).parent.parent.parent / "seed" / "root_pub.json"
            if seed_path.exists():
                with open(seed_path) as f:
                    root_data = json.load(f)
                
                # Convert created timestamp
                root_data['created'] = datetime.fromisoformat(root_data['created'].replace('Z', '+00:00'))
                
                root_wa = WACertificate(**root_data)
                await self.create_wa(root_wa)
    
    async def create_channel_token_for_adapter(self, adapter_type: str, adapter_info: dict) -> str:
        """Create a channel token for an adapter."""
        # Ensure adapter_info has proper structure
        if not adapter_info:
            adapter_info = {}
        
        # Add default instance_id if not present
        if 'instance_id' not in adapter_info:
            adapter_info['instance_id'] = 'default'
            
        channel_identity = ChannelIdentity.from_adapter(adapter_type, adapter_info)
        
        # Create or get adapter observer
        observer = await self.create_adapter_observer(
            channel_identity.adapter_id,
            f"{adapter_type}_observer"
        )
        
        # Generate token
        token = self.create_channel_token(observer)
        
        # Cache the token
        self._channel_token_cache[channel_identity.adapter_id] = token
        
        return token