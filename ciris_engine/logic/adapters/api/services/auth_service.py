"""Authentication service for API v2.0.

Manages API keys, OAuth users, and authentication state.
"""
import hashlib
import secrets
import base64
from typing import Optional, List, Dict, Any
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass

from ciris_engine.schemas.api.auth import UserRole, APIKeyInfo
from ciris_engine.schemas.services.authority_core import WARole
from ciris_engine.schemas.runtime.api import APIRole
from ciris_engine.schemas.services.authority.wise_authority import WAUpdate
from ciris_engine.protocols.services.infrastructure.authentication import AuthenticationServiceProtocol

@dataclass
class StoredAPIKey:
    """Internal representation of an API key."""
    key_id: str  # Unique ID for the key
    key_hash: str
    key_value: str  # Masked version for display
    user_id: str
    role: UserRole
    expires_at: Optional[datetime]
    description: Optional[str]
    created_at: datetime
    created_by: str
    last_used: Optional[datetime]
    is_active: bool

@dataclass
class OAuthUser:
    """OAuth user information."""
    user_id: str  # Format: provider:external_id
    provider: str
    external_id: str
    email: Optional[str]
    name: Optional[str]
    role: UserRole
    created_at: datetime
    last_login: datetime

@dataclass
class User:
    """Unified user representation combining auth methods and WA status."""
    wa_id: str  # Primary ID (from WA cert)
    name: str
    auth_type: str  # "password", "oauth", "api_key"
    api_role: APIRole
    wa_role: Optional[WARole] = None
    oauth_provider: Optional[str] = None
    oauth_email: Optional[str] = None
    oauth_external_id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    wa_parent_id: Optional[str] = None
    wa_auto_minted: bool = False
    password_hash: Optional[str] = None
    custom_permissions: Optional[List[str]] = None  # Additional permissions beyond role defaults

class APIAuthService:
    """Simple in-memory authentication service with database persistence."""

    def __init__(self, auth_service: Optional[AuthenticationServiceProtocol] = None) -> None:
        # In-memory caches for performance
        self._api_keys: Dict[str, StoredAPIKey] = {}
        self._oauth_users: Dict[str, OAuthUser] = {}
        self._users: Dict[str, User] = {}
        
        # Store reference to the actual authentication service
        self._auth_service = auth_service
        
        # Load existing users from database on startup
        if self._auth_service:
            self._load_users_from_db()
        else:
            # Fallback: Initialize with system admin user if no auth service
            now = datetime.now(timezone.utc)
            admin_user = User(
                wa_id="wa-system-admin",
                name="admin",
                auth_type="password",
                api_role=APIRole.SYSTEM_ADMIN,
                wa_role=None,  # System admin is not a WA by default
                created_at=now,
                is_active=True,
                password_hash=self._hash_password("ciris_admin_password")
            )
            self._users[admin_user.wa_id] = admin_user
    
    def _load_users_from_db(self) -> None:
        """Load existing users from the database."""
        import asyncio
        
        if not self._auth_service:
            return
            
        try:
            # Get all WA certificates from the database
            was = asyncio.run(self._auth_service.list_was(active_only=False))
            
            for wa in was:
                # Convert WA certificate to User
                user = User(
                    wa_id=wa.wa_id,
                    name=wa.name,
                    auth_type="password" if wa.password_hash else "certificate",
                    api_role=self._wa_role_to_api_role(wa.role),
                    wa_role=wa.role,
                    created_at=wa.created_at,
                    last_login=wa.last_auth,
                    is_active=True,  # Assume active if in database
                    wa_parent_id=wa.parent_wa_id,
                    wa_auto_minted=wa.auto_minted,
                    password_hash=wa.password_hash,
                    custom_permissions=wa.custom_permissions if hasattr(wa, 'custom_permissions') else None
                )
                self._users[user.wa_id] = user
            
            # If no admin user exists, create the default one
            if not any(u.name == "admin" for u in self._users.values()):
                asyncio.run(self._create_default_admin())
                
        except Exception as e:
            print(f"Error loading users from database: {e}")
            # Fall back to in-memory admin
            now = datetime.now(timezone.utc)
            admin_user = User(
                wa_id="wa-system-admin",
                name="admin",
                auth_type="password",
                api_role=APIRole.SYSTEM_ADMIN,
                wa_role=None,
                created_at=now,
                is_active=True,
                password_hash=self._hash_password("ciris_admin_password")
            )
            self._users[admin_user.wa_id] = admin_user
    
    async def _create_default_admin(self) -> None:
        """Create the default admin user in the database."""
        if not self._auth_service:
            return
            
        try:
            # Create admin WA certificate
            wa_cert = await self._auth_service.create_wa(
                name="admin",
                email="admin@ciris.local",
                scopes=["*"],  # All permissions
                role=WARole.ROOT  # System admin gets ROOT role
            )
            
            # Update with password hash
            await self._auth_service.update_wa(
                wa_cert.wa_id,
                updates=None,
                password_hash=self._hash_password("ciris_admin_password")
            )
            
            # Add to cache
            admin_user = User(
                wa_id=wa_cert.wa_id,
                name="admin",
                auth_type="password",
                api_role=APIRole.SYSTEM_ADMIN,
                wa_role=WARole.ROOT,
                created_at=wa_cert.created_at,
                is_active=True,
                password_hash=self._hash_password("ciris_admin_password")
            )
            self._users[admin_user.wa_id] = admin_user
            
        except Exception as e:
            print(f"Error creating default admin: {e}")
    
    def _wa_role_to_api_role(self, wa_role: Optional[WARole]) -> APIRole:
        """Convert WA role to API role."""
        if not wa_role:
            return APIRole.OBSERVER
        
        role_map = {
            WARole.ROOT: APIRole.SYSTEM_ADMIN,
            WARole.AUTHORITY: APIRole.AUTHORITY,
            WARole.OBSERVER: APIRole.OBSERVER
        }
        return role_map.get(wa_role, APIRole.OBSERVER)

    def _hash_key(self, api_key: str) -> str:
        """Hash an API key for storage."""
        return hashlib.sha256(api_key.encode()).hexdigest()

    def _get_key_id(self, api_key: str) -> str:
        """Extract key ID from full API key."""
        # Key format: ciris_role_randomstring
        # Key ID is first 8 chars of the hash
        return self._hash_key(api_key)[:8]

    async def store_api_key(
        self,
        key: str,
        user_id: str,
        role: UserRole,
        expires_at: Optional[datetime] = None,
        description: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> None:
        """Store a new API key."""
        key_hash = self._hash_key(key)
        key_id = self._get_key_id(key)
        stored_key = StoredAPIKey(
            key_id=key_id,
            key_hash=key_hash,
            key_value=key[:12] + "..." + key[-4:],  # Masked version
            user_id=user_id,
            role=role,
            expires_at=expires_at,
            description=description,
            created_at=datetime.now(timezone.utc),
            created_by=created_by or user_id,
            last_used=None,
            is_active=True
        )
        self._api_keys[key_hash] = stored_key

    async def validate_api_key(self, api_key: str) -> Optional[StoredAPIKey]:
        """Validate an API key and return its info."""
        key_hash = self._hash_key(api_key)
        stored_key = self._api_keys.get(key_hash)

        if not stored_key or not stored_key.is_active:
            return None

        # Check expiration
        if stored_key.expires_at and stored_key.expires_at < datetime.now(timezone.utc):
            return None

        # Update last used
        stored_key.last_used = datetime.now(timezone.utc)
        
        # Ensure system admin user exists in _users
        if stored_key.user_id == "wa-system-admin" and stored_key.user_id not in self._users:
            # Re-create the system admin user
            admin_user = User(
                wa_id="wa-system-admin",
                name="admin",
                auth_type="password",
                api_role=APIRole.SYSTEM_ADMIN,
                wa_role=None,
                created_at=datetime.now(timezone.utc),
                is_active=True,
                password_hash=self._hash_password("ciris_admin_password")
            )
            self._users[admin_user.wa_id] = admin_user

        return stored_key


    async def revoke_api_key(self, key_id: str) -> None:
        """Revoke an API key."""
        # Find key by partial hash
        for key_hash, stored_key in self._api_keys.items():
            if key_hash.startswith(key_id):
                stored_key.is_active = False
                return

    async def create_oauth_user(
        self,
        provider: str,
        external_id: str,
        email: Optional[str],
        name: Optional[str],
        role: UserRole
    ) -> OAuthUser:
        """Create or update an OAuth user."""
        user_id = f"{provider}:{external_id}"
        now = datetime.now(timezone.utc)

        if user_id in self._oauth_users:
            # Update existing user
            user = self._oauth_users[user_id]
            user.last_login = now
            if email:
                user.email = email
            if name:
                user.name = name
        else:
            # Create new user
            user = OAuthUser(
                user_id=user_id,
                provider=provider,
                external_id=external_id,
                email=email,
                name=name,
                role=role,
                created_at=now,
                last_login=now
            )
            self._oauth_users[user_id] = user

        return user

    # ========== User Management Methods ==========
    
    def _hash_password(self, password: str) -> str:
        """Hash a password for storage."""
        # In production, use bcrypt or argon2
        return hashlib.sha256(password.encode()).hexdigest()
    
    async def get_user_by_username(self, username: str) -> Optional[User]:
        """Get a user by username."""
        for user in self._users.values():
            if user.name == username:
                return user
        return None
    
    async def create_user(
        self, 
        username: str, 
        password: str, 
        api_role: APIRole = APIRole.OBSERVER
    ) -> Optional[User]:
        """Create a new user account."""
        # Check if username already exists
        existing = await self.get_user_by_username(username)
        if existing:
            return None
        
        # Map API role to WA role
        wa_role_map = {
            APIRole.SYSTEM_ADMIN: WARole.ROOT,
            APIRole.AUTHORITY: WARole.AUTHORITY,
            APIRole.ADMIN: WARole.AUTHORITY,  # Admin also gets AUTHORITY
            APIRole.OBSERVER: WARole.OBSERVER
        }
        wa_role = wa_role_map.get(api_role, WARole.OBSERVER)
        
        # If we have an auth service, create in database
        if self._auth_service:
            try:
                # Create WA certificate
                wa_cert = await self._auth_service.create_wa(
                    name=username,
                    email=f"{username}@ciris.local",
                    scopes=self.get_permissions_for_role(api_role),
                    role=wa_role
                )
                
                # Update with password hash
                await self._auth_service.update_wa(
                    wa_cert.wa_id,
                    updates=None,
                    password_hash=self._hash_password(password)
                )
                
                # Create user object
                user = User(
                    wa_id=wa_cert.wa_id,
                    name=username,
                    auth_type="password",
                    api_role=api_role,
                    wa_role=wa_role,
                    created_at=wa_cert.created_at,
                    is_active=True,
                    password_hash=self._hash_password(password)
                )
                
                # Store in cache
                self._users[wa_cert.wa_id] = user
                return user
                
            except Exception as e:
                print(f"Error creating user in database: {e}")
                # Fall through to in-memory creation
        
        # Fallback: in-memory only
        user_id = f"wa-user-{secrets.token_hex(8)}"
        now = datetime.now(timezone.utc)
        user = User(
            wa_id=user_id,
            name=username,
            auth_type="password",
            api_role=api_role,
            created_at=now,
            is_active=True,
            password_hash=self._hash_password(password)
        )
        
        # Store user
        self._users[user_id] = user
        
        return user
    
    async def list_users(
        self,
        search: Optional[str] = None,
        auth_type: Optional[str] = None,
        api_role: Optional[APIRole] = None,
        wa_role: Optional[WARole] = None,
        is_active: Optional[bool] = None
    ) -> List[User]:
        """List all users with optional filtering."""
        users = []
        
        # Add all stored users
        for user in self._users.values():
            # Apply filters
            if search and search.lower() not in user.name.lower():
                continue
            if auth_type and user.auth_type != auth_type:
                continue
            if api_role and user.api_role != api_role:
                continue
            if wa_role and user.wa_role != wa_role:
                continue
            if is_active is not None and user.is_active != is_active:
                continue
            
            users.append(user)
        
        # Add OAuth users not in _users
        for oauth_user in self._oauth_users.values():
            # Check if already in users
            if any(u.oauth_external_id == oauth_user.external_id for u in users):
                continue
            
            # Convert OAuth user to User
            user = User(
                wa_id=oauth_user.user_id,
                name=oauth_user.name or oauth_user.email or oauth_user.user_id,
                auth_type="oauth",
                api_role=self._user_role_to_api_role(oauth_user.role),
                oauth_provider=oauth_user.provider,
                oauth_email=oauth_user.email,
                oauth_external_id=oauth_user.external_id,
                created_at=oauth_user.created_at,
                last_login=oauth_user.last_login,
                is_active=True
            )
            
            # Apply filters
            if search and search.lower() not in user.name.lower():
                continue
            if auth_type and user.auth_type != auth_type:
                continue
            if api_role and user.api_role != api_role:
                continue
            if wa_role is not None:
                continue  # OAuth users without WA role
            if is_active is not None and user.is_active != is_active:
                continue
            
            users.append(user)
        
        return sorted(users, key=lambda u: u.created_at or datetime.min, reverse=True)
    
    def _user_role_to_api_role(self, role: UserRole) -> APIRole:
        """Convert UserRole to APIRole."""
        mapping = {
            UserRole.OBSERVER: APIRole.OBSERVER,
            UserRole.ADMIN: APIRole.ADMIN,
            UserRole.SYSTEM_ADMIN: APIRole.SYSTEM_ADMIN
        }
        return mapping.get(role, APIRole.OBSERVER)
    
    async def get_user(self, user_id: str) -> Optional[User]:
        """Get a specific user by ID."""
        # Check stored users first
        if user_id in self._users:
            return self._users[user_id]
        
        # Check OAuth users
        if user_id in self._oauth_users:
            oauth_user = self._oauth_users[user_id]
            return User(
                wa_id=oauth_user.user_id,
                name=oauth_user.name or oauth_user.email or oauth_user.user_id,
                auth_type="oauth",
                api_role=self._user_role_to_api_role(oauth_user.role),
                oauth_provider=oauth_user.provider,
                oauth_email=oauth_user.email,
                oauth_external_id=oauth_user.external_id,
                created_at=oauth_user.created_at,
                last_login=oauth_user.last_login,
                is_active=True
            )
        
        return None
    
    async def update_user(
        self,
        user_id: str,
        api_role: Optional[APIRole] = None,
        is_active: Optional[bool] = None
    ) -> Optional[User]:
        """Update user information."""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # Update fields
        if api_role is not None:
            user.api_role = api_role
            # Also update WA role to match
            wa_role_map = {
                APIRole.SYSTEM_ADMIN: WARole.ROOT,
                APIRole.AUTHORITY: WARole.AUTHORITY,
                APIRole.ADMIN: WARole.AUTHORITY,  # Admin also gets AUTHORITY
                APIRole.OBSERVER: WARole.OBSERVER
            }
            user.wa_role = wa_role_map.get(api_role, WARole.OBSERVER)
        if is_active is not None:
            user.is_active = is_active
        
        # Store updated user
        self._users[user_id] = user
        
        # Also update in database if we have auth service
        if self._auth_service:
            try:
                # Update role in database
                if api_role is not None and user.wa_role:
                    await self._auth_service.update_wa(
                        user_id, 
                        updates=WAUpdate(role=user.wa_role.value if hasattr(user.wa_role, 'value') else str(user.wa_role))
                    )
                
                # Update active status in database
                if is_active is not None:
                    if is_active:
                        # Reactivate - note: this may not work if cert was revoked
                        await self._auth_service.update_wa(
                            user_id,
                            updates=WAUpdate(is_active=True)
                        )
                    else:
                        # Deactivate
                        await self._auth_service.revoke_wa(user_id, reason="User deactivated via API")
            except Exception as e:
                print(f"Error updating user in database: {e}")
        
        # Also update OAuth user if applicable
        if user_id in self._oauth_users:
            oauth_user = self._oauth_users[user_id]
            if api_role is not None:
                # Convert APIRole back to UserRole
                role_mapping = {
                    APIRole.OBSERVER: UserRole.OBSERVER,
                    APIRole.ADMIN: UserRole.ADMIN,
                    APIRole.AUTHORITY: UserRole.ADMIN,  # No direct mapping
                    APIRole.SYSTEM_ADMIN: UserRole.SYSTEM_ADMIN
                }
                oauth_user.role = role_mapping.get(api_role, UserRole.OBSERVER)
        
        return user
    
    async def change_password(
        self,
        user_id: str,
        new_password: str,
        current_password: Optional[str] = None,
        skip_current_check: bool = False
    ) -> bool:
        """Change user password."""
        user = await self.get_user(user_id)
        if not user or user.auth_type != "password":
            return False
        
        # Verify current password unless skip_current_check is True
        if not skip_current_check and current_password:
            current_hash = self._hash_password(current_password)
            if user.password_hash != current_hash:
                return False
        
        # Update password
        user.password_hash = self._hash_password(new_password)
        self._users[user_id] = user
        
        # Also update in database if we have auth service
        if self._auth_service:
            try:
                import asyncio
                asyncio.run(self._auth_service.update_wa(
                    user_id,
                    updates=None,
                    password_hash=self._hash_password(new_password)
                ))
            except Exception as e:
                print(f"Error updating password in database: {e}")
        
        return True
    
    async def deactivate_user(self, user_id: str) -> bool:
        """Deactivate a user account."""
        user = await self.get_user(user_id)
        if not user:
            return False
        
        user.is_active = False
        self._users[user_id] = user
        
        # Also update in database if we have auth service
        if self._auth_service:
            try:
                await self._auth_service.revoke_wa(user_id)
            except Exception as e:
                print(f"Error deactivating user in database: {e}")
        
        # Also deactivate OAuth user if applicable
        if user_id in self._oauth_users:
            # Can't really deactivate OAuth users in this simple implementation
            pass
        
        return True
    
    def get_permissions_for_role(self, role: APIRole) -> List[str]:
        """Get permissions for a given API role."""
        # Define role permissions
        permissions = {
            APIRole.OBSERVER: [
                "system.read",
                "memory.read",
                "telemetry.read",
                "config.read",
                "audit.read"
            ],
            APIRole.ADMIN: [
                "system.read",
                "system.write",
                "memory.read",
                "memory.write",
                "telemetry.read",
                "config.read",
                "config.write",
                "audit.read",
                "audit.write",
                "users.read"
            ],
            APIRole.AUTHORITY: [
                "system.read",
                "system.write",
                "memory.read",
                "memory.write",
                "telemetry.read",
                "config.read",
                "config.write",
                "audit.read",
                "audit.write",
                "users.read",
                "wa.read",
                "wa.write"
            ],
            APIRole.SYSTEM_ADMIN: [
                "system.read",
                "system.write",
                "memory.read",
                "memory.write",
                "telemetry.read",
                "config.read",
                "config.write",
                "audit.read",
                "audit.write",
                "users.read",
                "users.write",
                "users.delete",
                "wa.read",
                "wa.write",
                "wa.mint",
                "emergency.shutdown"
            ]
        }
        
        return permissions.get(role, [])
    
    async def update_user_permissions(self, user_id: str, permissions: List[str]) -> Optional[User]:
        """Update a user's custom permissions."""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # Update custom permissions
        user.custom_permissions = permissions
        self._users[user_id] = user
        
        # Also update in database if we have auth service
        if self._auth_service:
            try:
                import json
                # Update the WA certificate with custom permissions
                await self._auth_service.update_wa(
                    user_id,
                    updates=None,
                    custom_permissions_json=json.dumps(permissions) if permissions else None
                )
            except Exception as e:
                print(f"Error updating permissions in database: {e}")
        
        return user
    
    async def list_user_api_keys(self, user_id: str) -> List[StoredAPIKey]:
        """List all API keys for a specific user."""
        keys = []
        for stored_key in self._api_keys.values():
            if stored_key.user_id == user_id:
                keys.append(stored_key)
        return sorted(keys, key=lambda k: k.created_at, reverse=True)
    
    async def verify_root_signature(
        self,
        user_id: str,
        wa_role: WARole,
        signature: str
    ) -> bool:
        """Verify a ROOT signature for WA minting.
        
        The signature should be over the message:
        "MINT_WA:{user_id}:{wa_role}:{timestamp}"
        
        Where timestamp is in ISO format.
        """
        import json
        from pathlib import Path
        from cryptography.hazmat.primitives.asymmetric import ed25519
        
        try:
            # Load ROOT public key from seed/
            root_pub_path = Path(__file__).parent.parent.parent.parent.parent.parent / "seed" / "root_pub.json"
            with open(root_pub_path, 'r') as f:
                root_data = json.load(f)
            
            # Get the public key (base64url encoded)
            pubkey_b64 = root_data['pubkey']
            
            # Decode from base64url to bytes
            # Add padding if needed
            pubkey_b64_padded = pubkey_b64 + '=' * (4 - len(pubkey_b64) % 4)
            pubkey_bytes = base64.urlsafe_b64decode(pubkey_b64_padded)
            
            # Create Ed25519 public key object
            public_key = ed25519.Ed25519PublicKey.from_public_bytes(pubkey_bytes)
            
            # The signature should include a timestamp
            # For verification, we'll accept signatures from the last hour
            now = datetime.now(timezone.utc)
            
            # Try multiple timestamp formats within the last hour
            for minutes_ago in range(0, 60, 1):  # Check last 60 minutes
                timestamp = (now - timedelta(minutes=minutes_ago)).isoformat()
                message = f"MINT_WA:{user_id}:{wa_role.value}:{timestamp}"
                
                try:
                    # Decode signature from base64url
                    sig_padded = signature + '=' * (4 - len(signature) % 4)
                    sig_bytes = base64.urlsafe_b64decode(sig_padded)
                    
                    # Verify signature
                    public_key.verify(sig_bytes, message.encode())
                    
                    # If we get here, signature is valid
                    return True
                except Exception:
                    # Try next timestamp
                    continue
            
            # Also try without timestamp for backwards compatibility
            message_no_ts = f"MINT_WA:{user_id}:{wa_role.value}"
            
            # Try standard base64 first (what our signing script produces)
            try:
                sig_bytes = base64.b64decode(signature)
                public_key.verify(sig_bytes, message_no_ts.encode())
                return True
            except Exception:
                pass
            
            # Try urlsafe base64
            try:
                sig_padded = signature + '=' * (4 - len(signature) % 4)
                sig_bytes = base64.urlsafe_b64decode(sig_padded)
                public_key.verify(sig_bytes, message_no_ts.encode())
                return True
            except Exception:
                pass
            
            return False
            
        except Exception as e:
            # Log error but don't expose internal details
            print(f"Signature verification error: {e}")
            return False
    
    async def mint_wise_authority(
        self,
        user_id: str,
        wa_role: WARole,
        minted_by: str
    ) -> Optional[User]:
        """Mint a user as a Wise Authority."""
        user = await self.get_user(user_id)
        if not user:
            return None
        
        # Update WA role
        user.wa_role = wa_role
        user.wa_parent_id = minted_by
        user.wa_auto_minted = False
        
        # If user doesn't have sufficient API role, upgrade it
        if wa_role == WARole.AUTHORITY and user.api_role.value < APIRole.AUTHORITY.value:
            user.api_role = APIRole.AUTHORITY
        elif wa_role == WARole.OBSERVER and user.api_role.value < APIRole.OBSERVER.value:
            user.api_role = APIRole.OBSERVER
        
        # Store updated user
        self._users[user_id] = user
        
        # Also update in database if we have auth service
        if self._auth_service:
            try:
                # Update WA role and parent in database
                await self._auth_service.update_wa(
                    user_id,
                    updates=WAUpdate(role=wa_role.value if hasattr(wa_role, 'value') else str(wa_role)),
                    parent_wa_id=minted_by,
                    auto_minted=0  # Use 0 instead of False for integer field
                )
            except Exception as e:
                print(f"Error updating WA role in database: {e}")
        
        return user
