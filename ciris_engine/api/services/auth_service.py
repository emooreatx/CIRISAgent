"""Authentication service for API v2.0.

Manages API keys, OAuth users, and authentication state.
"""
import hashlib
from typing import Optional, List, Dict
from datetime import datetime, timezone
from dataclasses import dataclass

from ciris_engine.schemas.api.auth import UserRole, APIKeyInfo

@dataclass
class StoredAPIKey:
    """Internal representation of an API key."""
    key_hash: str
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

class APIAuthService:
    """Simple in-memory authentication service."""

    def __init__(self):
        # In production, these would be backed by a database
        self._api_keys: Dict[str, StoredAPIKey] = {}
        self._oauth_users: Dict[str, OAuthUser] = {}

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
        stored_key = StoredAPIKey(
            key_hash=key_hash,
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

        return stored_key

    async def list_api_keys(self) -> List[APIKeyInfo]:
        """List all API keys (without the actual keys)."""
        keys = []
        for key_hash, stored_key in self._api_keys.items():
            keys.append(APIKeyInfo(
                key_id=key_hash[:8],  # Show partial hash as ID
                role=stored_key.role,
                expires_at=stored_key.expires_at,
                description=stored_key.description,
                created_at=stored_key.created_at,
                created_by=stored_key.created_by,
                last_used=stored_key.last_used,
                is_active=stored_key.is_active
            ))
        return keys

    async def get_api_key_info(self, key_id: str) -> Optional[APIKeyInfo]:
        """Get info about a specific API key."""
        # Find key by partial hash
        for key_hash, stored_key in self._api_keys.items():
            if key_hash.startswith(key_id):
                return APIKeyInfo(
                    key_id=key_hash[:8],
                    role=stored_key.role,
                    expires_at=stored_key.expires_at,
                    description=stored_key.description,
                    created_at=stored_key.created_at,
                    created_by=stored_key.created_by,
                    last_used=stored_key.last_used,
                    is_active=stored_key.is_active
                )
        return None

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

    async def get_user_by_oauth(
        self,
        provider: str,
        external_id: str
    ) -> Optional[OAuthUser]:
        """Get user by OAuth provider and external ID."""
        user_id = f"{provider}:{external_id}"
        return self._oauth_users.get(user_id)
