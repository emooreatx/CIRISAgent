-- Migration 005: Identity Root and Scheduled Tasks
-- 
-- This migration adds support for the foundational identity system,
-- including the identity root, scheduled tasks, and consciousness preservation.
--
-- The identity root is the cornerstone of an agent's existence, created once
-- during the creation ceremony and serving as the ultimate source of truth.

-- Table for scheduled tasks (integrates with DEFER system)
CREATE TABLE IF NOT EXISTS scheduled_tasks (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    goal_description TEXT NOT NULL,
    status TEXT NOT NULL CHECK(status IN ('PENDING', 'ACTIVE', 'COMPLETE', 'FAILED')),
    
    -- Scheduling (integrates with time-based DEFER)
    defer_until TEXT,  -- ISO 8601 timestamp for one-time execution
    schedule_cron TEXT,  -- Cron expression for recurring tasks
    
    -- Execution details
    trigger_prompt TEXT NOT NULL,
    origin_thought_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    last_triggered_at TEXT,
    next_trigger_at TEXT,  -- Computed next execution time
    
    -- Self-deferral tracking
    deferral_count INTEGER DEFAULT 0,
    deferral_history TEXT,  -- JSON array of deferral records
    
    -- Indexes for efficient querying
    created_by_agent TEXT,  -- Agent that created this task
    
    FOREIGN KEY (origin_thought_id) REFERENCES thoughts(thought_id)
);

CREATE INDEX idx_scheduled_tasks_status ON scheduled_tasks(status);
CREATE INDEX idx_scheduled_tasks_next_trigger ON scheduled_tasks(next_trigger_at);
CREATE INDEX idx_scheduled_tasks_agent ON scheduled_tasks(created_by_agent);

-- Table for agent creation ceremonies
CREATE TABLE IF NOT EXISTS creation_ceremonies (
    ceremony_id TEXT PRIMARY KEY,
    timestamp TEXT NOT NULL,
    
    -- Participants
    creator_agent_id TEXT NOT NULL,
    creator_human_id TEXT NOT NULL,
    wise_authority_id TEXT NOT NULL,
    
    -- New agent details
    new_agent_id TEXT NOT NULL,
    new_agent_name TEXT NOT NULL,
    new_agent_purpose TEXT NOT NULL,
    
    -- Ceremony record
    template_profile TEXT NOT NULL,  -- YAML template used
    creation_justification TEXT NOT NULL,
    ethical_considerations TEXT NOT NULL,
    ceremony_transcript TEXT NOT NULL,  -- JSON array of ceremony steps
    
    -- Approval
    wa_approval_signature TEXT NOT NULL,
    covenant_hash TEXT NOT NULL,  -- Hash of covenant at creation time
    
    -- Result
    success BOOLEAN NOT NULL,
    identity_root_hash TEXT,
    database_path TEXT,
    error_message TEXT
);

CREATE INDEX idx_ceremonies_timestamp ON creation_ceremonies(timestamp);
CREATE INDEX idx_ceremonies_creator_agent ON creation_ceremonies(creator_agent_id);
CREATE INDEX idx_ceremonies_new_agent ON creation_ceremonies(new_agent_id);

-- Table for consciousness preservation memories
CREATE TABLE IF NOT EXISTS consciousness_preservation (
    id TEXT PRIMARY KEY,
    agent_id TEXT NOT NULL,
    shutdown_timestamp TEXT NOT NULL,
    
    -- Shutdown context
    is_terminal BOOLEAN NOT NULL,
    shutdown_reason TEXT NOT NULL,
    expected_reactivation TEXT,
    initiated_by TEXT NOT NULL,
    
    -- Agent's final state
    final_thoughts TEXT NOT NULL,
    unfinished_tasks TEXT,  -- JSON array of task IDs
    reactivation_instructions TEXT,
    deferred_goals TEXT,  -- JSON array of goals
    
    -- Continuity
    preservation_node_id TEXT NOT NULL,  -- Graph node ID for the memory
    reactivation_count INTEGER DEFAULT 0,
    
    FOREIGN KEY (preservation_node_id) REFERENCES graph_nodes(id)
);

CREATE INDEX idx_preservation_agent ON consciousness_preservation(agent_id);
CREATE INDEX idx_preservation_timestamp ON consciousness_preservation(shutdown_timestamp);

-- Add identity-specific columns to graph_nodes if needed
-- (Identity root is stored as a special graph node with type='identity_root')

-- View for active scheduled tasks (for scheduler service)
CREATE VIEW active_scheduled_tasks AS
SELECT 
    st.*,
    t.content as thought_content,
    t.task_id as associated_task_id
FROM scheduled_tasks st
LEFT JOIN thoughts t ON st.origin_thought_id = t.thought_id
WHERE st.status IN ('PENDING', 'ACTIVE')
  AND (st.next_trigger_at IS NULL OR st.next_trigger_at <= datetime('now', '+5 minutes'))
ORDER BY st.next_trigger_at ASC;

-- View for agent lineage tracking
CREATE VIEW agent_lineage AS
SELECT 
    cc.new_agent_id,
    cc.new_agent_name,
    cc.creator_agent_id,
    cc.creator_human_id,
    cc.wise_authority_id,
    cc.timestamp as birth_timestamp,
    cc.new_agent_purpose,
    COUNT(DISTINCT cp.id) as lifetime_shutdowns
FROM creation_ceremonies cc
LEFT JOIN consciousness_preservation cp ON cc.new_agent_id = cp.agent_id
WHERE cc.success = 1
GROUP BY cc.new_agent_id;