# Configuration Management

The configuration module provides enterprise-grade configuration management with multi-source loading, dynamic updates, type safety, and environment-aware operation. The system supports hierarchical configuration merging with runtime validation and hot-reloading capabilities.

## Architecture

### Core Components

#### Configuration Manager (`config_manager.py`)
Singleton-based central configuration management with thread-safe initialization.

#### Configuration Loader (`config_loader.py`)
YAML file processing with validation, merging, and error handling.

#### Dynamic Configuration (`dynamic_config.py`)
Runtime configuration updates with validation and rollback capabilities.

#### Environment Utilities (`env_utils.py`)
Environment variable processing with type conversion and nested key support.

## Key Features

### Multi-Source Configuration Hierarchy

#### Precedence Order (highest to lowest)
1. **Environment Variables** - Runtime overrides
2. **Profile Overlays** - Agent-specific configuration (`ciris_profiles/{profile}.yaml`)
3. **Base Configuration** - `config/base.yaml`
4. **Application Defaults** - Built-in sensible defaults

```python
class ConfigLoader:
    @staticmethod
    async def load_config(
        config_path: Optional[Path] = None,
        profile_name: str = "default",
    ) -> AppConfig:
        # 1. Load base configuration
        base_config = await load_base_config(config_path)
        
        # 2. Apply profile overlay
        profile_config = await load_profile_config(profile_name)
        merged_config = deep_merge(base_config, profile_config)
        
        # 3. Apply environment variable overrides
        final_config = apply_env_overrides(merged_config)
        
        return AppConfig(**final_config)
```

### Type-Safe Configuration Access

#### Pydantic Model Integration
```python
class AppConfig(BaseModel):
    database: DatabaseConfig
    workflow: WorkflowConfig  
    llm_services: LLMServicesConfig
    guardrails: GuardrailsConfig
    audit: AuditConfig
    telemetry: TelemetryConfig

class LLMServicesConfig(BaseModel):
    openai: OpenAIConfig
    timeout_seconds: int = 30
    max_retries: int = 3

class OpenAIConfig(BaseModel):
    api_key: str = ""
    model_name: str = "gpt-4"
    base_url: Optional[str] = None
    instructor_mode: str = "JSON"
    
    def load_env_vars(self) -> None:
        """Automatically load from environment variables"""
        if not self.api_key:
            self.api_key = get_env_var("OPENAI_API_KEY", "")
        if not self.base_url:
            self.base_url = get_env_var("OPENAI_BASE_URL")
```

#### Thread-Safe Singleton Pattern
```python
# Global configuration access
from ciris_engine.config import get_config

config = get_config()  # Thread-safe singleton instance
llm_model = config.llm_services.openai.model_name
database_path = config.database.db_filename
```

### Dynamic Configuration Updates

#### Hot Reloading Without Restart
```python
class ConfigManager:
    async def update_config(self, path: str, value: Any) -> None:
        """Apply configuration updates using dot notation"""
        async with self._lock:
            # Update configuration at specified path
            # Example: "database.db_filename", "new_database.db"
            current_config = copy.deepcopy(self._config.dict())
            set_nested_value(current_config, path, value)
            
            # Validate and apply
            self._config = AppConfig(**current_config)
            logger.info(f"Configuration updated: {path} = {value}")

    async def reload_profile(self, profile_name: str, config_path: Path | None = None) -> None:
        """Hot-reload agent profiles without restart"""
        async with self._lock:
            new_config = await ConfigLoader.load_config(config_path, profile_name)
            self._config = new_config
            logger.info(f"Profile reloaded: {profile_name}")
```

#### Profile-Based Configuration
```python
# Runtime profile switching
config_manager = ConfigManager(config)
await config_manager.reload_profile("teacher")  # Switch to teacher profile
await config_manager.reload_profile("student")  # Switch to student profile

# Configuration watching (extensible)
async def on_config_change(config: AppConfig):
    logger.info("Configuration changed, reinitializing services")
    await reinitialize_services(config)

await config_manager.watch_config_changes(on_config_change)
```

### Environment Variable Integration

#### Flexible Environment Variable Support
```python
# Environment utilities with .env file support
def load_env_file(path: Path | str = Path(".env"), *, force: bool = False) -> None:
    """Load environment variables from .env file"""
    
def get_env_var(name: str, default: Optional[str] = None) -> Optional[str]:
    """Get environment variable with OS priority over .env"""

def get_discord_channel_id(config: Optional[object] = None) -> Optional[str]:
    """Smart Discord channel ID resolution"""
```

#### Environment Variable Examples
```bash
# LLM configuration
export OPENAI_API_KEY="sk-your-key-here"
export OPENAI_BASE_URL="https://api.openai.com/v1"

# Database configuration
export CIRIS_DB_PATH="/custom/path/ciris.db"

# Feature toggles
export CIRIS_TELEMETRY_ENABLED=true
export CIRIS_GUARDRAILS_ENABLED=false
```

## Configuration File Structure

### Base Configuration (`config/base.yaml`)
```yaml
database:
  db_filename: "ciris.db"
  data_directory: "data"
  graph_memory_filename: "graph_memory.db"

workflow:
  max_rounds: 5
  timeout_seconds: 30
  retry_limit: 3

llm_services:
  openai:
    model_name: "gpt-4"
    instructor_mode: "JSON"
    timeout_seconds: 30
    max_retries: 3

guardrails:
  entropy: enabled
  coherence: enabled
  rate_limit_observe:
    max_messages_per_cycle: 10

audit:
  enabled: true
  log_filename: "audit_logs.jsonl"
  retention_days: 90

telemetry:
  enabled: false  # Secure by default
  collection_interval_ms: 1000
```

### Agent Profile Configuration
```yaml
# ciris_profiles/teacher.yaml
name: "teacher"
description: "Educational assistance agent"
dsdma_identifier: "BaseDSDMA"

permitted_actions:
  - "speak"
  - "observe"
  - "memorize"
  - "recall"
  - "ponder"
  - "defer"
  - "tool"

action_selection_pdma_overrides:
  system_header: |
    You are a teacher assistant for the CIRIS project.
    Please keep in mind you are humble and kind...

guardrails_config:
  entropy: enabled
  coherence: enabled
  rate_limit_observe:
    max_messages_per_cycle: 15
```

## Agent Profile System

### Profile Structure
```python
class AgentProfile(BaseModel):
    name: str
    description: Optional[str] = None
    dsdma_identifier: Optional[str] = None
    dsdma_kwargs: Optional[Dict[str, Any]] = None
    permitted_actions: List[HandlerActionType] = Field(default_factory=list)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    guardrails_config: Optional[GuardrailsConfig] = None
```

### Profile Loading and Validation
```python
# Profile loading with validation
async def load_profile(profile_path: Path | str) -> AgentProfile:
    profile_data = await load_yaml_file(profile_path)
    
    # Convert action strings to enums
    if "permitted_actions" in profile_data:
        profile_data["permitted_actions"] = [
            HandlerActionType(action) for action in profile_data["permitted_actions"]
        ]
    
    return AgentProfile(**profile_data)

# Integration with configuration system
profile = await load_profile(f"ciris_profiles/{profile_name}.yaml")
config_overrides = profile.get_config_overrides()
final_config = deep_merge(base_config, config_overrides)
```

## Usage Examples

### Basic Configuration Access
```python
from ciris_engine.config import get_config

# Get global configuration
config = get_config()

# Access configuration values
db_path = config.database.db_filename
model_name = config.llm_services.openai.model_name
max_rounds = config.workflow.max_rounds

# Use in service initialization
llm_service = OpenAILLMService(
    api_key=config.llm_services.openai.api_key,
    model_name=config.llm_services.openai.model_name,
    timeout=config.llm_services.timeout_seconds
)
```

### Dynamic Configuration Management
```python
from ciris_engine.config import ConfigManager

# Initialize dynamic configuration
config = get_config()
config_manager = ConfigManager(config)

# Runtime configuration updates
await config_manager.update_config("workflow.max_rounds", 10)
await config_manager.update_config("llm_services.openai.model_name", "gpt-4-turbo")

# Profile hot-reloading
await config_manager.reload_profile("student")
await config_manager.reload_profile("teacher")
```

### Profile-Based Configuration Loading
```python
from ciris_engine.config import ConfigLoader

# Load configuration with specific profile
config = await ConfigLoader.load_config(
    config_path=Path("config/base.yaml"),
    profile_name="teacher"
)

# Profile determines available actions and behavior
permitted_actions = config.profile.permitted_actions
dsdma_config = config.profile.dsdma_kwargs
```

### Environment Integration
```python
from ciris_engine.config import load_env_file, get_env_var

# Load environment variables from .env file
load_env_file(".env")

# Access environment variables with fallbacks
api_key = get_env_var("OPENAI_API_KEY", "default-key")
channel_id = get_discord_channel_id(config)

# Automatic environment loading in schemas
config.llm_services.openai.load_env_vars()
```

## Error Handling and Validation

### Comprehensive Error Management
```python
# Configuration loading with graceful fallbacks
try:
    config = await ConfigLoader.load_config(profile_name="custom")
except Exception as e:
    logger.warning(f"Failed to load custom profile: {e}")
    config = await ConfigLoader.load_config(profile_name="default")

# Environment variable validation
config.llm_services.openai.load_env_vars()
if not config.llm_services.openai.api_key:
    raise ConfigurationError("OpenAI API key not configured")

# Path validation and creation
db_path = get_sqlite_db_full_path()
os.makedirs(os.path.dirname(db_path), exist_ok=True)
```

### Configuration Validation
```python
# Pydantic validation with custom validators
class WorkflowConfig(BaseModel):
    max_rounds: int = Field(default=5, ge=1, le=50)
    timeout_seconds: int = Field(default=30, ge=1, le=300)
    
    @validator('max_rounds')
    def validate_max_rounds(cls, v):
        if v > 20:
            logger.warning(f"High max_rounds value: {v}")
        return v

# Runtime validation
def validate_configuration(config: AppConfig) -> List[str]:
    errors = []
    
    if not config.llm_services.openai.api_key:
        errors.append("OpenAI API key is required")
    
    if config.workflow.max_rounds > 20:
        errors.append("Max rounds exceeds recommended limit")
    
    return errors
```

## Agent Self-Configuration

### Memory-Based Configuration Management

The CIRIS Agent can modify its own configuration through the memory system using the **Agent Configuration Service**:

```python
class AgentConfigService:
    """Service enabling agents to modify their own configuration through memory operations"""
    
    async def memorize_config_change(
        self,
        config_path: str,
        new_value: Any,
        rationale: str,
        requester_id: str = "agent"
    ) -> bool:
        """Memorize a configuration change request for later application"""
        
    async def apply_memorized_config_changes(self) -> List[Dict[str, Any]]:
        """Apply all pending configuration changes stored in memory"""
        
    async def recall_config_history(self, config_path: Optional[str] = None) -> List[Dict[str, Any]]:
        """Recall configuration change history from memory"""
```

### Agent-Modifiable Configuration Paths

#### Allowed Paths
- `workflow.max_rounds` - Maximum ponder rounds
- `workflow.timeout_seconds` - Operation timeouts
- `guardrails.entropy.threshold` - Entropy validation threshold
- `guardrails.coherence.threshold` - Coherence validation threshold
- `llm_services.openai.model_name` - Active model selection
- `llm_services.openai.instructor_mode` - Instructor output mode
- `audit.retention_days` - Audit log retention period
- `telemetry.collection_interval_ms` - Telemetry collection frequency

#### Restricted Paths (require special authorization)
- `llm_services.openai.api_key` - API credentials
- `database.db_filename` - Database paths
- `secrets.storage_path` - Secrets storage location

### Self-Configuration Workflow

#### 1. Configuration Introspection
```python
# Agent queries current configuration
config_summary = await agent_config_service.get_current_config_summary()

# Agent recalls configuration history
history = await agent_config_service.recall_config_history(
    config_path="workflow.max_rounds",
    limit=10
)
```

#### 2. Memory-Based Configuration Changes
```python
# Agent memorizes a configuration change
await agent_config_service.memorize_config_change(
    config_path="workflow.max_rounds",
    new_value=10,
    rationale="Increasing max rounds for complex reasoning tasks"
)

# Changes are applied through memory processing
results = await agent_config_service.apply_memorized_config_changes()
```

#### 3. Configuration Memory Schema
```python
# Configuration changes stored as graph nodes
GraphNode(
    node_id="config_change:workflow.max_rounds:2024-01-15T10:30:00",
    node_type=NodeType.CONCEPT,
    scope=GraphScope.IDENTITY,
    attributes={
        "config_path": "workflow.max_rounds",
        "new_value": 8,
        "current_value": 5,
        "rationale": "Increasing rounds for complex tasks",
        "requester_id": "agent",
        "timestamp": "2024-01-15T10:30:00",
        "status": "pending",
        "change_type": "configuration_update"
    }
)
```

### Agent Self-Optimization Examples

#### Performance Optimization
```python
# Agent analyzes performance and adjusts configuration
if avg_response_time > target_time:
    await agent_config_service.memorize_config_change(
        "llm_services.openai.model_name",
        "gpt-3.5-turbo",  # Faster model
        "Switching to faster model to improve response time"
    )
```

#### Adaptive Reasoning
```python
# Agent adjusts reasoning depth based on task complexity
if task_complexity > high_threshold:
    await agent_config_service.memorize_config_change(
        "workflow.max_rounds",
        max_rounds + 3,
        "Increasing reasoning rounds for complex task"
    )
```

#### Quality Tuning
```python
# Agent adjusts quality thresholds based on feedback
if user_satisfaction < quality_threshold:
    await agent_config_service.memorize_config_change(
        "guardrails.coherence.threshold",
        coherence_threshold + 0.1,
        "Increasing coherence threshold to improve output quality"
    )
```

## Performance and Best Practices

### Performance Optimization
- **Singleton Pattern**: Single configuration instance per application
- **Lazy Loading**: Configuration loaded only when first accessed
- **Async Operations**: Non-blocking YAML loading and profile switching
- **Caching**: Environment variable and file loading caching

### Best Practices
1. **Use Profiles**: Create specialized profiles for different agent roles
2. **Environment Variables**: Keep sensitive data in environment variables
3. **Validation**: Always validate configuration on startup
4. **Hot Reloading**: Use dynamic configuration for runtime adjustments
5. **Error Handling**: Provide meaningful fallbacks for missing configuration
6. **Type Safety**: Leverage Pydantic models for configuration structure
7. **Agent Self-Configuration**: Enable agents to optimize their own performance through memory
8. **Documentation**: Document configuration options in schema models

---

The configuration module provides a robust, flexible foundation for managing complex agent configurations across different runtime environments while maintaining security, performance, and ease of use with comprehensive profile support, dynamic updates, and agent self-configuration capabilities through the memory system.
