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

graph_nodes_table_v1 = '''
CREATE TABLE IF NOT EXISTS graph_nodes (
    node_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    node_type TEXT NOT NULL,
    attributes_json TEXT,
    version INTEGER DEFAULT 1,
    updated_by TEXT,
    updated_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (node_id, scope)
);
CREATE INDEX IF NOT EXISTS idx_graph_nodes_scope ON graph_nodes(scope);
'''

graph_edges_table_v1 = '''
CREATE TABLE IF NOT EXISTS graph_edges (
    edge_id TEXT PRIMARY KEY,
    source_node_id TEXT NOT NULL,
    target_node_id TEXT NOT NULL,
    scope TEXT NOT NULL,
    relationship TEXT NOT NULL,
    weight REAL DEFAULT 1.0,
    attributes_json TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (source_node_id, scope) REFERENCES graph_nodes(node_id, scope),
    FOREIGN KEY (target_node_id, scope) REFERENCES graph_nodes(node_id, scope)
);
CREATE INDEX IF NOT EXISTS idx_graph_edges_scope ON graph_edges(scope);
CREATE INDEX IF NOT EXISTS idx_graph_edges_source ON graph_edges(source_node_id);
CREATE INDEX IF NOT EXISTS idx_graph_edges_target ON graph_edges(target_node_id);
'''

service_correlations_table_v1 = '''
CREATE TABLE IF NOT EXISTS service_correlations (
    correlation_id TEXT PRIMARY KEY,
    service_type TEXT NOT NULL,
    handler_name TEXT NOT NULL,
    action_type TEXT NOT NULL,
    request_data TEXT,
    response_data TEXT,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_correlations_status ON service_correlations(status);
CREATE INDEX IF NOT EXISTS idx_correlations_handler ON service_correlations(handler_name);
'''
