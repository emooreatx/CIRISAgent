# Vulture whitelist for CIRIS Engine
# This file contains false positives that vulture reports as unused
# but are actually used dynamically by frameworks or through protocols

# ===== FastAPI Route Handlers =====
# All route functions are registered via decorators
_.interact  # @router.post("/interact")
_.get_history  # @router.get("/history")
_.get_identity  # @router.get("/identity")
_.get_channels  # @router.get("/channels")
_.websocket_stream  # @router.websocket("/stream")
_.store_message_response  # background task

# Auth routes
_.login  # @router.post("/login")
_.logout  # @router.post("/logout")
_.get_current_user  # @router.get("/me")
_.refresh_token  # @router.post("/refresh")
_.list_oauth_providers  # @router.get("/oauth/providers")
_.configure_oauth_provider  # @router.post("/oauth/providers")
_.oauth_login  # @router.get("/oauth/{provider}/login")
_.oauth_callback  # @router.get("/oauth/{provider}/callback")

# Audit routes
_.get_audit_entry  # @router.get("/entries/{entry_id}")
_.search_audit_trails  # @router.post("/search")
_.verify_audit_entry  # @router.post("/entries/{entry_id}/verify")

# Memory routes
_.store_memory  # @router.post("/store")
_.query_memory  # @router.post("/query")
_.forget_memory  # @router.delete("/forget/{node_id}")
_.get_timeline  # @router.get("/timeline")
_.recall_memory  # @router.post("/recall")
_.get_memory_stats  # @router.get("/stats")
_.visualize_memory_graph  # @router.get("/visualize")

# System routes
_.get_system_health  # @router.get("/health")
_.get_system_time  # @router.get("/time")
_.get_resource_usage  # @router.get("/resources")
_.control_runtime  # @router.post("/runtime/control")
_.get_services_status  # @router.get("/services")
_.shutdown_system  # @router.post("/shutdown")

# System extension routes
_.get_processing_queue_status  # @router.get("/processing-queue")
_.single_step_processor  # @router.post("/single-step")
_.get_service_health_details  # @router.get("/services/health")
_.reset_service_circuit_breakers  # @router.post("/services/{service_name}/reset-circuit-breaker")
_.get_processor_states  # @router.get("/processors/states")

# Emergency routes
_.emergency_shutdown  # @router.post("/shutdown")
_.test_emergency_endpoint  # @router.get("/test")

# ===== FastAPI Dependencies =====
_.get_auth_context  # Depends()
_.get_auth_service  # Depends()
_.require_observer  # Depends()
_.require_admin  # Depends()
_.require_authority  # Depends()
_.require_system_admin  # Depends()
_.get_current_user  # Depends()
_.require_role  # Depends()
_.check_permissions  # Depends()
_.get_runtime_service  # Depends()

# ===== Middleware and Lifespan =====
_.rate_limit_wrapper  # @app.middleware("http")
_.lifespan  # FastAPI(lifespan=lifespan)

# ===== Protocol Required Methods =====
# These are required by protocol definitions
_.can_process  # ProcessorProtocol
_.get_algorithm_type  # BaseDMAProtocol
_.handle_request  # APIAdapterProtocol
_.handle_input  # CLIAdapterProtocol
_.handle_reaction  # DiscordAdapterProtocol
_.get_variance_history  # IdentityVarianceMonitorProtocol
_.apply_learning  # ConfigurationFeedbackLoopProtocol
_.authenticate  # AuthenticationServiceProtocol
_.create_token  # AuthenticationServiceProtocol
_.rotate_keys  # AuthenticationServiceProtocol
_.verify_entry  # AuditVerifierProtocol
_.get_health  # AdaptiveFilterServiceProtocol
_.recall_secret  # SecretsServiceProtocol
_.update_filter_config  # SecretsServiceProtocol
_.clear_circuit_breakers  # LLMBusProtocol
_.request_graceful_shutdown  # BaseHandlerProtocol

# ===== Discord Event Handlers =====
_.on_message  # Discord event
_.on_ready  # Discord event
_.on_disconnect  # Discord event
_.on_error  # Discord event
_.on_raw_reaction_add  # Discord event
_.on_connected  # Connection event
_.on_disconnected  # Connection event
_.on_reconnecting  # Connection event
_.on_failed  # Connection event

# ===== Dynamic Methods =====
_.__getattr__  # Dynamic attribute resolution
_.from_graph_node  # Class method pattern
_.from_dict  # Class method pattern
_.to_graph_node  # Instance method pattern

# ===== Pydantic Validators and Serializers =====
_.serialize_timestamp  # @field_serializer
_.serialize_times  # @field_serializer
_.serialize_ts  # @field_serializer
_.serialize_updated_at  # @field_serializer
_.serialize_dates  # @field_serializer
_.validate_query_params  # @model_validator

# ===== Exception Handlers =====
_.setup_global_exception_handler  # Exception setup
_.handle_exception  # sys.excepthook

# ===== Helper Functions =====
# These are used within route handlers
_.verify_signature  # Emergency endpoint helper
_.verify_timestamp  # Emergency endpoint helper
_.is_authorized_key  # Emergency endpoint helper
_._convert_audit_entry  # Audit route helper
_._get_audit_service  # Audit route helper
_.get_node_time  # Memory visualization helper
_.get_node_sort_time  # Memory visualization helper
_._get_edge_color  # Memory visualization helper
_._get_edge_style  # Memory visualization helper
_._get_node_color  # Memory visualization helper
_._get_node_size  # Memory visualization helper
_._hierarchy_pos  # Memory visualization helper
_._hierarchy_pos_recursive  # Memory visualization helper
_._calculate_timeline_layout  # Memory visualization helper
_._generate_svg  # Memory visualization helper

# ===== Class Methods =====
_.load  # Settings.load()
_._mock_instructor_patch  # MockLLMService method

# ===== Background Tasks =====
_.notify_interact_response  # BackgroundTasks
_.store_message_response  # BackgroundTasks

# ===== Test Infrastructure =====
# Mock service methods
_.get_emergency_shutdown_status  # Mock emergency status

# ===== Protocol Parameters =====
# Parameters in protocol method signatures
_.subscription_id  # BusManagerProtocol.unsubscribe parameter
_.checkpoint_id  # PersistenceManagerProtocol parameters