-- Migration 003: Signed Audit Trail System
-- Adds cryptographic integrity to audit logs with hash chaining and digital signatures

-- Create the new audit log table with integrity fields
CREATE TABLE IF NOT EXISTS audit_log_v2 (
    entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT NOT NULL UNIQUE,              -- UUID for the event
    event_timestamp TEXT NOT NULL,              -- ISO8601
    event_type TEXT NOT NULL,
    originator_id TEXT NOT NULL,
    event_payload TEXT,                         -- JSON payload
    
    -- Hash chain fields
    sequence_number INTEGER NOT NULL,           -- Monotonic counter
    previous_hash TEXT NOT NULL,                -- SHA-256 of previous entry
    entry_hash TEXT NOT NULL,                   -- SHA-256 of this entry's content
    
    -- Signature fields
    signature TEXT NOT NULL,                    -- Base64 encoded signature
    signing_key_id TEXT NOT NULL,               -- Key used to sign
    
    -- Indexing
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    -- Constraints
    UNIQUE(sequence_number),
    CHECK(sequence_number > 0)
);

-- Create indexes for efficient querying
CREATE INDEX IF NOT EXISTS idx_audit_event_type ON audit_log_v2(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_timestamp ON audit_log_v2(event_timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_originator ON audit_log_v2(originator_id);
CREATE INDEX IF NOT EXISTS idx_audit_sequence ON audit_log_v2(sequence_number);

-- Root hash anchoring table for periodic integrity checkpoints
CREATE TABLE IF NOT EXISTS audit_roots (
    root_id INTEGER PRIMARY KEY AUTOINCREMENT,
    sequence_start INTEGER NOT NULL,
    sequence_end INTEGER NOT NULL,
    root_hash TEXT NOT NULL,                    -- Merkle root of entries
    timestamp TEXT NOT NULL,
    external_anchor TEXT,                       -- External timestamp proof
    
    UNIQUE(sequence_start, sequence_end)
);

-- Create index for root lookup
CREATE INDEX IF NOT EXISTS idx_audit_roots_range ON audit_roots(sequence_start, sequence_end);

-- Signing keys table for key management
CREATE TABLE IF NOT EXISTS audit_signing_keys (
    key_id TEXT PRIMARY KEY,
    public_key TEXT NOT NULL,                   -- PEM format public key
    algorithm TEXT NOT NULL DEFAULT 'rsa-pss',
    key_size INTEGER NOT NULL DEFAULT 2048,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    revoked_at TEXT,                           -- NULL if active
    
    CHECK(algorithm IN ('rsa-pss', 'ed25519'))
);

-- Create index for active key lookup
CREATE INDEX IF NOT EXISTS idx_audit_keys_active ON audit_signing_keys(created_at) 
WHERE revoked_at IS NULL;