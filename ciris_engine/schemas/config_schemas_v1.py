from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

from .guardrails_config_v1 import GuardrailsConfig
from .foundational_schemas_v1 import SensitivityLevel

DEFAULT_SQLITE_DB_FILENAME = "ciris_engine.db"
DEFAULT_DATA_DIR = "data"
DEFAULT_OPENAI_MODEL_NAME = "gpt-4o-mini"

class DatabaseConfig(BaseModel):
    """Minimal v1 database configuration."""
    db_filename: str = Field(default=DEFAULT_SQLITE_DB_FILENAME, alias="db_filename")
    data_directory: str = DEFAULT_DATA_DIR
    graph_memory_filename: str = Field(default="graph_memory.pkl", alias="graph_memory_filename")

from .agent_core_schemas_v1 import Task, Thought
from .action_params_v1 import *
from .foundational_schemas_v1 import HandlerActionType

class WorkflowConfig(BaseModel):
    """Workflow processing configuration for v1."""
    max_active_tasks: int = Field(default=10, description="Maximum tasks that can be active simultaneously")
    max_active_thoughts: int = Field(default=50, description="Maximum thoughts to pull into processing queue per round") 
    round_delay_seconds: float = Field(default=1.0, description="Delay between processing rounds in seconds")
    max_rounds: int = Field(default=7, description="Maximum ponder iterations before auto-defer")
    num_rounds: Optional[int] = Field(default=None, description="Maximum number of processing rounds (None = infinite)")
    DMA_RETRY_LIMIT: int = Field(default=3, description="Maximum retry attempts for DMAs")
    DMA_TIMEOUT_SECONDS: float = Field(
        default=30.0,
        description="Timeout in seconds for each DMA evaluation",
    )
    GUARDRAIL_RETRY_LIMIT: int = Field(default=2, description="Maximum retry attempts for guardrails")

class OpenAIConfig(BaseModel):
    """OpenAI/LLM service configuration for v1."""
    model_name: str = Field(default="gpt-4o-mini", description="Default model name")
    base_url: Optional[str] = Field(default=None, description="Custom API base URL")
    timeout_seconds: float = Field(default=30.0, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    api_key: Optional[str] = Field(default=None, description="API key for OpenAI or compatible service")
    api_key_env_var: str = Field(default="OPENAI_API_KEY", description="Environment variable for API key")
    instructor_mode: str = Field(default="JSON", description="InGuardrailsConfiguctor library mode")

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var

        if not self.api_key:
            self.api_key = get_env_var(self.api_key_env_var)
        
        if not self.base_url:
            base_url = get_env_var("OPENAI_API_BASE") or get_env_var("OPENAI_BASE_URL")
            if base_url:
                self.base_url = base_url
        
        if not self.model_name or self.model_name == "gpt-4o-mini":
            env_model = get_env_var("OPENAI_MODEL_NAME")
            if env_model:
                self.model_name = env_model

class LLMServicesConfig(BaseModel):
    """LLM services configuration container."""
    openai: OpenAIConfig = OpenAIConfig()

class AgentProfile(BaseModel):
    """Minimal v1 agent profile configuration."""
    name: str
    dsdma_identifier: Optional[str] = None
    dsdma_kwargs: Optional[Dict[str, Any]] = None
    permitted_actions: List[HandlerActionType] = Field(default_factory=list)
    csdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    action_selection_pdma_overrides: Dict[str, Any] = Field(default_factory=dict)
    guardrails_config: Optional[GuardrailsConfig] = None

class CIRISNodeConfig(BaseModel):
    """Configuration for communicating with CIRISNode service."""

    base_url: str = Field(default="https://localhost:8001")
    timeout_seconds: float = Field(default=30.0)
    max_retries: int = Field(default=2)
    agent_secret_jwt: Optional[str] = None

    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var

        env_url = get_env_var("CIRISNODE_BASE_URL")
        if env_url:
            self.base_url = env_url
        self.agent_secret_jwt = get_env_var("CIRISNODE_AGENT_SECRET_JWT")

class NetworkConfig(BaseModel):
    """Network participation configuration"""
    enabled_networks: List[str] = Field(default_factory=lambda: ["local", "cirisnode"])
    agent_identity_path: Optional[str] = None  # Path to identity file
    peer_discovery_interval: int = 300  # seconds
    reputation_threshold: int = 30  # 0-100 scale
    
class CollectorConfig(BaseModel):
    """Configuration for telemetry collectors"""
    interval_ms: int = Field(description="Collection interval in milliseconds")
    max_buffer_size: int = Field(description="Maximum buffer size for this collector")

class TelemetryCollectorsConfig(BaseModel):
    """Configuration for all telemetry collector tiers"""
    instant: CollectorConfig = CollectorConfig(interval_ms=50, max_buffer_size=1000)
    fast: CollectorConfig = CollectorConfig(interval_ms=250, max_buffer_size=5000)
    normal: CollectorConfig = CollectorConfig(interval_ms=1000, max_buffer_size=10000)
    slow: CollectorConfig = CollectorConfig(interval_ms=5000, max_buffer_size=5000)
    aggregate: CollectorConfig = CollectorConfig(interval_ms=30000, max_buffer_size=1000)

class TelemetrySecurityConfig(BaseModel):
    """Security configuration for telemetry system"""
    require_tls: bool = Field(default=True, description="Require TLS for external telemetry")
    require_auth: bool = Field(default=True, description="Require authentication for telemetry endpoints")
    pii_detection: bool = Field(default=True, description="Enable PII detection and filtering")
    max_history_hours: int = Field(default=1, description="Maximum telemetry history retention")
    encryption_key_env: str = Field(default="TELEMETRY_ENCRYPTION_KEY", description="Environment variable for encryption key")

class TelemetryExportConfig(BaseModel):
    """Export configuration for telemetry data"""
    otlp: bool = Field(default=False, description="Enable OpenTelemetry protocol export")
    websocket: bool = Field(default=False, description="Enable WebSocket telemetry streaming")
    api: bool = Field(default=False, description="Enable API endpoint for telemetry")

class TelemetryConfig(BaseModel):
    """Comprehensive telemetry configuration"""
    enabled: bool = Field(default=False, description="Enable telemetry system")
    internal_only: bool = Field(default=True, description="Restrict to internal telemetry only")
    retention_hours: int = Field(default=1, description="Data retention period in hours")
    snapshot_interval_ms: int = Field(default=1000, description="SystemSnapshot update interval")
    buffer_size: int = Field(default=1000, description="Main telemetry buffer size")
    security: TelemetrySecurityConfig = TelemetrySecurityConfig()
    collectors: TelemetryCollectorsConfig = TelemetryCollectorsConfig()
    export: TelemetryExportConfig = TelemetryExportConfig()

class SecretsStorageConfig(BaseModel):
    """Configuration for secrets storage"""
    database_path: str = Field(default="secrets.db", description="Path to secrets database")
    encryption_key_env: str = Field(default="SECRETS_MASTER_KEY", description="Environment variable for master encryption key")
    key_rotation_days: int = Field(default=90, description="Key rotation period in days")

class SecretPattern(BaseModel):
    """Configuration for a secret detection pattern"""
    name: str = Field(description="Pattern name")
    regex: str = Field(description="Regular expression pattern") 
    description: str = Field(description="Human-readable description")
    sensitivity: SensitivityLevel
    context_hint: str = Field(description="Safe description for context")
    enabled: bool = True

class SecretsDetectionConfig(BaseModel):
    """Configuration for secrets detection"""
    builtin_patterns: bool = Field(default=True, description="Enable built-in detection patterns")
    custom_patterns_enabled: bool = Field(default=True, description="Allow custom detection patterns")
    sensitivity_threshold: str = Field(default="MEDIUM", description="Detection sensitivity: LOW, MEDIUM, HIGH, CRITICAL")
    
    # Default built-in patterns that can be configured by the agent
    default_patterns: List[SecretPattern] = Field(default_factory=lambda: [
        SecretPattern(
            name="api_keys",
            regex=r"(?i)api[_-]?key[s]?[\s:=]+['\"]?([a-z0-9_-]{20,})['\"]?",
            description="API Key",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="API authentication key"
        ),
        SecretPattern(
            name="bearer_tokens",
            regex=r"(?i)bearer[\s]+([a-z0-9\-_.]{20,})",
            description="Bearer Token",
            sensitivity=SensitivityLevel.HIGH, 
            context_hint="Bearer authentication token"
        ),
        SecretPattern(
            name="passwords",
            regex=r"(?i)password[s]?[\s:=]+['\"]?([^\s'\"]{8,})['\"]?",
            description="Password",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="Password credential"
        ),
        SecretPattern(
            name="urls_with_auth",
            regex=r"https?://[^:]+:[^@]+@[^\s]+",
            description="URL with Authentication",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="Authenticated URL"
        ),
        SecretPattern(
            name="private_keys",
            regex=r"-----BEGIN [A-Z ]+PRIVATE KEY-----",
            description="Private Key",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="Cryptographic private key"
        ),
        SecretPattern(
            name="credit_cards",
            regex=r"\b(?:4[0-9]{12}(?:[0-9]{3})?|5[1-5][0-9]{14}|3[47][0-9]{13})\b",
            description="Credit Card Number",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="Payment card number"
        ),
        SecretPattern(
            name="social_security",
            regex=r"\b\d{3}-\d{2}-\d{4}\b",
            description="Social Security Number",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="Social Security Number"
        ),
        SecretPattern(
            name="aws_access_key",
            regex=r"AKIA[0-9A-Z]{16}",
            description="AWS Access Key",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="AWS access key"
        ),
        SecretPattern(
            name="aws_secret_key",
            regex=r"(?i)aws[_-]?secret[_-]?access[_-]?key[\s:=]+['\"]?([a-z0-9/+=]{40})['\"]?",
            description="AWS Secret Key",
            sensitivity=SensitivityLevel.CRITICAL,
            context_hint="AWS secret access key"
        ),
        SecretPattern(
            name="github_token",
            regex=r"gh[ps]_[a-zA-Z0-9]{36}",
            description="GitHub Token",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="GitHub access token"
        ),
        SecretPattern(
            name="slack_token",
            regex=r"xox[baprs]-([0-9a-zA-Z]{10,48})",
            description="Slack Token",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="Slack API token"
        ),
        SecretPattern(
            name="discord_token",
            regex=r"[MN][A-Za-z\d]{23}\.[\w-]{6}\.[\w-]{27}",
            description="Discord Bot Token",
            sensitivity=SensitivityLevel.HIGH,
            context_hint="Discord bot token"
        ),
    ])
    
    # Patterns disabled by agent configuration
    disabled_patterns: List[str] = Field(default_factory=list, description="List of pattern names to disable")
    
    # Custom patterns added by agent
    custom_patterns: List[SecretPattern] = Field(default_factory=list, description="Agent-defined custom patterns")

class SecretsAccessControlConfig(BaseModel):
    """Configuration for secrets access control"""
    max_accesses_per_minute: int = Field(default=10, description="Maximum secret accesses per minute")
    max_accesses_per_hour: int = Field(default=100, description="Maximum secret accesses per hour")
    max_decryptions_per_hour: int = Field(default=20, description="Maximum decryptions per hour")
    require_confirmation_for: List[str] = Field(default_factory=lambda: ["CRITICAL"], description="Sensitivity levels requiring confirmation")


class SecretsFilter(BaseModel):
    """Agent-configurable secrets detection rules"""
    filter_id: str = Field(description="Unique identifier for this filter set")
    version: int = Field(description="Version number for updates")
    
    # Built-in patterns (always active)
    builtin_patterns_enabled: bool = True
    
    # Agent-defined custom patterns
    custom_patterns: List[SecretPattern] = Field(default_factory=list)
    
    # Pattern overrides
    disabled_patterns: List[str] = Field(default_factory=list)
    sensitivity_overrides: Dict[str, str] = Field(default_factory=dict)
    
    # Behavioral settings
    require_confirmation_for: List[str] = Field(default=["CRITICAL"])
    auto_decrypt_for_actions: List[str] = Field(default=["speak", "tool"])

class SecretsAuditConfig(BaseModel):
    """Configuration for secrets audit logging"""
    log_all_access: bool = Field(default=True, description="Log all secret access operations")
    log_path: str = Field(default="secrets_audit.log", description="Path to secrets audit log")
    retention_days: int = Field(default=365, description="Audit log retention period")

class SecretsAutoDecapsulationConfig(BaseModel):
    """Configuration for automatic secrets decapsulation"""
    enabled: bool = Field(default=True, description="Enable automatic decapsulation in handlers")
    allowed_actions: List[str] = Field(default_factory=lambda: ["speak", "tool", "memorize"], description="Actions that allow auto-decapsulation")
    require_purpose: bool = Field(default=True, description="Require purpose documentation for decapsulation")

class SecretsConfig(BaseModel):
    """Comprehensive secrets management configuration"""
    enabled: bool = Field(default=True, description="Enable secrets management system")
    storage: SecretsStorageConfig = SecretsStorageConfig()
    detection: SecretsDetectionConfig = SecretsDetectionConfig()
    access_control: SecretsAccessControlConfig = SecretsAccessControlConfig()
    audit: SecretsAuditConfig = SecretsAuditConfig()
    auto_decapsulation: SecretsAutoDecapsulationConfig = SecretsAutoDecapsulationConfig()
    
    def load_env_vars(self) -> None:
        """Load configuration from environment variables if present."""
        from ciris_engine.config.env_utils import get_env_var
        
        # Load storage configuration
        db_path = get_env_var("SECRETS_DB_PATH")
        if db_path:
            self.storage.database_path = db_path
        
        # Load sensitivity threshold
        sensitivity = get_env_var("SECRETS_SENSITIVITY_THRESHOLD")
        if sensitivity and sensitivity.upper() in ["LOW", "MEDIUM", "HIGH", "CRITICAL"]:
            self.detection.sensitivity_threshold = sensitivity.upper()
        
        # Load access control limits
        max_per_minute = get_env_var("SECRETS_MAX_ACCESS_PER_MINUTE")
        if max_per_minute:
            try:
                self.access_control.max_accesses_per_minute = int(max_per_minute)
            except ValueError:
                pass

class AuditHashChainConfig(BaseModel):
    """Configuration for audit hash chains"""
    enabled: bool = Field(default=True, description="Enable hash chain integrity")
    algorithm: str = Field(default="sha256", description="Hash algorithm")

class AuditSignatureConfig(BaseModel):
    """Configuration for audit signatures"""
    enabled: bool = Field(default=True, description="Enable digital signatures")
    algorithm: str = Field(default="rsa-pss", description="Signature algorithm")
    key_size: int = Field(default=2048, description="Key size in bits")
    key_rotation_days: int = Field(default=90, description="Key rotation period")

class AuditAnchoringConfig(BaseModel):
    """Configuration for audit anchoring"""
    enabled: bool = Field(default=True, description="Enable audit anchoring")
    interval_hours: int = Field(default=1, description="Anchoring interval in hours")
    method: str = Field(default="local", description="Anchoring method: local, blockchain, rfc3161")

class AuditConfig(BaseModel):
    """Comprehensive audit service configuration"""
    enable_signed_audit: bool = Field(default=False, description="Enable cryptographically signed audit trail")
    enable_jsonl_audit: bool = Field(default=True, description="Enable traditional JSONL audit logging")
    audit_log_path: str = Field(default="audit_logs.jsonl", description="Path to JSONL audit log file")
    audit_db_path: str = Field(default="ciris_audit.db", description="Path to signed audit database")
    audit_key_path: str = Field(default="audit_keys", description="Directory for audit signing keys")
    rotation_size_mb: int = Field(default=100, description="JSONL file rotation size in MB")
    retention_days: int = Field(default=90, description="Audit log retention period in days")
    hash_chain: AuditHashChainConfig = AuditHashChainConfig()
    signatures: AuditSignatureConfig = AuditSignatureConfig()
    anchoring: AuditAnchoringConfig = AuditAnchoringConfig()

class ResourceBudgetConfig(BaseModel):
    """Configuration for individual resource budgets"""
    limit: float = Field(description="Resource limit threshold")
    warning: float = Field(description="Warning threshold")
    critical: float = Field(description="Critical threshold")
    action: str = Field(description="Action to take when threshold exceeded: defer, throttle, reject, shutdown")

class ResourceThrottleConfig(BaseModel):
    """Configuration for resource throttling actions"""
    min_delay_seconds: float = Field(default=0.1, description="Minimum throttle delay")
    max_delay_seconds: float = Field(default=10.0, description="Maximum throttle delay")
    increment: float = Field(default=1.0, description="Delay increment factor")

class ResourceDeferConfig(BaseModel):
    """Configuration for resource deferral actions"""
    priority_threshold: int = Field(default=50, description="Priority threshold for deferral")

class ResourceShutdownConfig(BaseModel):
    """Configuration for resource shutdown actions"""
    grace_period_seconds: int = Field(default=30, description="Graceful shutdown period")
    save_state: bool = Field(default=True, description="Save state before shutdown")

class ResourceActionsConfig(BaseModel):
    """Configuration for resource management actions"""
    throttle: ResourceThrottleConfig = ResourceThrottleConfig()
    defer: ResourceDeferConfig = ResourceDeferConfig()
    shutdown: ResourceShutdownConfig = ResourceShutdownConfig()

class ResourceMonitoringConfig(BaseModel):
    """Configuration for resource monitoring"""
    interval_seconds: int = Field(default=1, description="Monitoring interval")
    history_hours: int = Field(default=24, description="Resource history retention")

class ResourceConfig(BaseModel):
    """Comprehensive resource management configuration"""
    enabled: bool = Field(default=True, description="Enable resource management")
    monitoring: ResourceMonitoringConfig = ResourceMonitoringConfig()
    budgets: Dict[str, ResourceBudgetConfig] = Field(default_factory=lambda: {
        "memory": ResourceBudgetConfig(limit=256, warning=200, critical=240, action="defer"),
        "cpu": ResourceBudgetConfig(limit=80, warning=60, critical=75, action="throttle"),
        "tokens_hour": ResourceBudgetConfig(limit=10000, warning=8000, critical=9500, action="defer"),
        "tokens_day": ResourceBudgetConfig(limit=100000, warning=80000, critical=95000, action="reject"),
        "thoughts": ResourceBudgetConfig(limit=50, warning=40, critical=48, action="defer")
    })
    actions: ResourceActionsConfig = ResourceActionsConfig()

class AdaptiveFilteringConfig(BaseModel):
    """Configuration for adaptive message filtering"""
    new_user_threshold: int = Field(default=5, description="Threshold for new user classification")
    sample_rate_default: float = Field(default=0.1, description="Default sampling rate")
    effectiveness_threshold: float = Field(default=0.3, description="Effectiveness threshold for adjustments")
    false_positive_threshold: float = Field(default=0.2, description="False positive threshold")

class AdaptiveLearningConfig(BaseModel):
    """Configuration for adaptive learning system"""
    enabled: bool = Field(default=True, description="Enable adaptive learning")
    adjustment_interval: int = Field(default=3600, description="Adjustment interval in seconds")
    min_samples_for_adjustment: int = Field(default=10, description="Minimum samples required for adjustment")

class CircuitBreakerConfig(BaseModel):
    """Configuration for circuit breaker patterns"""
    failure_threshold: int = Field(default=3, description="Failure threshold to open circuit")
    reset_timeout: int = Field(default=300, description="Reset timeout in seconds")
    half_open_test_interval: int = Field(default=60, description="Half-open test interval")

class IdentityUpdatesConfig(BaseModel):
    """Configuration for identity update management"""
    require_wa_approval: bool = Field(default=True, description="Require WA approval for identity changes")
    wa_timeout_hours: int = Field(default=72, description="WA approval timeout")
    allow_emergency_override: bool = Field(default=False, description="Allow emergency override of WA requirement")

class AdaptiveConfig(BaseModel):
    """Comprehensive adaptive configuration and self-configuration"""
    enabled: bool = Field(default=True, description="Enable adaptive configuration system")
    filtering: AdaptiveFilteringConfig = AdaptiveFilteringConfig()
    learning: AdaptiveLearningConfig = AdaptiveLearningConfig()
    circuit_breaker: CircuitBreakerConfig = CircuitBreakerConfig()
    identity_updates: IdentityUpdatesConfig = IdentityUpdatesConfig()

class PersistenceIntegrityConfig(BaseModel):
    """Configuration for persistence integrity verification"""
    enabled: bool = Field(default=True, description="Enable integrity verification")
    mode: str = Field(default="full", description="Integrity mode: full, lightweight, disabled")

class PersistenceHashChainsConfig(BaseModel):
    """Configuration for persistence hash chains"""
    tasks: bool = Field(default=True, description="Enable hash chains for tasks")
    thoughts: bool = Field(default=True, description="Enable hash chains for thoughts")
    graph_nodes: bool = Field(default=False, description="Enable hash chains for graph nodes")

class PersistenceSignaturesConfig(BaseModel):
    """Configuration for persistence signatures"""
    enabled: bool = Field(default=True, description="Enable selective signing")
    selective: bool = Field(default=True, description="Use selective signing")
    deferred_thoughts: bool = Field(default=True, description="Sign deferred thoughts")
    high_priority_tasks: bool = Field(default=True, description="Sign high priority tasks")
    wa_updates: bool = Field(default=True, description="Sign WA updates")

class PersistenceVerificationConfig(BaseModel):
    """Configuration for persistence verification"""
    on_startup: bool = Field(default=False, description="Verify on startup")
    on_deferral: bool = Field(default=True, description="Verify on deferral")
    periodic_hours: int = Field(default=24, description="Periodic verification interval")

class PersistenceConfig(BaseModel):
    """Configuration for persistence integrity system"""
    integrity: PersistenceIntegrityConfig = PersistenceIntegrityConfig()
    hash_chains: PersistenceHashChainsConfig = PersistenceHashChainsConfig()
    signatures: PersistenceSignaturesConfig = PersistenceSignaturesConfig()
    verification: PersistenceVerificationConfig = PersistenceVerificationConfig()

class WisdomConfig(BaseModel):
    """Wisdom-seeking configuration"""
    wa_timeout_hours: int = 72  # Hours before considering WA unavailable
    allow_universal_guidance: bool = True  # Allow prayer protocol
    minimum_urgency_for_universal: int = 80  # 0-100 scale
    peer_consensus_threshold: int = 3  # Minimum peers for consensus

class AppConfig(BaseModel):
    """Comprehensive v1 application configuration with all implemented features."""
    version: Optional[str] = None
    log_level: Optional[str] = None
    database: DatabaseConfig = DatabaseConfig()
    llm_services: LLMServicesConfig = LLMServicesConfig()
    guardrails: GuardrailsConfig = GuardrailsConfig()
    workflow: WorkflowConfig = WorkflowConfig()
    audit: AuditConfig = AuditConfig()
    cirisnode: CIRISNodeConfig = CIRISNodeConfig()
    network: NetworkConfig = NetworkConfig()
    telemetry: TelemetryConfig = TelemetryConfig()
    secrets: SecretsConfig = SecretsConfig()
    resources: ResourceConfig = ResourceConfig()
    adaptive: AdaptiveConfig = AdaptiveConfig()
    persistence: PersistenceConfig = PersistenceConfig()
    wisdom: WisdomConfig = WisdomConfig()
    profile_directory: str = Field(default="ciris_profiles", description="Directory containing agent profiles")
    default_profile: str = Field(default="default", description="Default agent profile name to use if not specified")
    agent_profiles: Dict[str, AgentProfile] = Field(default_factory=dict)
    discord_channel_ids: Optional[List[str]] = Field(default=None, description="List of Discord channel IDs to monitor")
    discord_channel_id: Optional[str] = Field(default=None, description="Primary Discord channel ID (deprecated - use discord_channel_ids)")
    discord_deferral_channel_id: Optional[str] = Field(default=None, description="Channel ID for Discord deferrals and guidance")
    agent_mode: str = Field(default="", description="Runtime mode: 'cli', 'discord', 'api'")
    cli_channel_id: Optional[str] = Field(default=None, description="Channel ID for CLI mode")
    api_channel_id: Optional[str] = Field(default=None, description="Channel ID for API mode")
    data_archive_dir: str = Field(default="data_archive", description="Directory for archived data")
    archive_older_than_hours: int = Field(default=24, description="Archive data older than this many hours")

DMA_RETRY_LIMIT = 3
GUARDRAIL_RETRY_LIMIT = 2
DMA_TIMEOUT_SECONDS = 30.0
