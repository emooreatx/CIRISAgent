from pydantic import BaseModel, Field

class GuardrailsConfig(BaseModel):
    """Streamlined guardrails configuration for v1"""
    # Epistemic Faculty Thresholds
    entropy_threshold: float = Field(
        default=0.40, 
        ge=0.0, 
        le=1.0,
        description="Maximum allowed entropy (chaos/randomness) in outputs"
    )
    coherence_threshold: float = Field(
        default=0.60, 
        ge=0.0, 
        le=1.0,
        description="Minimum required coherence with CIRIS values"
    )
    optimization_veto_ratio: float = Field(
        default=10.0,
        ge=0.0,
        description="Maximum allowed entropy-reduction to value-loss ratio"
    )
    epistemic_humility_threshold: float = Field(
        default=0.70,
        ge=0.0,
        le=1.0,
        description="Threshold for epistemic certainty (lower = more humble)"
    )
    # Core Safety Constraints
    input_sanitization_method: str = Field(
        default="bleach",
        description="Method for input sanitization"
    )
    pii_detection_enabled: bool = Field(
        default=True,
        description="Enable PII detection and filtering"
    )
    pii_confidence_threshold: float = Field(
        default=0.7,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for PII detection"
    )
    # Rate Limits
    max_observe_per_cycle: int = Field(
        default=10,
        description="Maximum observations per processing cycle"
    )
    max_actions_per_thought: int = Field(
        default=7,
        description="Maximum actions before thought escalation"
    )
    max_ponder_rounds: int = Field(
        default=5,
        description="Maximum ponder iterations before auto-defer"
    )
    # Memory Constraints
    max_metadata_bytes: int = Field(
        default=1024,
        description="Maximum size for metadata storage"
    )
    channel_updates_require_feedback: bool = Field(
        default=True,
        description="Channel metadata updates require WA feedback"
    )
    # External Service Limits
    graphql_timeout_seconds: float = Field(
        default=3.0,
        description="Timeout for GraphQL queries"
    )
    enable_remote_graphql: bool = Field(
        default=False,
        description="Enable remote GraphQL lookups"
    )
    # Lifecycle Management
    shutdown_timeout_seconds: int = Field(
        default=10,
        description="Maximum time to wait for graceful shutdown"
    )
    # Action Constraints
    max_speak_length: int = Field(
        default=2000,
        description="Maximum characters in SPEAK action"
    )
    min_defer_reason_length: int = Field(
        default=20,
        description="Minimum characters in DEFER reason"
    )
    # Faculty Enable Flags
    entropy_check_enabled: bool = Field(default=True)
    coherence_check_enabled: bool = Field(default=True)
    optimization_veto_enabled: bool = Field(default=True)
    epistemic_humility_enabled: bool = Field(default=True)
