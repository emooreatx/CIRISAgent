"""
Encrypted Secrets Storage System for CIRIS Agent.

Provides secure, encrypted storage for detected secrets with AES-256-GCM encryption
and comprehensive access auditing.
"""
import os
import sqlite3
import asyncio
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path
import logging

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.backends import default_backend
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class SecretRecord(BaseModel):
    """Encrypted secret storage record."""
    secret_uuid: str = Field(description="UUID identifier for the secret")
    encrypted_value: bytes = Field(description="AES-256-GCM encrypted secret value")
    encryption_key_ref: str = Field(description="Reference to encryption key in secure store")
    salt: bytes = Field(description="Cryptographic salt")
    nonce: bytes = Field(description="AES-GCM nonce")
    
    # Metadata (not encrypted)
    description: str = Field(description="Human-readable description")
    sensitivity_level: str = Field(description="LOW, MEDIUM, HIGH, or CRITICAL")
    detected_pattern: str = Field(description="Pattern that detected this secret")
    context_hint: str = Field(description="Safe context description")
    
    # Audit fields
    created_at: datetime
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    source_message_id: Optional[str] = None
    
    # Access control
    auto_decapsulate_for_actions: List[str] = Field(default_factory=list)
    manual_access_only: bool = False


class SecretAccessLog(BaseModel):
    """Audit log for secret access."""
    access_id: str = Field(description="Unique access identifier")
    secret_uuid: str = Field(description="Secret that was accessed")
    access_type: str = Field(description="VIEW, DECRYPT, UPDATE, or DELETE")
    accessor: str = Field(description="Who/what accessed the secret")
    purpose: str = Field(description="Stated purpose for access")
    timestamp: datetime
    source_ip: Optional[str] = None
    user_agent: Optional[str] = None
    action_context: Optional[str] = None
    success: bool = True
    failure_reason: Optional[str] = None


class SecretsEncryption:
    """Handles encryption/decryption of secrets using AES-256-GCM."""
    
    def __init__(self, master_key: Optional[bytes] = None):
        """Initialize with master key or generate new one."""
        if master_key:
            if len(master_key) != 32:
                raise ValueError("Master key must be 32 bytes (256 bits)")
            self._master_key = master_key
        else:
            self._master_key = AESGCM.generate_key(bit_length=256)
            
    @property
    def master_key(self) -> bytes:
        """Get master key (for persistence)."""
        return self._master_key
        
    def _derive_key(self, salt: bytes) -> bytes:
        """Derive per-secret key from master key + salt."""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        return kdf.derive(self._master_key)
        
    def encrypt_secret(self, value: str) -> Tuple[bytes, bytes, bytes]:
        """
        Encrypt secret value using AES-256-GCM.
        
        Returns: (encrypted_value, salt, nonce)
        Uses master key + salt to derive per-secret key.
        """
        # Generate random salt and nonce
        salt = os.urandom(16)
        nonce = os.urandom(12)  # GCM standard nonce size
        
        # Derive per-secret key
        derived_key = self._derive_key(salt)
        
        # Encrypt with AES-256-GCM
        aesgcm = AESGCM(derived_key)
        encrypted_value = aesgcm.encrypt(nonce, value.encode('utf-8'), None)
        
        return encrypted_value, salt, nonce
        
    def decrypt_secret(self, encrypted_value: bytes, salt: bytes, nonce: bytes) -> str:
        """
        Decrypt secret value using master key + salt.
        
        Args:
            encrypted_value: Encrypted secret data
            salt: Salt used for key derivation
            nonce: Nonce used for encryption
            
        Returns:
            Decrypted secret value as string
        """
        # Derive the same key used for encryption
        derived_key = self._derive_key(salt)
        
        # Decrypt with AES-256-GCM
        aesgcm = AESGCM(derived_key)
        decrypted_bytes = aesgcm.decrypt(nonce, encrypted_value, None)
        
        return decrypted_bytes.decode('utf-8')
        
    def rotate_master_key(self, new_master_key: Optional[bytes] = None) -> bytes:
        """
        Rotate master encryption key.
        
        Args:
            new_master_key: New master key, or None to generate
            
        Returns:
            New master key
        """
        if new_master_key:
            if len(new_master_key) != 32:
                raise ValueError("New master key must be 32 bytes (256 bits)")
            self._master_key = new_master_key
        else:
            self._master_key = AESGCM.generate_key(bit_length=256)
            
        return self._master_key


class SecretsStore:
    """
    Encrypted storage for secrets with comprehensive access controls.
    
    Stores secrets in SQLite database with AES-256-GCM encryption
    and maintains full audit trail of all access.
    """
    
    def __init__(
        self, 
        db_path: str = "secrets.db",
        master_key: Optional[bytes] = None,
        max_accesses_per_minute: int = 10,
        max_accesses_per_hour: int = 100
    ):
        """
        Initialize secrets store.
        
        Args:
            db_path: Path to SQLite database file
            master_key: Master encryption key (generated if None)
            max_accesses_per_minute: Rate limit for secret access
            max_accesses_per_hour: Hourly access limit
        """
        self.db_path = Path(db_path)
        self.encryption = SecretsEncryption(master_key)
        self.max_accesses_per_minute = max_accesses_per_minute
        self.max_accesses_per_hour = max_accesses_per_hour
        self._access_counts: Dict[str, List[datetime]] = {}
        self._lock = asyncio.Lock()
        
        # Initialize database
        self._init_database()
        
    def _init_database(self) -> None:
        """Initialize SQLite database with required tables."""
        # Ensure directory exists
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
        with sqlite3.connect(self.db_path) as conn:
            # Secrets table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS secrets (
                    secret_uuid TEXT PRIMARY KEY,
                    encrypted_value BLOB NOT NULL,
                    encryption_key_ref TEXT NOT NULL,
                    salt BLOB NOT NULL,
                    nonce BLOB NOT NULL,
                    description TEXT NOT NULL,
                    sensitivity_level TEXT NOT NULL,
                    detected_pattern TEXT NOT NULL,
                    context_hint TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    last_accessed TEXT,
                    access_count INTEGER DEFAULT 0,
                    source_message_id TEXT,
                    auto_decapsulate_for_actions TEXT,
                    manual_access_only INTEGER DEFAULT 0
                )
            """)
            
            # Access log table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS secret_access_log (
                    access_id TEXT PRIMARY KEY,
                    secret_uuid TEXT NOT NULL,
                    access_type TEXT NOT NULL,
                    accessor TEXT NOT NULL,
                    purpose TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    source_ip TEXT,
                    user_agent TEXT,
                    action_context TEXT,
                    success INTEGER DEFAULT 1,
                    failure_reason TEXT,
                    FOREIGN KEY (secret_uuid) REFERENCES secrets (secret_uuid)
                )
            """)
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_secrets_pattern ON secrets(detected_pattern)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_secrets_sensitivity ON secrets(sensitivity_level)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_access_log_timestamp ON secret_access_log(timestamp)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_access_log_secret ON secret_access_log(secret_uuid)")
            
            conn.commit()
            
    async def store_secret(self, secret_record: SecretRecord, original_value: str) -> bool:
        """
        Store encrypted secret in database.
        
        Args:
            secret_record: Secret metadata
            original_value: Plain text secret value to encrypt
            
        Returns:
            True if stored successfully
        """
        async with self._lock:
            try:
                # Encrypt the secret value
                encrypted_value, salt, nonce = self.encryption.encrypt_secret(original_value)
                
                # Update record with encryption data
                secret_record.encrypted_value = encrypted_value
                secret_record.salt = salt
                secret_record.nonce = nonce
                secret_record.encryption_key_ref = "master_key_v1"  # Key versioning
                
                with sqlite3.connect(self.db_path) as conn:
                    conn.execute("""
                        INSERT OR REPLACE INTO secrets (
                            secret_uuid, encrypted_value, encryption_key_ref, salt, nonce,
                            description, sensitivity_level, detected_pattern, context_hint,
                            created_at, last_accessed, access_count, source_message_id,
                            auto_decapsulate_for_actions, manual_access_only
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        secret_record.secret_uuid,
                        secret_record.encrypted_value,
                        secret_record.encryption_key_ref,
                        secret_record.salt,
                        secret_record.nonce,
                        secret_record.description,
                        secret_record.sensitivity_level,
                        secret_record.detected_pattern,
                        secret_record.context_hint,
                        secret_record.created_at.isoformat(),
                        secret_record.last_accessed.isoformat() if secret_record.last_accessed else None,
                        secret_record.access_count,
                        secret_record.source_message_id,
                        ",".join(secret_record.auto_decapsulate_for_actions),
                        1 if secret_record.manual_access_only else 0
                    ))
                    conn.commit()
                    
                await self._log_access(
                    secret_record.secret_uuid,
                    "STORE",
                    "system",
                    "Initial secret storage",
                    True
                )
                
                logger.info(f"Stored encrypted secret {secret_record.secret_uuid}")
                return True
                
            except Exception as e:
                logger.error(f"Failed to store secret {secret_record.secret_uuid}: {e}")
                await self._log_access(
                    secret_record.secret_uuid,
                    "STORE",
                    "system", 
                    "Initial secret storage",
                    False,
                    str(e)
                )
                return False
                
    async def retrieve_secret(
        self, 
        secret_uuid: str, 
        purpose: str,
        accessor: str = "system",
        decrypt: bool = False
    ) -> Optional[SecretRecord]:
        """
        Retrieve secret from storage.
        
        Args:
            secret_uuid: UUID of secret to retrieve
            purpose: Purpose for accessing secret (for audit)
            accessor: Who is accessing the secret
            decrypt: Whether to decrypt the secret value
            
        Returns:
            SecretRecord if found, None otherwise
        """
        async with self._lock:
            # Check rate limits
            if not await self._check_rate_limits(accessor):
                await self._log_access(
                    secret_uuid, "VIEW", accessor, purpose, False, "Rate limit exceeded"
                )
                return None
                
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute("""
                        SELECT * FROM secrets WHERE secret_uuid = ?
                    """, (secret_uuid,))
                    
                    row = cursor.fetchone()
                    if not row:
                        await self._log_access(
                            secret_uuid, "VIEW", accessor, purpose, False, "Secret not found"
                        )
                        return None
                        
                    # Parse database row
                    secret_record = SecretRecord(
                        secret_uuid=row[0],
                        encrypted_value=row[1],
                        encryption_key_ref=row[2],
                        salt=row[3],
                        nonce=row[4],
                        description=row[5],
                        sensitivity_level=row[6],
                        detected_pattern=row[7],
                        context_hint=row[8],
                        created_at=datetime.fromisoformat(row[9]),
                        last_accessed=datetime.fromisoformat(row[10]) if row[10] else None,
                        access_count=row[11],
                        source_message_id=row[12],
                        auto_decapsulate_for_actions=row[13].split(",") if row[13] else [],
                        manual_access_only=bool(row[14])
                    )
                    
                    # Update access tracking
                    secret_record.last_accessed = datetime.now()
                    secret_record.access_count += 1
                    
                    conn.execute("""
                        UPDATE secrets 
                        SET last_accessed = ?, access_count = ?
                        WHERE secret_uuid = ?
                    """, (
                        secret_record.last_accessed.isoformat(),
                        secret_record.access_count,
                        secret_uuid
                    ))
                    conn.commit()
                    
                access_type = "DECRYPT" if decrypt else "VIEW"
                await self._log_access(secret_uuid, access_type, accessor, purpose, True)
                
                return secret_record
                
            except Exception as e:
                logger.error(f"Failed to retrieve secret {secret_uuid}: {e}")
                await self._log_access(
                    secret_uuid, "VIEW", accessor, purpose, False, str(e)
                )
                return None
                
    async def decrypt_secret_value(self, secret_record: SecretRecord) -> Optional[str]:
        """
        Decrypt the actual secret value.
        
        Args:
            secret_record: Secret record with encryption data
            
        Returns:
            Decrypted secret value or None if decryption fails
        """
        try:
            return self.encryption.decrypt_secret(
                secret_record.encrypted_value,
                secret_record.salt,
                secret_record.nonce
            )
        except Exception as e:
            logger.error(f"Failed to decrypt secret {secret_record.secret_uuid}: {e}")
            return None
            
    async def delete_secret(self, secret_uuid: str, accessor: str = "system") -> bool:
        """
        Delete secret from storage.
        
        Args:
            secret_uuid: UUID of secret to delete
            accessor: Who is deleting the secret
            
        Returns:
            True if deleted successfully
        """
        async with self._lock:
            try:
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.execute(
                        "DELETE FROM secrets WHERE secret_uuid = ?", 
                        (secret_uuid,)
                    )
                    deleted = cursor.rowcount > 0
                    conn.commit()
                    
                await self._log_access(
                    secret_uuid, "DELETE", accessor, "Secret deletion", deleted
                )
                
                if deleted:
                    logger.info(f"Deleted secret {secret_uuid}")
                return deleted
                
            except Exception as e:
                logger.error(f"Failed to delete secret {secret_uuid}: {e}")
                await self._log_access(
                    secret_uuid, "DELETE", accessor, "Secret deletion", False, str(e)
                )
                return False
                
    async def list_secrets(
        self, 
        pattern_filter: Optional[str] = None,
        sensitivity_filter: Optional[str] = None
    ) -> List[SecretRecord]:
        """
        List stored secrets (without decryption).
        
        Args:
            pattern_filter: Filter by detection pattern
            sensitivity_filter: Filter by sensitivity level
            
        Returns:
            List of secret records (encrypted values)
        """
        try:
            query = "SELECT * FROM secrets WHERE 1=1"
            params = []
            
            if pattern_filter:
                query += " AND detected_pattern = ?"
                params.append(pattern_filter)
                
            if sensitivity_filter:
                query += " AND sensitivity_level = ?"
                params.append(sensitivity_filter)
                
            query += " ORDER BY created_at DESC"
            
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(query, params)
                rows = cursor.fetchall()
                
            secrets = []
            for row in rows:
                secret_record = SecretRecord(
                    secret_uuid=row[0],
                    encrypted_value=row[1],
                    encryption_key_ref=row[2],
                    salt=row[3],
                    nonce=row[4],
                    description=row[5],
                    sensitivity_level=row[6],
                    detected_pattern=row[7],
                    context_hint=row[8],
                    created_at=datetime.fromisoformat(row[9]),
                    last_accessed=datetime.fromisoformat(row[10]) if row[10] else None,
                    access_count=row[11],
                    source_message_id=row[12],
                    auto_decapsulate_for_actions=row[13].split(",") if row[13] else [],
                    manual_access_only=bool(row[14])
                )
                secrets.append(secret_record)
                
            return secrets
            
        except Exception as e:
            logger.error(f"Failed to list secrets: {e}")
            return []
            
    async def _check_rate_limits(self, accessor: str) -> bool:
        """Check if accessor is within rate limits."""
        now = datetime.now()
        
        # Initialize tracking for new accessor
        if accessor not in self._access_counts:
            self._access_counts[accessor] = []
            
        access_times = self._access_counts[accessor]
        
        # Remove old access times
        minute_ago = now.timestamp() - 60
        hour_ago = now.timestamp() - 3600
        
        access_times[:] = [
            access_time for access_time in access_times 
            if access_time.timestamp() > hour_ago
        ]
        
        # Check limits
        recent_accesses = [
            access_time for access_time in access_times 
            if access_time.timestamp() > minute_ago
        ]
        
        if len(recent_accesses) >= self.max_accesses_per_minute:
            return False
            
        if len(access_times) >= self.max_accesses_per_hour:
            return False
            
        # Record this access
        access_times.append(now)
        return True
        
    async def _log_access(
        self,
        secret_uuid: str,
        access_type: str,
        accessor: str,
        purpose: str,
        success: bool,
        failure_reason: Optional[str] = None
    ) -> None:
        """Log secret access for audit trail."""
        try:
            access_log = SecretAccessLog(
                access_id=f"access_{datetime.now().timestamp()}_{secret_uuid[:8]}",
                secret_uuid=secret_uuid,
                access_type=access_type,
                accessor=accessor,
                purpose=purpose,
                timestamp=datetime.now(),
                success=success,
                failure_reason=failure_reason
            )
            
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO secret_access_log (
                        access_id, secret_uuid, access_type, accessor, purpose,
                        timestamp, source_ip, user_agent, action_context,
                        success, failure_reason
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    access_log.access_id,
                    access_log.secret_uuid,
                    access_log.access_type,
                    access_log.accessor,
                    access_log.purpose,
                    access_log.timestamp.isoformat(),
                    access_log.source_ip,
                    access_log.user_agent,
                    access_log.action_context,
                    1 if access_log.success else 0,
                    access_log.failure_reason
                ))
                conn.commit()
                
        except Exception as e:
            logger.error(f"Failed to log secret access: {e}")