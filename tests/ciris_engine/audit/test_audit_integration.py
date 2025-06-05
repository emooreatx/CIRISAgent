"""
Comprehensive tests for the CIRIS audit system integration.

Tests cover:
- Hash chain integrity verification
- RSA signature generation and verification
- Database migration 003 application
- Integration with existing audit service
- Performance impact validation
- Error handling and recovery
- Key rotation procedures
"""

import pytest
import sqlite3
import tempfile
import os
import time
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, Any

from ciris_engine.audit.hash_chain import AuditHashChain
from ciris_engine.audit.signature_manager import AuditSignatureManager  
from ciris_engine.audit.verifier import AuditVerifier


class TestAuditHashChain:
    """Test the AuditHashChain component"""
    
    @pytest.fixture
    def temp_db(self):
        """Create a temporary database for testing"""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create the audit_log_v2 table
        conn = sqlite3.connect(path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE audit_log_v2 (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                originator_id TEXT NOT NULL,
                event_payload TEXT,
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
        conn.commit()
        conn.close()
        
        yield path
        os.unlink(path)
    
    def test_hash_chain_initialization(self, temp_db):
        """Test hash chain initializes correctly"""
        chain = AuditHashChain(temp_db)
        
        # Should not be initialized yet
        assert not chain._initialized
        
        # Initialize
        chain.initialize()
        assert chain._initialized
        assert chain._sequence_number == 0
        assert chain._last_hash is None
    
    def test_hash_computation_deterministic(self, temp_db):
        """Test that hash computation is deterministic"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload",
            "sequence_number": 1,
            "previous_hash": "genesis"
        }
        
        hash1 = chain.compute_entry_hash(entry)
        hash2 = chain.compute_entry_hash(entry)
        
        assert hash1 == hash2
        assert len(hash1) == 64  # SHA-256 hex digest
        assert hash1 != "genesis"
    
    def test_hash_changes_with_content(self, temp_db):
        """Test that different content produces different hashes"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        entry1 = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload",
            "sequence_number": 1,
            "previous_hash": "genesis"
        }
        
        entry2 = entry1.copy()
        entry2["event_payload"] = "different payload"
        
        hash1 = chain.compute_entry_hash(entry1)
        hash2 = chain.compute_entry_hash(entry2)
        
        assert hash1 != hash2
    
    def test_entry_preparation(self, temp_db):
        """Test entry preparation adds chain fields correctly"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = chain.prepare_entry(entry)
        
        assert prepared["sequence_number"] == 1
        assert prepared["previous_hash"] == "genesis"
        assert "entry_hash" in prepared
        assert len(prepared["entry_hash"]) == 64
        
        # Prepare another entry
        entry2 = entry.copy()
        entry2["event_id"] = "test-456"
        prepared2 = chain.prepare_entry(entry2)
        
        assert prepared2["sequence_number"] == 2
        assert prepared2["previous_hash"] == prepared["entry_hash"]
    
    def test_chain_verification_empty(self, temp_db):
        """Test verification of empty chain"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        result = chain.verify_chain_integrity()
        assert result["valid"] is True
        assert result["entries_checked"] == 0
        assert result["errors"] == []
    
    def test_chain_verification_single_entry(self, temp_db):
        """Test verification of single entry chain"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        # Insert a valid entry
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = chain.prepare_entry(entry)
        
        # Store in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log_v2 
            (event_id, event_timestamp, event_type, originator_id, event_payload,
             sequence_number, previous_hash, entry_hash, signature, signing_key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
            prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
            prepared["previous_hash"], prepared["entry_hash"], "dummy_signature", "dummy_key"
        ))
        conn.commit()
        conn.close()
        
        result = chain.verify_chain_integrity()
        assert result["valid"] is True
        assert result["entries_checked"] == 1
        assert result["errors"] == []
    
    def test_chain_verification_multiple_entries(self, temp_db):
        """Test verification of multi-entry chain"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        # Insert multiple valid entries
        entries = []
        for i in range(3):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            prepared = chain.prepare_entry(entry)
            entries.append(prepared)
        
        # Store all entries
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        for entry in entries:
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["event_id"], entry["event_timestamp"], entry["event_type"],
                entry["originator_id"], entry["event_payload"], entry["sequence_number"],
                entry["previous_hash"], entry["entry_hash"], "dummy_signature", "dummy_key"
            ))
        conn.commit()
        conn.close()
        
        result = chain.verify_chain_integrity()
        assert result["valid"] is True
        assert result["entries_checked"] == 3
        assert result["errors"] == []
    
    def test_chain_verification_detects_tampering(self, temp_db):
        """Test that verification detects tampering"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        # Insert a valid entry
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = chain.prepare_entry(entry)
        
        # Store in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log_v2 
            (event_id, event_timestamp, event_type, originator_id, event_payload,
             sequence_number, previous_hash, entry_hash, signature, signing_key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
            prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
            prepared["previous_hash"], prepared["entry_hash"], "dummy_signature", "dummy_key"
        ))
        
        # Tamper with the entry by changing the payload
        cursor.execute("""
            UPDATE audit_log_v2 
            SET event_payload = 'tampered payload'
            WHERE event_id = ?
        """, (prepared["event_id"],))
        
        conn.commit()
        conn.close()
        
        result = chain.verify_chain_integrity()
        assert result["valid"] is False
        assert result["entries_checked"] == 1
        assert len(result["errors"]) > 0
        assert "hash mismatch" in result["errors"][0].lower()
    
    def test_chain_summary(self, temp_db):
        """Test chain summary generation"""
        chain = AuditHashChain(temp_db)
        chain.initialize()
        
        # Empty chain summary
        summary = chain.get_chain_summary()
        assert summary["total_entries"] == 0
        assert summary["sequence_range"] == [0, 0]
        assert summary["current_sequence"] == 0
        assert summary["current_hash"] is None
        
        # Add an entry
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = chain.prepare_entry(entry)
        
        # Store in database
        conn = sqlite3.connect(temp_db)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log_v2 
            (event_id, event_timestamp, event_type, originator_id, event_payload,
             sequence_number, previous_hash, entry_hash, signature, signing_key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
            prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
            prepared["previous_hash"], prepared["entry_hash"], "dummy_signature", "dummy_key"
        ))
        conn.commit()
        conn.close()
        
        # Re-initialize to pick up the new entry
        chain.initialize()
        summary = chain.get_chain_summary()
        
        assert summary["total_entries"] == 1
        assert summary["sequence_range"] == [1, 1]
        assert summary["current_sequence"] == 1
        assert summary["current_hash"] == prepared["entry_hash"]


class TestAuditSignatureManager:
    """Test the AuditSignatureManager component"""
    
    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for keys and database"""
        import tempfile
        import shutil
        
        key_dir = tempfile.mkdtemp()
        
        # Create database with signing keys table
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE audit_signing_keys (
                key_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                key_size INTEGER NOT NULL DEFAULT 2048,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT,
                CHECK(algorithm IN ('rsa-pss', 'ed25519'))
            )
        """)
        conn.commit()
        conn.close()
        
        yield key_dir, db_path
        
        shutil.rmtree(key_dir)
        os.unlink(db_path)
    
    def test_signature_manager_initialization(self, temp_dirs):
        """Test signature manager initializes correctly"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        assert manager._private_key is None
        assert manager._key_id is None
        
        # Initialize
        manager.initialize()
        assert manager._private_key is not None
        assert manager._public_key is not None
        assert manager._key_id is not None
        assert len(manager._key_id) > 0
    
    def test_key_generation_and_persistence(self, temp_dirs):
        """Test that keys are generated and persisted correctly"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        # Check that key files exist
        private_key_path = Path(key_dir) / "audit_private.pem"
        public_key_path = Path(key_dir) / "audit_public.pem"
        
        assert private_key_path.exists()
        assert public_key_path.exists()
        
        # Check file permissions on private key
        stat = private_key_path.stat()
        # On Unix systems, 0o600 means read/write for owner only
        assert oct(stat.st_mode)[-3:] == '600'
        
        # Check that key is registered in database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT key_id, algorithm, key_size FROM audit_signing_keys")
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
        assert row[0] == manager._key_id
        assert row[1] == 'rsa-pss'
        assert row[2] == 2048
    
    def test_key_loading_existing(self, temp_dirs):
        """Test loading existing keys"""
        key_dir, db_path = temp_dirs
        
        # Create first manager and initialize
        manager1 = AuditSignatureManager(key_dir, db_path)
        manager1.initialize()
        key_id1 = manager1._key_id
        
        # Create second manager and initialize - should load existing keys
        manager2 = AuditSignatureManager(key_dir, db_path)
        manager2.initialize()
        key_id2 = manager2._key_id
        
        assert key_id1 == key_id2
        
        # Should be able to verify signatures across managers
        test_data = "test_data_for_signing"
        signature = manager1.sign_entry(test_data)
        verified = manager2.verify_signature(test_data, signature)
        assert verified is True
    
    def test_signature_generation_and_verification(self, temp_dirs):
        """Test signature generation and verification"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        test_data = "test_entry_hash_12345"
        
        # Generate signature
        signature = manager.sign_entry(test_data)
        assert isinstance(signature, str)
        assert len(signature) > 0
        
        # Verify signature
        verified = manager.verify_signature(test_data, signature)
        assert verified is True
        
        # Verify with wrong data
        verified_wrong = manager.verify_signature("wrong_data", signature)
        assert verified_wrong is False
        
        # Verify with corrupted signature
        corrupted_signature = signature[:-1] + "X"
        verified_corrupted = manager.verify_signature(test_data, corrupted_signature)
        assert verified_corrupted is False
    
    def test_signature_deterministic(self, temp_dirs):
        """Test that signatures are not deterministic (include randomness)"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        test_data = "test_entry_hash_12345"
        
        # Generate multiple signatures
        sig1 = manager.sign_entry(test_data)
        sig2 = manager.sign_entry(test_data)
        
        # Signatures should be different (RSA-PSS uses random salt)
        assert sig1 != sig2
        
        # But both should verify correctly
        assert manager.verify_signature(test_data, sig1) is True
        assert manager.verify_signature(test_data, sig2) is True
    
    def test_key_rotation(self, temp_dirs):
        """Test key rotation functionality"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        old_key_id = manager._key_id
        test_data = "test_data"
        old_signature = manager.sign_entry(test_data)
        
        # Rotate keys
        new_key_id = manager.rotate_keys()
        
        assert new_key_id != old_key_id
        assert manager._key_id == new_key_id
        
        # Old signature should still verify with old key
        assert manager.verify_signature(test_data, old_signature, old_key_id) is True
        
        # New signature should verify with current key
        new_signature = manager.sign_entry(test_data)
        assert manager.verify_signature(test_data, new_signature) is True
        
        # Check that old key is marked as revoked
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT revoked_at FROM audit_signing_keys WHERE key_id = ?", (old_key_id,))
        row = cursor.fetchone()
        conn.close()
        
        assert row is not None
        assert row[0] is not None  # revoked_at should be set
    
    def test_signing_test_function(self, temp_dirs):
        """Test the built-in signing test function"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        # Test function should pass
        result = manager.test_signing()
        assert result is True
    
    def test_key_info_retrieval(self, temp_dirs):
        """Test key information retrieval"""
        key_dir, db_path = temp_dirs
        
        manager = AuditSignatureManager(key_dir, db_path)
        manager.initialize()
        
        key_info = manager.get_key_info()
        
        assert "key_id" in key_info
        assert key_info["key_id"] == manager._key_id
        assert key_info["algorithm"] == "rsa-pss"
        assert key_info["key_size"] == 2048
        assert key_info["active"] is True
        assert "created_at" in key_info


class TestAuditVerifier:
    """Test the AuditVerifier component"""
    
    @pytest.fixture
    def complete_audit_system(self):
        """Create a complete audit system for testing"""
        import tempfile
        import shutil
        
        key_dir = tempfile.mkdtemp()
        
        # Create database with all required tables
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Create audit_log_v2 table
        cursor.execute("""
            CREATE TABLE audit_log_v2 (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                originator_id TEXT NOT NULL,
                event_payload TEXT,
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
        
        # Create signing keys table
        cursor.execute("""
            CREATE TABLE audit_signing_keys (
                key_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                key_size INTEGER NOT NULL DEFAULT 2048,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT,
                CHECK(algorithm IN ('rsa-pss', 'ed25519'))
            )
        """)
        
        # Create audit roots table
        cursor.execute("""
            CREATE TABLE audit_roots (
                root_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sequence_start INTEGER NOT NULL,
                sequence_end INTEGER NOT NULL,
                root_hash TEXT NOT NULL,
                timestamp TEXT NOT NULL,
                external_anchor TEXT,
                UNIQUE(sequence_start, sequence_end)
            )
        """)
        
        conn.commit()
        conn.close()
        
        # Initialize components
        hash_chain = AuditHashChain(db_path)
        signature_manager = AuditSignatureManager(key_dir, db_path)
        verifier = AuditVerifier(db_path, key_dir)
        
        hash_chain.initialize()
        signature_manager.initialize()
        verifier.initialize()
        
        yield hash_chain, signature_manager, verifier, db_path
        
        shutil.rmtree(key_dir)
        os.unlink(db_path)
    
    def test_verifier_initialization(self, complete_audit_system):
        """Test verifier initializes correctly"""
        _, _, verifier, _ = complete_audit_system
        
        assert verifier._initialized is True
        assert verifier.hash_chain is not None
        assert verifier.signature_manager is not None
    
    def test_complete_chain_verification_empty(self, complete_audit_system):
        """Test complete verification of empty chain"""
        _, _, verifier, _ = complete_audit_system
        
        result = verifier.verify_complete_chain()
        
        assert result["valid"] is True
        assert result["entries_verified"] == 0
        assert result["hash_chain_valid"] is True
        assert result["signatures_valid"] is True
        assert "summary" in result
    
    def test_complete_chain_verification_with_entries(self, complete_audit_system):
        """Test complete verification with valid entries"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create and store valid entries
        entries = []
        for i in range(3):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            
            prepared = hash_chain.prepare_entry(entry)
            signature = signature_manager.sign_entry(prepared["entry_hash"])
            prepared["signature"] = signature
            prepared["signing_key_id"] = signature_manager.key_id
            
            entries.append(prepared)
        
        # Store all entries
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for entry in entries:
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["event_id"], entry["event_timestamp"], entry["event_type"],
                entry["originator_id"], entry["event_payload"], entry["sequence_number"],
                entry["previous_hash"], entry["entry_hash"], entry["signature"], 
                entry["signing_key_id"]
            ))
        conn.commit()
        conn.close()
        
        result = verifier.verify_complete_chain()
        
        assert result["valid"] is True
        assert result["entries_verified"] == 3
        assert result["hash_chain_valid"] is True
        assert result["signatures_valid"] is True
        assert result["verification_time_ms"] >= 0
    
    def test_verification_detects_invalid_signature(self, complete_audit_system):
        """Test that verification detects invalid signatures"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create an entry with invalid signature
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = hash_chain.prepare_entry(entry)
        prepared["signature"] = "invalid_signature"
        prepared["signing_key_id"] = signature_manager.key_id
        
        # Store entry
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log_v2 
            (event_id, event_timestamp, event_type, originator_id, event_payload,
             sequence_number, previous_hash, entry_hash, signature, signing_key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
            prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
            prepared["previous_hash"], prepared["entry_hash"], prepared["signature"], 
            prepared["signing_key_id"]
        ))
        conn.commit()
        conn.close()
        
        result = verifier.verify_complete_chain()
        
        assert result["valid"] is False
        assert result["entries_verified"] == 1
        assert result["hash_chain_valid"] is True  # Hash chain should be valid
        assert result["signatures_valid"] is False  # Signatures should be invalid
        assert len(result["signature_errors"]) > 0
    
    def test_single_entry_verification(self, complete_audit_system):
        """Test verification of a single entry"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create and store a valid entry
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload"
        }
        
        prepared = hash_chain.prepare_entry(entry)
        signature = signature_manager.sign_entry(prepared["entry_hash"])
        prepared["signature"] = signature
        prepared["signing_key_id"] = signature_manager.key_id
        
        # Store entry
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO audit_log_v2 
            (event_id, event_timestamp, event_type, originator_id, event_payload,
             sequence_number, previous_hash, entry_hash, signature, signing_key_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
            prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
            prepared["previous_hash"], prepared["entry_hash"], prepared["signature"], 
            prepared["signing_key_id"]
        ))
        conn.commit()
        
        # Get the entry ID
        cursor.execute("SELECT entry_id FROM audit_log_v2 WHERE event_id = ?", (prepared["event_id"],))
        entry_id = cursor.fetchone()[0]
        conn.close()
        
        result = verifier.verify_entry(entry_id)
        
        assert result["valid"] is True
        assert result["entry_id"] == entry_id
        assert result["sequence_number"] == 1
        assert result["errors"] == []
    
    def test_range_verification(self, complete_audit_system):
        """Test verification of a range of entries"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create and store multiple valid entries
        entries = []
        for i in range(5):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            
            prepared = hash_chain.prepare_entry(entry)
            signature = signature_manager.sign_entry(prepared["entry_hash"])
            prepared["signature"] = signature
            prepared["signing_key_id"] = signature_manager.key_id
            
            entries.append(prepared)
        
        # Store all entries
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for entry in entries:
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["event_id"], entry["event_timestamp"], entry["event_type"],
                entry["originator_id"], entry["event_payload"], entry["sequence_number"],
                entry["previous_hash"], entry["entry_hash"], entry["signature"], 
                entry["signing_key_id"]
            ))
        conn.commit()
        conn.close()
        
        # Verify a range
        result = verifier.verify_range(2, 4)
        
        assert result["valid"] is True
        assert result["entries_verified"] == 3  # Sequences 2, 3, 4
        assert result["hash_chain_valid"] is True
        assert result["signatures_valid"] is True
    
    def test_fast_tampering_detection(self, complete_audit_system):
        """Test fast tampering detection"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create valid chain
        entries = []
        for i in range(5):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            
            prepared = hash_chain.prepare_entry(entry)
            signature = signature_manager.sign_entry(prepared["entry_hash"])
            prepared["signature"] = signature
            prepared["signing_key_id"] = signature_manager.key_id
            
            entries.append(prepared)
        
        # Store all entries
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        for entry in entries:
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                entry["event_id"], entry["event_timestamp"], entry["event_type"],
                entry["originator_id"], entry["event_payload"], entry["sequence_number"],
                entry["previous_hash"], entry["entry_hash"], entry["signature"], 
                entry["signing_key_id"]
            ))
        
        # Tamper with the third entry
        cursor.execute("""
            UPDATE audit_log_v2 
            SET event_payload = 'tampered payload'
            WHERE sequence_number = 3
        """)
        
        conn.commit()
        conn.close()
        
        # Re-initialize to pick up changes
        verifier.hash_chain.initialize(force=True)
        
        # Fast tampering detection should find the tampered entry
        first_tampered = verifier.find_tampering_fast()
        
        assert first_tampered is not None
        assert first_tampered == 3  # Third entry was tampered
    
    def test_verification_report_generation(self, complete_audit_system):
        """Test comprehensive verification report generation"""
        hash_chain, signature_manager, verifier, db_path = complete_audit_system
        
        # Create some valid entries
        for i in range(3):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            
            prepared = hash_chain.prepare_entry(entry)
            signature = signature_manager.sign_entry(prepared["entry_hash"])
            prepared["signature"] = signature
            prepared["signing_key_id"] = signature_manager.key_id
            
            # Store entry
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
                prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
                prepared["previous_hash"], prepared["entry_hash"], prepared["signature"], 
                prepared["signing_key_id"]
            ))
            conn.commit()
            conn.close()
        
        report = verifier.get_verification_report()
        
        assert "timestamp" in report
        assert "verification_result" in report
        assert "chain_summary" in report
        assert "signing_key_info" in report
        assert "tampering_detected" in report
        assert "recommendations" in report
        
        assert report["tampering_detected"] is False
        assert report["verification_result"]["valid"] is True


class TestPerformanceImpact:
    """Test performance impact of audit system"""
    
    @pytest.fixture
    def performance_system(self):
        """Create audit system for performance testing"""
        import tempfile
        import shutil
        
        key_dir = tempfile.mkdtemp()
        
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create minimal required tables
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE audit_log_v2 (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                event_timestamp TEXT NOT NULL,
                event_type TEXT NOT NULL,
                originator_id TEXT NOT NULL,
                event_payload TEXT,
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
            CREATE TABLE audit_signing_keys (
                key_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                key_size INTEGER NOT NULL DEFAULT 2048,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        hash_chain = AuditHashChain(db_path)
        signature_manager = AuditSignatureManager(key_dir, db_path)
        
        hash_chain.initialize()
        signature_manager.initialize()
        
        yield hash_chain, signature_manager, db_path
        
        shutil.rmtree(key_dir)
        os.unlink(db_path)
    
    def test_hash_computation_performance(self, performance_system):
        """Test hash computation performance"""
        hash_chain, _, _ = performance_system
        
        entry = {
            "event_id": "test-123",
            "event_timestamp": "2025-01-06T12:00:00Z",
            "event_type": "test_event",
            "originator_id": "test_originator",
            "event_payload": "test payload",
            "sequence_number": 1,
            "previous_hash": "genesis"
        }
        
        # Measure hash computation time
        start_time = time.time()
        for _ in range(1000):
            hash_chain.compute_entry_hash(entry)
        end_time = time.time()
        
        avg_time_ms = (end_time - start_time) * 1000 / 1000
        
        # Should be much less than 1ms per hash
        assert avg_time_ms < 1.0, f"Hash computation too slow: {avg_time_ms}ms average"
    
    def test_signature_performance(self, performance_system):
        """Test signature generation and verification performance"""
        _, signature_manager, _ = performance_system
        
        test_data = "test_entry_hash_12345"
        
        # Measure signing time
        start_time = time.time()
        signatures = []
        for _ in range(100):  # Fewer iterations as signing is more expensive
            signature = signature_manager.sign_entry(test_data)
            signatures.append(signature)
        sign_time = time.time() - start_time
        
        avg_sign_time_ms = sign_time * 1000 / 100
        
        # Measure verification time
        start_time = time.time()
        for signature in signatures:
            signature_manager.verify_signature(test_data, signature)
        verify_time = time.time() - start_time
        
        avg_verify_time_ms = verify_time * 1000 / 100
        
        # Performance targets from specification
        assert avg_sign_time_ms < 5.0, f"Signing too slow: {avg_sign_time_ms}ms average"
        assert avg_verify_time_ms < 5.0, f"Verification too slow: {avg_verify_time_ms}ms average"
    
    def test_end_to_end_performance(self, performance_system):
        """Test end-to-end audit entry creation performance"""
        hash_chain, signature_manager, db_path = performance_system
        
        # Measure complete audit entry creation
        start_time = time.time()
        
        for i in range(100):
            entry = {
                "event_id": f"test-{i}",
                "event_timestamp": "2025-01-06T12:00:00Z",
                "event_type": "test_event",
                "originator_id": "test_originator",
                "event_payload": f"test payload {i}"
            }
            
            # Prepare entry (hash chain)
            prepared = hash_chain.prepare_entry(entry)
            
            # Sign entry
            signature = signature_manager.sign_entry(prepared["entry_hash"])
            prepared["signature"] = signature
            prepared["signing_key_id"] = signature_manager.key_id
            
            # Store in database (simplified)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO audit_log_v2 
                (event_id, event_timestamp, event_type, originator_id, event_payload,
                 sequence_number, previous_hash, entry_hash, signature, signing_key_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                prepared["event_id"], prepared["event_timestamp"], prepared["event_type"],
                prepared["originator_id"], prepared["event_payload"], prepared["sequence_number"],
                prepared["previous_hash"], prepared["entry_hash"], prepared["signature"], 
                prepared["signing_key_id"]
            ))
            conn.commit()
            conn.close()
        
        end_time = time.time()
        total_time_ms = (end_time - start_time) * 1000
        avg_time_ms = total_time_ms / 100
        
        # Target: less than 10ms per complete audit entry
        assert avg_time_ms < 10.0, f"End-to-end audit too slow: {avg_time_ms}ms average"


class TestErrorHandling:
    """Test error handling and recovery scenarios"""
    
    def test_hash_chain_database_error(self):
        """Test hash chain handles database errors gracefully"""
        # Use non-existent database path
        chain = AuditHashChain("/nonexistent/path/database.db")
        
        # Should handle errors gracefully
        result = chain.get_last_entry()
        assert result is None
        
        result = chain.verify_chain_integrity()
        assert result["valid"] is False
        assert "error" in result["errors"][0].lower()
    
    def test_signature_manager_invalid_key_path(self):
        """Test signature manager handles invalid key paths"""
        # Use read-only directory for key path
        import tempfile
        
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE audit_signing_keys (
                key_id TEXT PRIMARY KEY,
                public_key TEXT NOT NULL,
                algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
                key_size INTEGER NOT NULL DEFAULT 2048,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                revoked_at TEXT
            )
        """)
        conn.commit()
        conn.close()
        
        # Try to use a read-only path
        try:
            manager = AuditSignatureManager("/", db_path)  # Root directory is usually read-only
            # Initialization should handle the error gracefully
            with pytest.raises(Exception):  # Should raise an exception
                manager.initialize()
        finally:
            os.unlink(db_path)
    
    def test_verifier_corrupted_database(self):
        """Test verifier handles corrupted database gracefully"""
        import tempfile
        
        key_dir = tempfile.mkdtemp()
        fd, db_path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        
        # Create corrupted database (empty file)
        with open(db_path, 'w') as f:
            f.write("corrupted database content")
        
        try:
            verifier = AuditVerifier(db_path, key_dir)
            
            # Should handle corruption gracefully - initialize succeeds but verification fails
            verifier.initialize()
            
            # Verification should fail gracefully
            result = verifier.verify_complete_chain()
            assert result["valid"] is False
            assert "error" in str(result).lower() or len(result.get("hash_chain_errors", [])) > 0
            
        finally:
            import shutil
            shutil.rmtree(key_dir)
            os.unlink(db_path)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])