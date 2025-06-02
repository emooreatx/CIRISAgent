-- Example migration: add retry_count column to tasks
ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0;
