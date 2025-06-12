"""
Audit verifier for tamper detection in signed audit trail system.

Provides comprehensive verification of audit log integrity including
hash chains, digital signatures, and root anchoring.
"""

import sqlite3
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime

from .hash_chain import AuditHashChain
from .signature_manager import AuditSignatureManager

logger = logging.getLogger(__name__)

class AuditVerifier:
    """Verifies audit log integrity and detects tampering"""
    
    def __init__(self, db_path: str, key_path: str) -> None:
        self.db_path = db_path
        self.hash_chain = AuditHashChain(db_path)
        self.signature_manager = AuditSignatureManager(key_path, db_path)
        self._initialized = False
    
    def initialize(self) -> None:
        """Initialize the verifier components"""
        if self._initialized:
            return
            
        self.hash_chain.initialize()
        self.signature_manager.initialize()
        self._initialized = True
        logger.info("Audit verifier initialized")
    
    def verify_complete_chain(self) -> Dict[str, Any]:
        """Perform complete verification of the entire audit chain"""
        if not self._initialized:
            self.initialize()
        
        logger.info("Starting complete audit chain verification")
        start_time = datetime.now()
        
        # Get chain summary
        summary = self.hash_chain.get_chain_summary()
        if summary.get("error"):
            return {
                "valid": False,
                "error": summary["error"],
                "verification_time_ms": 0
            }
        
        total_entries = summary["total_entries"]
        if total_entries == 0:
            return {
                "valid": True,
                "entries_verified": 0,
                "hash_chain_valid": True,
                "signatures_valid": True,
                "verification_time_ms": 0,
                "summary": "Empty audit log"
            }
        
        # Verify hash chain integrity
        chain_result = self.hash_chain.verify_chain_integrity()
        
        # Verify signatures
        signature_result = self._verify_all_signatures()
        
        # Calculate verification time
        end_time = datetime.now()
        verification_time = int((end_time - start_time).total_seconds() * 1000)
        
        # Combine results
        overall_valid = chain_result["valid"] and signature_result["valid"]
        
        result = {
            "valid": overall_valid,
            "entries_verified": total_entries,
            "hash_chain_valid": chain_result["valid"],
            "signatures_valid": signature_result["valid"],
            "verification_time_ms": verification_time,
            "hash_chain_errors": chain_result.get("errors", []),
            "signature_errors": signature_result.get("errors", []),
            "chain_summary": summary
        }
        
        if overall_valid:
            logger.info(f"Audit verification passed: {total_entries} entries in {verification_time}ms")
        else:
            logger.error(f"Audit verification FAILED: {len(chain_result.get('errors', []))} hash + {len(signature_result.get('errors', []))} signature errors")
        
        return result
    
    def verify_entry(self, entry_id: int) -> Dict[str, Any]:
        """Verify a specific audit entry by ID"""
        if not self._initialized:
            self.initialize()
        
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT * FROM audit_log_v2 WHERE entry_id = ?",
                (entry_id,)
            )
            
            row = cursor.fetchone()
            conn.close()
            
            if not row:
                return {
                    "valid": False,
                    "error": f"Entry {entry_id} not found"
                }
            
            entry = dict(row)
            return self._verify_single_entry(entry)
            
        except sqlite3.Error as e:
            logger.error(f"Database error verifying entry {entry_id}: {e}")
            return {
                "valid": False,
                "error": f"Database error: {e}"
            }
    
    def verify_range(self, start_seq: int, end_seq: int) -> Dict[str, Any]:
        """Verify a range of entries by sequence number"""
        if not self._initialized:
            self.initialize()
        
        logger.debug(f"Verifying sequence range {start_seq} to {end_seq}")
        
        # Verify hash chain for range
        chain_result = self.hash_chain.verify_chain_integrity(start_seq, end_seq)
        
        # Verify signatures for range
        signature_result = self._verify_signatures_in_range(start_seq, end_seq)
        
        return {
            "valid": chain_result["valid"] and signature_result["valid"],
            "entries_verified": chain_result["entries_checked"],
            "hash_chain_valid": chain_result["valid"],
            "signatures_valid": signature_result["valid"],
            "hash_chain_errors": chain_result.get("errors", []),
            "signature_errors": signature_result.get("errors", [])
        }
    
    def find_tampering_fast(self) -> Optional[int]:
        """Quickly find the first tampered entry using binary search"""
        if not self._initialized:
            self.initialize()
        
        logger.info("Performing fast tampering detection")
        return self.hash_chain.find_tampering()
    
    def _verify_single_entry(self, entry: Dict[str, Any]) -> Dict[str, Any]:
        """Verify a single entry's hash and signature"""
        errors: List[Any] = []
        
        # Verify entry hash
        computed_hash = self.hash_chain.compute_entry_hash(entry)
        if computed_hash != entry["entry_hash"]:
            errors.append(f"Entry hash mismatch: computed {computed_hash}, stored {entry['entry_hash']}")
        
        # Verify signature
        if not self.signature_manager.verify_signature(
            entry["entry_hash"], 
            entry["signature"], 
            entry["signing_key_id"]
        ):
            errors.append(f"Invalid signature for entry {entry['entry_id']}")
        
        return {
            "valid": len(errors) == 0,
            "entry_id": entry["entry_id"],
            "sequence_number": entry["sequence_number"],
            "errors": errors
        }
    
    def _verify_all_signatures(self) -> Dict[str, Any]:
        """Verify signatures for all entries in the audit log"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT entry_id, entry_hash, signature, signing_key_id 
                FROM audit_log_v2 
                ORDER BY sequence_number
            """)
            
            entries = cursor.fetchall()
            conn.close()
            
            errors: List[Any] = []
            verified_count = 0
            
            for entry in entries:
                if self.signature_manager.verify_signature(
                    entry["entry_hash"],
                    entry["signature"],
                    entry["signing_key_id"]
                ):
                    verified_count += 1
                else:
                    errors.append(f"Invalid signature for entry {entry['entry_id']}")
            
            return {
                "valid": len(errors) == 0,
                "verified_count": verified_count,
                "total_count": len(entries),
                "errors": errors
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error verifying signatures: {e}")
            return {
                "valid": False,
                "verified_count": 0,
                "total_count": 0,
                "errors": [f"Database error: {e}"]
            }
    
    def _verify_signatures_in_range(self, start_seq: int, end_seq: int) -> Dict[str, Any]:
        """Verify signatures for entries in a specific sequence range"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT entry_id, entry_hash, signature, signing_key_id 
                FROM audit_log_v2 
                WHERE sequence_number >= ? AND sequence_number <= ?
                ORDER BY sequence_number
            """, (start_seq, end_seq))
            
            entries = cursor.fetchall()
            conn.close()
            
            errors: List[Any] = []
            verified_count = 0
            
            for entry in entries:
                if self.signature_manager.verify_signature(
                    entry["entry_hash"],
                    entry["signature"],
                    entry["signing_key_id"]
                ):
                    verified_count += 1
                else:
                    errors.append(f"Invalid signature for entry {entry['entry_id']} (seq {start_seq}-{end_seq})")
            
            return {
                "valid": len(errors) == 0,
                "verified_count": verified_count,
                "total_count": len(entries),
                "errors": errors
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error verifying range signatures: {e}")
            return {
                "valid": False,
                "verified_count": 0,
                "total_count": 0,
                "errors": [f"Database error: {e}"]
            }
    
    def get_verification_report(self) -> Dict[str, Any]:
        """Generate a comprehensive verification report"""
        if not self._initialized:
            self.initialize()
        
        logger.info("Generating comprehensive audit verification report")
        
        chain_summary = self.hash_chain.get_chain_summary()
        
        verification_result = self.verify_complete_chain()
        
        key_info = self.signature_manager.get_key_info()
        
        first_tampered = self.find_tampering_fast()
        
        report: Dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "verification_result": verification_result,
            "chain_summary": chain_summary,
            "signing_key_info": key_info,
            "tampering_detected": first_tampered is not None,
            "first_tampered_sequence": first_tampered,
            "recommendations": []
        }
        
        if not verification_result["valid"]:
            report["recommendations"].append("CRITICAL: Audit log integrity compromised - investigate immediately")
        
        if first_tampered:
            report["recommendations"].append(f"Tampering detected at sequence {first_tampered} - verify backup logs")
        
        if verification_result.get("verification_time_ms", 0) > 10000:
            report["recommendations"].append("Verification taking too long - consider archiving old entries")
        
        if chain_summary.get("total_entries", 0) > 100000:
            report["recommendations"].append("Large audit log - consider periodic archiving")
        
        if not key_info.get("active", False):
            report["recommendations"].append("WARNING: Signing key is revoked or inactive")
        
        return report
    
    def verify_root_anchors(self) -> Dict[str, Any]:
        """Verify the integrity of root hash anchors"""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute("""
                SELECT root_id, sequence_start, sequence_end, root_hash, timestamp
                FROM audit_roots 
                ORDER BY sequence_start
            """)
            
            roots = cursor.fetchall()
            conn.close()
            
            if not roots:
                return {
                    "valid": True,
                    "verified_count": 0,
                    "message": "No root anchors found"
                }
            
            errors: List[Any] = []
            verified_count = 0
            
            for root in roots:
                range_result = self.verify_range(root["sequence_start"], root["sequence_end"])
                
                if range_result["valid"]:
                    verified_count += 1
                else:
                    errors.append(f"Root {root['root_id']} invalid: range {root['sequence_start']}-{root['sequence_end']} compromised")
            
            return {
                "valid": len(errors) == 0,
                "verified_count": verified_count,
                "total_count": len(roots),
                "errors": errors
            }
            
        except sqlite3.Error as e:
            logger.error(f"Database error verifying root anchors: {e}")
            return {
                "valid": False,
                "verified_count": 0,
                "total_count": 0,
                "errors": [f"Database error: {e}"]
            }