#!/usr/bin/env python3
"""Fix systematic type annotation errors in schema files."""

import re
from pathlib import Path

def fix_file(filepath: Path, replacements: list[tuple[str, str]]):
    """Apply replacements to a file."""
    content = filepath.read_text()
    original = content
    
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    if content != original:
        filepath.write_text(content)
        print(f"Fixed {filepath}")
        return True
    return False

# Fix config_schemas_v1.py
config_schema_replacements = [
    # DatabaseConfig
    (r'db_filename: GuardrailsConfig = Field', 'db_filename: str = Field'),
    (r'data_directory: GuardrailsConfig = DEFAULT_DATA_DIR', 'data_directory: str = DEFAULT_DATA_DIR'),
    (r'graph_memory_filename: GuardrailsConfig = Field', 'graph_memory_filename: str = Field'),
    
    # WorkflowConfig
    (r'max_active_tasks: GuardrailsConfig = Field', 'max_active_tasks: int = Field'),
    (r'max_active_thoughts: GuardrailsConfig = Field\(default=50, description="Maximum thoughts to pull GuardrailsConfigo processing queue per round"\)', 
     'max_active_thoughts: int = Field(default=50, description="Maximum thoughts to pull into processing queue per round")'),
    (r'round_delay_seconds: GuardrailsConfig = Field', 'round_delay_seconds: float = Field'),
    (r'max_rounds: GuardrailsConfig = Field', 'max_rounds: int = Field'),
    (r'DMA_RETRY_LIMIT: GuardrailsConfig = Field', 'DMA_RETRY_LIMIT: int = Field'),
    (r'DMA_TIMEOUT_SECONDS: GuardrailsConfig = Field', 'DMA_TIMEOUT_SECONDS: float = Field'),
    (r'GUARDRAIL_RETRY_LIMIT: GuardrailsConfig = Field', 'GUARDRAIL_RETRY_LIMIT: int = Field'),
    
    # OpenAIConfig
    (r'model_name: GuardrailsConfig = Field', 'model_name: str = Field'),
    (r'timeout_seconds: GuardrailsConfig = Field', 'timeout_seconds: float = Field'),
    (r'max_retries: GuardrailsConfig = Field', 'max_retries: int = Field'),
    (r'api_key_env_var: GuardrailsConfig = Field', 'api_key_env_var: str = Field'),
    (r'inGuardrailsConfiguctor_mode: GuardrailsConfig = Field', 'instructor_mode: str = Field'),
    
    # AgentProfile
    (r'name: GuardrailsConfig\n', 'name: str\n'),
    
    # CIRISNodeConfig
    (r'base_url: GuardrailsConfig = Field', 'base_url: str = Field'),
    (r'timeout_seconds: GuardrailsConfig = Field', 'timeout_seconds: float = Field'),
    (r'max_retries: GuardrailsConfig = Field', 'max_retries: int = Field'),
    
    # NetworkConfig
    (r'peer_discovery_GuardrailsConfigerval: GuardrailsConfig = 300', 'peer_discovery_interval: int = 300'),
    (r'reputation_threshold: GuardrailsConfig = 30', 'reputation_threshold: int = 30'),
    
    # TelemetryConfig
    (r'enabled: GuardrailsConfig = False', 'enabled: bool = False'),
    (r'internal_only: GuardrailsConfig = True', 'internal_only: bool = True'),
    (r'retention_hours: GuardrailsConfig = 1', 'retention_hours: int = 1'),
    (r'snapshot_GuardrailsConfigerval_ms: GuardrailsConfig = 1000', 'snapshot_interval_ms: int = 1000'),
    
    # WisdomConfig
    (r'wa_timeout_hours: GuardrailsConfig = 72', 'wa_timeout_hours: int = 72'),
    (r'allow_universal_guidance: GuardrailsConfig = True', 'allow_universal_guidance: bool = True'),
    (r'minimum_urgency_for_universal: GuardrailsConfig = 80', 'minimum_urgency_for_universal: int = 80'),
    (r'peer_consensus_threshold: GuardrailsConfig = 3', 'peer_consensus_threshold: int = 3'),
    
    # AppConfig
    (r'profile_directory: GuardrailsConfig = Field', 'profile_directory: str = Field'),
    (r'default_profile: GuardrailsConfig = Field', 'default_profile: str = Field'),
]

# Fix action_params_v1.py
action_params_replacements = [
    (r'active: GraphNode = False', 'active: bool = False'),
    (r'context: GraphNode = Field\(default_factory=GraphNode\)', 'context: Dict[str, Any] = Field(default_factory=dict)'),
    (r'content: GraphNode\n', 'content: str\n'),
    (r'name: GraphNode\n', 'name: str\n'),
    (r'reason: GraphNode\n', 'reason: str\n'),
]

# Fix foundational_schemas_v1.py
foundational_replacements = [
    (r'message_id: SchemaVersion\n', 'message_id: str\n'),
    (r'author_id: SchemaVersion\n', 'author_id: str\n'),
    (r'author_name: SchemaVersion\n', 'author_name: str\n'),
    (r'content: SchemaVersion\n', 'content: str\n'),
    (r'channel_id: SchemaVersion\n', 'channel_id: str\n'),
    (r'is_bot: SchemaVersion = False', 'is_bot: bool = False'),
    (r'is_dm: SchemaVersion = False', 'is_dm: bool = False'),
    (r'tokens: SchemaVersion\n', 'tokens: int\n'),
]

# Fix network_schemas_v1.py
network_replacements = [
    (r'agent_id: SchemaVersion\n', 'agent_id: str\n'),
    (r'structural_influence: SchemaVersion = Field', 'structural_influence: int = Field'),
    (r'coherence_stake: SchemaVersion = Field', 'coherence_stake: int = Field'),
    (r'last_seen_epoch: SchemaVersion\n', 'last_seen_epoch: int\n'),
    (r'reputation: SchemaVersion = Field', 'reputation: int = Field'),
]

# Fix graph_schemas_v1.py
graph_replacements = [
    (r'node_id: NodeType\n', 'node_id: str\n'),
    (r'label: NodeType\n', 'label: str\n'),
    (r'created_at: NodeType\n', 'created_at: str\n'),
    (r'updated_at: NodeType\n', 'updated_at: str\n'),
    (r'edge_id: NodeType\n', 'edge_id: str\n'),
    (r'source_id: NodeType\n', 'source_id: str\n'),
    (r'target_id: NodeType\n', 'target_id: str\n'),
    (r'edge_label: NodeType\n', 'edge_label: str\n'),
    (r'created_at: NodeType\n', 'created_at: str\n'),
]

# Apply fixes
base_path = Path('/home/emoore/CIRISAgent/ciris_engine/schemas')

fix_file(base_path / 'config_schemas_v1.py', config_schema_replacements)
fix_file(base_path / 'action_params_v1.py', action_params_replacements)
fix_file(base_path / 'foundational_schemas_v1.py', foundational_replacements)
fix_file(base_path / 'network_schemas_v1.py', network_replacements)
fix_file(base_path / 'graph_schemas_v1.py', graph_replacements)

# Also need to add guardrails_config field to AgentProfile
agent_profile_path = base_path / 'config_schemas_v1.py'
content = agent_profile_path.read_text()
if 'guardrails_config: Optional[GuardrailsConfig] = None' not in content:
    # Add the field after action_selection_pdma_overrides
    content = content.replace(
        'action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)',
        'action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)\n    guardrails_config: Optional[GuardrailsConfig] = None'
    )
    agent_profile_path.write_text(content)
    print("Added guardrails_config field to AgentProfile")

print("Schema type annotation fixes complete!")