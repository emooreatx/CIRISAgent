-- Migration to add task signing fields
-- This allows tracking which WA signed each task for security

-- Add signing fields to tasks table
ALTER TABLE tasks ADD COLUMN signed_by TEXT;
ALTER TABLE tasks ADD COLUMN signature TEXT;
ALTER TABLE tasks ADD COLUMN signed_at TEXT;

-- Create index for signed_by to quickly find tasks by signer
CREATE INDEX IF NOT EXISTS idx_tasks_signed_by ON tasks(signed_by);