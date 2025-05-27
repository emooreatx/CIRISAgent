# v1 minimal table schemas for CIRISAgent

tasks_table_v1 = '''
CREATE TABLE IF NOT EXISTS tasks (
    task_id TEXT PRIMARY KEY,
    description TEXT NOT NULL,
    status TEXT NOT NULL,
    priority INTEGER DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    parent_task_id TEXT,
    context_json TEXT,
    outcome_json TEXT
);
'''

thoughts_table_v1 = '''
CREATE TABLE IF NOT EXISTS thoughts (
    thought_id TEXT PRIMARY KEY,
    source_task_id TEXT NOT NULL,
    thought_type TEXT DEFAULT 'standard',
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    round_number INTEGER DEFAULT 0,
    content TEXT NOT NULL,
    context_json TEXT,
    ponder_count INTEGER DEFAULT 0,
    ponder_notes_json TEXT,
    parent_thought_id TEXT,
    final_action_json TEXT,
    FOREIGN KEY (source_task_id) REFERENCES tasks(task_id)
);
'''

feedback_mappings_table_v1 = '''
CREATE TABLE IF NOT EXISTS feedback_mappings (
    feedback_id TEXT PRIMARY KEY,
    source_message_id TEXT,
    target_thought_id TEXT,
    feedback_type TEXT,  -- 'identity' or 'environment'
    created_at TEXT NOT NULL
);
'''
