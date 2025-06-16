"""
Audit verification schemas for CIRIS Engine.

Provides visibility into cryptographic audit trail verification status,
ensuring the AI can see when its audit logs were last verified and their integrity status.
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

from .versioning import SchemaVersion


class VerificationResult(str, Enum):
    """Result of cryptographic verification."""
    VALID = "valid"
    INVALID = "invalid"
    PARTIAL = "partial"  # Some records verified, some failed
    ERROR = "error"  # Verification process failed
    PENDING = "pending"  # Verification in progress
    NOT_PERFORMED = "not_performed"  # No verification done yet


class AuditIntegrityStatus(BaseModel):
    """Status of a single audit record's integrity."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    record_id: str = Field(..., description="Unique identifier of the audit record")
    timestamp: datetime = Field(..., description="When the record was created")
    signature_valid: bool = Field(..., description="Whether cryptographic signature is valid")
    hash_valid: bool = Field(..., description="Whether content hash matches")
    chain_valid: bool = Field(..., description="Whether chain of records is intact")
    
    # Details if invalid
    failure_reason: Optional[str] = Field(default=None, description="Why verification failed")
    tamper_indicators: List[str] = Field(default_factory=list, description="Signs of tampering detected")
    
    # Metadata
    verified_at: datetime = Field(default_factory=datetime.utcnow, description="When this was verified")
    verified_by: str = Field(..., description="Service that performed verification")


class AuditVerificationReport(BaseModel):
    """Comprehensive audit trail verification report."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Overall status
    result: VerificationResult = Field(..., description="Overall verification result")
    is_valid: bool = Field(..., description="Simple boolean - is audit trail valid?")
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in verification (0-1)")
    
    # Verification details
    total_records: int = Field(..., description="Total audit records in system")
    verified_records: int = Field(..., description="Number of records verified")
    valid_records: int = Field(..., description="Number of valid records")
    invalid_records: int = Field(..., description="Number of invalid records")
    
    # Timing
    verification_started: datetime = Field(..., description="When verification began")
    verification_completed: datetime = Field(..., description="When verification finished")
    duration_seconds: float = Field(..., description="Time taken to verify")
    
    # Chain integrity
    chain_intact: bool = Field(..., description="Whether the audit chain is unbroken")
    last_valid_record_id: Optional[str] = Field(default=None, description="Last known good record")
    first_invalid_record_id: Optional[str] = Field(default=None, description="First detected bad record")
    
    # Invalid record details
    invalid_record_details: List[AuditIntegrityStatus] = Field(
        default_factory=list, 
        description="Details of invalid records found"
    )
    
    # Security metadata
    verifier_service_id: str = Field(..., description="ID of service that performed verification")
    verifier_public_key_hash: str = Field(..., description="Hash of verifier's public key")
    verification_method: str = Field(default="RSA-SHA256", description="Cryptographic method used")
    
    # Recommendations
    requires_immediate_action: bool = Field(default=False, description="Whether urgent action needed")
    recommended_actions: List[str] = Field(default_factory=list, description="Suggested remediation steps")
    
    @property
    def integrity_percentage(self) -> float:
        """Calculate percentage of records that are valid."""
        if self.verified_records == 0:
            return 0.0
        return (self.valid_records / self.verified_records) * 100.0
    
    @property
    def time_since_verification(self) -> float:
        """Seconds since verification completed."""
        return (datetime.utcnow() - self.verification_completed).total_seconds()


class ContinuousVerificationStatus(BaseModel):
    """Status of continuous audit verification process."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Current status
    is_running: bool = Field(..., description="Whether continuous verification is active")
    last_verification: Optional[AuditVerificationReport] = Field(
        default=None, 
        description="Most recent verification report"
    )
    
    # Schedule
    verification_interval_seconds: int = Field(default=3600, description="How often to verify")
    next_scheduled_verification: Optional[datetime] = Field(default=None, description="Next verification time")
    
    # History
    verification_history: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Summary of recent verifications"
    )
    consecutive_valid_verifications: int = Field(default=0, description="Valid verifications in a row")
    consecutive_invalid_verifications: int = Field(default=0, description="Invalid verifications in a row")
    
    # Alerts
    alert_on_invalid: bool = Field(default=True, description="Whether to alert on invalid audit")
    alert_threshold_percentage: float = Field(default=95.0, description="Alert if integrity drops below %")
    current_alerts: List[str] = Field(default_factory=list, description="Active integrity alerts")
    
    @property
    def is_healthy(self) -> bool:
        """Check if audit verification is healthy."""
        if not self.last_verification:
            return True  # Assume healthy if no verification yet
        return (
            self.last_verification.is_valid and 
            self.last_verification.integrity_percentage >= self.alert_threshold_percentage
        )
    
    @property
    def needs_immediate_verification(self) -> bool:
        """Check if immediate verification is needed."""
        if not self.last_verification:
            return True
        
        time_since = (datetime.utcnow() - self.last_verification.verification_completed).total_seconds()
        return (
            time_since > self.verification_interval_seconds * 2 or  # Overdue
            not self.last_verification.is_valid or  # Last was invalid
            self.consecutive_invalid_verifications > 0  # Recent failures
        )


class AuditVerificationRequest(BaseModel):
    """Request to verify audit trail integrity."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
    
    # Scope
    verify_all: bool = Field(default=True, description="Verify entire audit trail")
    start_time: Optional[datetime] = Field(default=None, description="Start of time range to verify")
    end_time: Optional[datetime] = Field(default=None, description="End of time range to verify")
    record_types: Optional[List[str]] = Field(default=None, description="Specific record types to verify")
    
    # Options
    deep_verification: bool = Field(default=True, description="Perform deep cryptographic checks")
    verify_chain: bool = Field(default=True, description="Verify chain integrity")
    verify_signatures: bool = Field(default=True, description="Verify all signatures")
    
    # Performance
    max_records: Optional[int] = Field(default=None, description="Maximum records to verify")
    timeout_seconds: int = Field(default=300, description="Maximum time for verification")
    
    # Reporting
    include_valid_records: bool = Field(default=False, description="Include valid records in report")
    summary_only: bool = Field(default=False, description="Return summary without details")


__all__ = [
    "VerificationResult",
    "AuditIntegrityStatus", 
    "AuditVerificationReport",
    "ContinuousVerificationStatus",
    "AuditVerificationRequest",
]