"""
Signed audit service integrating cryptographic hash chains and digital signatures.

This service extends the standard audit service to provide tamper-evident logging
with hash chain integrity and RSA digital signatures.
"""

import asyncio
import json
import logging
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from .base import Service
from .local_audit_log import AuditService
from ciris_engine.audit.hash_chain import AuditHashChain
from ciris_engine.audit.signature_manager import AuditSignatureManager
from ciris_engine.audit.verifier import AuditVerifier
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.schemas.audit_schemas_v1 import AuditLogEntry

logger = logging.getLogger(__name__)


class SignedAuditService(AuditService):
    """
    Enhanced audit service with cryptographic integrity protection.
    
    Provides:
    - Hash chain integrity for tamper detection
    - RSA digital signatures for non-repudiation
    - Backward compatibility with existing JSONL audit logs
    - Configurable dual-mode operation (JSONL only, DB only, or both)
    """
    
    def __init__(
        self,
        log_path: str = "audit_logs.jsonl",
        db_path: str = "ciris_audit.db",
        key_path: str = "audit_keys",
        rotation_size_mb: int = 100,
        retention_days: int = 90,
        enable_jsonl: bool = True,
        enable_signed: bool = True
    ) -> None:
        """
        Initialize the signed audit service.
        
        Args:
            log_path: Path to JSONL audit log file
            db_path: Path to SQLite database for signed audit trail
            key_path: Directory for storing signing keys
            rotation_size_mb: JSONL file rotation size in MB
            retention_days: Log retention period in days
            enable_jsonl: Whether to write to JSONL files
            enable_signed: Whether to write to signed database
        """
        super().__init__(log_path, rotation_size_mb, retention_days)
        
        self.db_path = Path(db_path)
        self.key_path = Path(key_path)
        self.enable_jsonl = enable_jsonl
        self.enable_signed = enable_signed
        
        self.hash_chain: Optional[AuditHashChain] = None
        self.signature_manager: Optional[AuditSignatureManager] = None
        self.verifier: Optional[AuditVerifier] = None
        
        self._db_connection: Optional[sqlite3.Connection] = None
        self._signing_enabled = False
    
    async def start(self) -> None:
        """Start the signed audit service."""
        # Start base service (handles JSONL)
        if self.enable_jsonl:
            await super().start()
        
        # Initialize signed audit components
        if self.enable_signed:
            await self._initialize_signed_audit()
    
    async def stop(self) -> None:
        """Stop the signed audit service."""
        await self._flush_buffer()
        
        if self._db_connection:
            self._db_connection.close()
        
        if self.enable_jsonl:
            await super().stop()
    
    async def log_action(
        self,
        handler_action: HandlerActionType,
        context: Dict[str, Any],
        outcome: Optional[str] = None,
    ) -> bool:
        """
        Log an action with both JSONL and signed database.
        
        This method extends the base log_action to also write to the
        signed audit trail when enabled.
        """
        try:
            entry = AuditLogEntry(
                event_id=str(uuid.uuid4()),
                event_timestamp=datetime.now(timezone.utc).isoformat(),
                event_type=handler_action.value,
                originator_id=context.get("thought_id", "unknown"),
                target_id=context.get("target_id"),
                event_summary=self._generate_summary(handler_action, context, outcome),
                event_payload=context,
                agent_profile=context.get("agent_profile"),
                round_number=context.get("round_number"),
                thought_id=context.get("thought_id"),
                task_id=context.get("task_id") or context.get("source_task_id"),
            )
            
            if self.enable_jsonl:
                self._buffer.append(entry)
                if len(self._buffer) >= 100:
                    await self._flush_buffer()
            
            if self.enable_signed and self._signing_enabled:
                await self._write_signed_entry(entry)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to log action: {e}")
            return False
    
    async def verify_audit_integrity(self) -> Dict[str, Any]:
        """
        Verify the integrity of the signed audit trail.
        
        Returns:
            Dictionary containing verification results
        """
        if not self.enable_signed or not self.verifier:
            return {
                "error": "Signed audit not enabled",
                "signed_audit_enabled": False
            }
        
        try:
            return await asyncio.to_thread(self.verifier.verify_complete_chain)
        except Exception as e:
            logger.error(f"Audit verification failed: {e}")
            return {
                "error": str(e),
                "valid": False
            }
    
    async def get_verification_report(self) -> Dict[str, Any]:
        """
        Generate a comprehensive audit verification report.
        
        Returns:
            Dictionary containing detailed verification report
        """
        if not self.enable_signed or not self.verifier:
            return {
                "error": "Signed audit not enabled",
                "signed_audit_enabled": False
            }
        
        try:
            return await asyncio.to_thread(self.verifier.get_verification_report)
        except Exception as e:
            logger.error(f"Failed to generate verification report: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
    
    async def _initialize_signed_audit(self) -> None:
        """Initialize the signed audit components."""
        try:
            # Ensure key directory exists
            self.key_path.mkdir(parents=True, exist_ok=True)
            
            # Initialize database
            await self._init_database()
            
            # Initialize components
            self.hash_chain = AuditHashChain(str(self.db_path))
            self.signature_manager = AuditSignatureManager(str(self.key_path), str(self.db_path))
            self.verifier = AuditVerifier(str(self.db_path), str(self.key_path))
            
            # Initialize in thread to avoid blocking
            await asyncio.to_thread(self._init_components_sync)
            
            self._signing_enabled = True
            logger.info("Signed audit system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize signed audit: {e}")
            self._signing_enabled = False
    
    def _init_components_sync(self) -> None:
        """Synchronous initialization of audit components."""
        if not self.hash_chain:
            raise RuntimeError("Hash chain not initialized")
        if not self.signature_manager:
            raise RuntimeError("Signature manager not initialized")
        if not self.verifier:
            raise RuntimeError("Verifier not initialized")
            
        self.hash_chain.initialize()
        self.signature_manager.initialize()
        self.verifier.initialize()
        
        if not self.signature_manager.test_signing():
            raise RuntimeError("Signing test failed")
    
    async def _init_database(self) -> None:
        """Initialize the audit database with required tables."""
        def _create_tables() -> None:
            conn = sqlite3.connect(str(self.db_path))
            cursor = conn.cursor()
            
            # Create audit_log_v2 table (from migration 003)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log_v2 (
                    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_id TEXT NOT NULL UNIQUE,
                    event_timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    originator_id TEXT NOT NULL,
                    target_id TEXT,
                    event_summary TEXT,
                    event_payload TEXT,
                    agent_profile TEXT,
                    round_number INTEGER,
                    thought_id TEXT,
                    task_id TEXT,
                    sequence_number INTEGER NOT NULL,
                    previous_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL,
                    signature TEXT NOT NULL,
                    signing_key_id TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(sequence_number),
                    CHECK(sequence_number > 0)
                )
            """)
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_signing_keys (
                    key_id TEXT PRIMARY KEY,
                    public_key TEXT NOT NULL,
                    algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                    key_size INTEGER NOT NULL DEFAULT 2048,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    revoked_at TEXT,
                    CHECK(algorithm IN ('rsa-pss', 'ed25519'))
                )
            """)
            
            # Create audit_roots table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_roots (
                    root_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    sequence_start INTEGER NOT NULL,
                    sequence_end INTEGER NOT NULL,
                    root_hash TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    external_anchor TEXT,
                    UNIQUE(sequence_start, sequence_end)
                )
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_v2_event_timestamp 
                ON audit_log_v2(event_timestamp)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_v2_event_type 
                ON audit_log_v2(event_type)
            """)
            
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_audit_log_v2_thought_id 
                ON audit_log_v2(thought_id)
            """)
            
            conn.commit()
            conn.close()
        
        await asyncio.to_thread(_create_tables)
        self._db_connection = sqlite3.connect(str(self.db_path))
    
    async def _write_signed_entry(self, entry: AuditLogEntry) -> None:
        """Write an entry to the signed audit database."""
        def _write_to_db() -> None:
            entry_dict = {
                "event_id": entry.event_id,
                "event_timestamp": entry.event_timestamp,
                "event_type": entry.event_type,
                "originator_id": entry.originator_id,
                "event_payload": json.dumps(entry.event_payload) if entry.event_payload else None
            }
            
            if not self.hash_chain:
                raise RuntimeError("Hash chain not available")
            prepared = self.hash_chain.prepare_entry(entry_dict)
            
            if not self.signature_manager:
                raise RuntimeError("Signature manager not available")
            signature = self.signature_manager.sign_entry(prepared["entry_hash"])
            
            if not self._db_connection:
                raise RuntimeError("Database connection not available")
            cursor = self._db_connection.cursor()
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, target_id,
                 event_summary, event_payload, agent_profile, round_number,
                 thought_id, task_id, sequence_number, previous_hash, 
                 entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry.event_id,
                entry.event_timestamp,
                entry.event_type,
                entry.originator_id,
                entry.target_id,
                entry.event_summary,
                json.dumps(entry.event_payload) if entry.event_payload else None,
                entry.agent_profile,
                entry.round_number,
                entry.thought_id,
                entry.task_id,
                prepared["sequence_number"],
                prepared["previous_hash"],
                prepared["entry_hash"],
                signature,
                self.signature_manager.key_id if self.signature_manager else "unknown"
            ))
            
            if self._db_connection:
                self._db_connection.commit()
        
        try:
            await asyncio.to_thread(_write_to_db)
        except Exception as e:
            logger.error(f"Failed to write signed audit entry: {e}")
    
    async def _flush_buffer(self) -> None:
        """Flush buffered entries to both JSONL and signed database."""
        if not self._buffer:
            return
        
        if self.enable_jsonl:
            await super()._flush_buffer()
        
        if self.enable_signed and self._signing_enabled:
            for entry in self._buffer:
                await self._write_signed_entry(entry)
        
        self._buffer.clear()
    
    async def rotate_signing_keys(self) -> str:
        """
        Rotate the signing keys for the audit system.
        
        Returns:
            New key ID after rotation
        """
        if not self.enable_signed or not self.signature_manager:
            raise RuntimeError("Signed audit not enabled")
        
        try:
            new_key_id = await asyncio.to_thread(self.signature_manager.rotate_keys)
            logger.info(f"Audit signing keys rotated, new key ID: {new_key_id}")
            return new_key_id
        except Exception as e:
            logger.error(f"Failed to rotate signing keys: {e}")
            raise
    
    async def create_root_anchor(self, external_anchor: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a root hash anchor for the current audit chain state.
        
        Args:
            external_anchor: Optional external reference (e.g., blockchain tx)
            
        Returns:
            Dictionary containing root anchor information
        """
        if not self.enable_signed:
            return {"error": "Signed audit not enabled"}
        
        try:
            if not self.hash_chain:
                return {"error": "Hash chain not available"}
            summary = await asyncio.to_thread(self.hash_chain.get_chain_summary)
            
            if summary["total_entries"] == 0:
                return {"error": "No entries in audit chain"}
            
            def _create_anchor() -> None:
                if not self._db_connection:
                    raise RuntimeError("Database connection not available")
                cursor = self._db_connection.cursor()
                cursor.execute("""
                    INSERT INTO audit_roots 
                    (sequence_start, sequence_end, root_hash, timestamp, external_anchor)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    1,  # Always start from beginning for now
                    summary["current_sequence"],
                    summary["current_hash"],
                    datetime.now(timezone.utc).isoformat(),
                    external_anchor
                ))
                
                self._db_connection.commit()
                return cursor.lastrowid
            
            root_id = await asyncio.to_thread(_create_anchor)
            
            return {
                "root_id": root_id,
                "sequence_range": [1, summary["current_sequence"]],
                "root_hash": summary["current_hash"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "external_anchor": external_anchor
            }
            
        except Exception as e:
            logger.error(f"Failed to create root anchor: {e}")
            return {"error": str(e)}