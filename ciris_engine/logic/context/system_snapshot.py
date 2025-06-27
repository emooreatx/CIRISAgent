import logging
from typing import Any, Dict, List, Optional, Tuple

from pydantic import BaseModel
from ciris_engine.logic.services.memory_service import LocalGraphMemoryService
from ciris_engine.logic.utils import GraphQLContextProvider
from ciris_engine.logic.secrets.service import SecretsService
from ciris_engine.schemas.runtime.models import Task
from ciris_engine.schemas.runtime.system_context import SystemSnapshot, TelemetrySummary
from ciris_engine.schemas.services.graph_core import GraphScope, GraphNode, NodeType
from ciris_engine.schemas.services.operations import MemoryQuery
from ciris_engine.schemas.runtime.enums import TaskStatus
from ciris_engine.logic import persistence
from .secrets_snapshot import build_secrets_snapshot

logger = logging.getLogger(__name__)

async def build_system_snapshot(
    task: Optional[Task],
    thought: Any,
    resource_monitor: Any,  # REQUIRED - mission critical system
    memory_service: Optional[LocalGraphMemoryService] = None,
    graphql_provider: Optional[GraphQLContextProvider] = None,
    telemetry_service: Optional[Any] = None,
    secrets_service: Optional[SecretsService] = None,
    runtime: Optional[Any] = None,
    service_registry: Optional[Any] = None,
) -> SystemSnapshot:
    """Build system snapshot for the thought."""
    from ciris_engine.schemas.runtime.system_context import ThoughtSummary, TaskSummary

    thought_summary = None
    if thought:
        status_val = getattr(thought, 'status', None)
        if status_val is not None and hasattr(status_val, 'value'):
            status_val = status_val.value
        elif status_val is not None:
            status_val = str(status_val)
        thought_type_val = getattr(thought, 'thought_type', None)
        thought_id_val = getattr(thought, 'thought_id', None)
        if thought_id_val is None:
            thought_id_val = "unknown"  # Provide a default value for required field
        thought_summary = ThoughtSummary(
            thought_id=thought_id_val,
            content=getattr(thought, 'content', None),
            status=status_val,
            source_task_id=getattr(thought, 'source_task_id', None),
            thought_type=thought_type_val,
            thought_depth=getattr(thought, 'thought_depth', None),
        )

    # Mission-critical channel_id and channel_context resolution with type safety
    channel_id = None
    channel_context = None

    def safe_extract_channel_info(context: Any, source_name: str) -> Tuple[Optional[str], Optional[Any]]:
        """Extract both channel_id and channel_context from context."""
        if not context:
            return None, None
        try:
            extracted_id = None
            extracted_context = None
            
            # First check if context has system_snapshot.channel_context
            if hasattr(context, 'system_snapshot') and hasattr(context.system_snapshot, 'channel_context'):
                extracted_context = context.system_snapshot.channel_context
                if extracted_context and hasattr(extracted_context, 'channel_id'):
                    extracted_id = str(extracted_context.channel_id)
                    logger.debug(f"Found channel_context in {source_name}.system_snapshot.channel_context")
                    return extracted_id, extracted_context
            
            # Then check if context has system_snapshot.channel_id
            if hasattr(context, 'system_snapshot') and hasattr(context.system_snapshot, 'channel_id'):
                cid = context.system_snapshot.channel_id
                if cid is not None:
                    logger.debug(f"Found channel_id '{cid}' in {source_name}.system_snapshot.channel_id")
                    return str(cid), None
            
            # Then check direct channel_id attribute
            if isinstance(context, dict):
                cid = context.get('channel_id')
                return str(cid) if cid is not None else None, None
            elif hasattr(context, 'channel_id'):
                cid = getattr(context, 'channel_id', None)
                return str(cid) if cid is not None else None, None
        except Exception as e:  # pragma: no cover - defensive
            logger.error(f"Error extracting channel info from {source_name}: {e}")
        return None, None

    if task and task.context:
        channel_id, channel_context = safe_extract_channel_info(task.context, "task.context")
    if not channel_id and thought and thought.context:
        channel_id, channel_context = safe_extract_channel_info(thought.context, "thought.context")

    if channel_id and memory_service:
        try:
            # First try direct lookup for performance
            query = MemoryQuery(
                node_id=f"channel/{channel_id}",
                scope=GraphScope.LOCAL,
                type=NodeType.CHANNEL,
                include_edges=False,
                depth=1
            )
            channel_nodes = await memory_service.recall(query)
            
            # If not found, try search
            if not channel_nodes:
                from ciris_engine.schemas.services.graph.memory import MemorySearchFilter
                search_filter = MemorySearchFilter(
                    node_types=[NodeType.CHANNEL],
                    scopes=[GraphScope.LOCAL],
                    limit=10
                )
                # Search by channel ID in attributes
                search_results = await memory_service.search(
                    query=channel_id,
                    filters=search_filter
                )
                # Update channel_context if we found channel info
                for node in search_results:
                    if node.attributes:
                        attrs = node.attributes if isinstance(node.attributes, dict) else node.attributes.model_dump()
                        if attrs.get('channel_id') == channel_id or node.id == f"channel/{channel_id}":
                            # Found the channel, could extract more context here if needed
                            break
        except Exception as e:
            logger.debug(f"Failed to retrieve channel context for {channel_id}: {e}")
    
    # Retrieve agent identity from graph - SINGLE CALL at snapshot generation
    identity_data: dict = {}
    identity_purpose: Optional[str] = None
    identity_capabilities: List[str] = []
    identity_restrictions: List[str] = []
    
    if memory_service:
        try:
            # Query for the agent's identity node from the graph
            identity_query = MemoryQuery(
                node_id="agent/identity",
                scope=GraphScope.IDENTITY,
                type=NodeType.AGENT,
                include_edges=False,
                depth=1
            )
            identity_nodes = await memory_service.recall(identity_query)
            identity_result = identity_nodes[0] if identity_nodes else None
            
            if identity_result and identity_result.attributes:
                # The identity is stored as a TypedGraphNode (IdentityNode)
                # Extract the identity fields from attributes
                attrs = identity_result.attributes
                if isinstance(attrs, dict):
                    # Direct access to identity fields
                    identity_data = {
                        "agent_id": attrs.get("agent_id", ""),
                        "description": attrs.get("description", ""),
                        "role": attrs.get("role_description", ""),
                        "trust_level": attrs.get("trust_level", 0.5)
                    }
                    identity_purpose = attrs.get("role_description", "")
                    identity_capabilities = attrs.get("permitted_actions", [])
                    identity_restrictions = attrs.get("restricted_capabilities", [])
                else:
                    # Handle GraphNodeAttributes or other types
                    attrs_dict = attrs.model_dump() if hasattr(attrs, 'model_dump') else {}
                    identity_data = {
                        "agent_id": attrs_dict.get("agent_id", ""),
                        "description": attrs_dict.get("description", ""),
                        "role": attrs_dict.get("role_description", ""),
                        "trust_level": attrs_dict.get("trust_level", 0.5)
                    }
                    identity_purpose = attrs_dict.get("role_description", "")
                    identity_capabilities = attrs_dict.get("permitted_actions", [])
                    identity_restrictions = attrs_dict.get("restricted_capabilities", [])
        except Exception as e:
            logger.warning(f"Failed to retrieve agent identity from graph: {e}")

    recent_tasks_list: List[Any] = []
    db_recent_tasks = persistence.get_recent_completed_tasks(10)
    for t_obj in db_recent_tasks:
        # db_recent_tasks returns List[Task], convert to TaskSummary
        if isinstance(t_obj, BaseModel):
            recent_tasks_list.append(TaskSummary(
                task_id=t_obj.task_id,
                channel_id=getattr(t_obj, 'channel_id', 'system'),
                created_at=t_obj.created_at,
                status=t_obj.status.value if hasattr(t_obj.status, 'value') else str(t_obj.status),
                priority=getattr(t_obj, 'priority', 0),
                retry_count=getattr(t_obj, 'retry_count', 0),
                parent_task_id=getattr(t_obj, 'parent_task_id', None)
            ))

    top_tasks_list: List[Any] = []
    db_top_tasks = persistence.get_top_tasks(10)
    for t_obj in db_top_tasks:
        # db_top_tasks returns List[Task], convert to TaskSummary
        if isinstance(t_obj, BaseModel):
            top_tasks_list.append(TaskSummary(
                task_id=t_obj.task_id,
                channel_id=getattr(t_obj, 'channel_id', 'system'),
                created_at=t_obj.created_at,
                status=t_obj.status.value if hasattr(t_obj.status, 'value') else str(t_obj.status),
                priority=getattr(t_obj, 'priority', 0),
                retry_count=getattr(t_obj, 'retry_count', 0),
                parent_task_id=getattr(t_obj, 'parent_task_id', None)
            ))

    current_task_summary = None
    if task:
        # Convert Task to TaskSummary
        if isinstance(task, BaseModel):
            current_task_summary = TaskSummary(
                task_id=task.task_id,
                channel_id=getattr(task, 'channel_id', 'system'),
                created_at=task.created_at,
                status=task.status.value if hasattr(task.status, 'value') else str(task.status),
                priority=getattr(task, 'priority', 0),
                retry_count=getattr(task, 'retry_count', 0),
                parent_task_id=getattr(task, 'parent_task_id', None)
            )

    secrets_data: dict = {}
    if secrets_service:
        secrets_data = await build_secrets_snapshot(secrets_service)

    # Get shutdown context from runtime
    shutdown_context = None
    if runtime and hasattr(runtime, 'current_shutdown_context'):
        shutdown_context = runtime.current_shutdown_context
    
    # Get resource alerts - CRITICAL for mission-critical systems
    resource_alerts: List[str] = []
    try:
        if resource_monitor is not None:
            snapshot = resource_monitor.snapshot
            # Check for critical resource conditions
            if snapshot.critical:
                for alert in snapshot.critical:
                    resource_alerts.append(f"🚨 CRITICAL! RESOURCE LIMIT BREACHED! {alert} - REJECT OR DEFER ALL TASKS!")
            # Also check if healthy flag is False
            if not snapshot.healthy:
                resource_alerts.append("🚨 CRITICAL! SYSTEM UNHEALTHY! RESOURCE LIMITS EXCEEDED - IMMEDIATE ACTION REQUIRED!")
        else:
            logger.warning("Resource monitor not available - cannot check resource constraints")
    except Exception as e:
        logger.error(f"Failed to get resource alerts: {e}")
        resource_alerts.append(f"🚨 CRITICAL! FAILED TO CHECK RESOURCES: {str(e)}")

    # Get service health status
    service_health: Dict[str, dict] = {}
    circuit_breaker_status: Dict[str, dict] = {}
    
    if service_registry:
        try:
            # Get health status from all registered services
            registry_info = service_registry.get_provider_info()
            
            # Check handler-specific services
            for handler, service_types in registry_info.get('handlers', {}).items():
                for service_type, services in service_types.items():
                    for service in services:
                        if hasattr(service, 'get_health_status'):
                            service_name = f"{handler}.{service_type}"
                            service_health[service_name] = await service.get_health_status()
                        if hasattr(service, 'get_circuit_breaker_status'):
                            service_name = f"{handler}.{service_type}"
                            circuit_breaker_status[service_name] = service.get_circuit_breaker_status()
            
            # Check global services
            for service_type, services in registry_info.get('global_services', {}).items():
                for service in services:
                    if hasattr(service, 'get_health_status'):
                        service_name = f"global.{service_type}"
                        service_health[service_name] = await service.get_health_status()
                    if hasattr(service, 'get_circuit_breaker_status'):
                        service_name = f"global.{service_type}"
                        circuit_breaker_status[service_name] = service.get_circuit_breaker_status()
                        
        except Exception as e:
            logger.warning(f"Failed to collect service health status: {e}")

    # Get telemetry summary for resource usage
    telemetry_summary = None
    if telemetry_service:
        try:
            telemetry_summary = await telemetry_service.get_telemetry_summary()
            logger.debug("Successfully retrieved telemetry summary")
        except Exception as e:
            logger.warning(f"Failed to get telemetry summary: {e}")
    
    context_data = {
        "current_task_details": current_task_summary,
        "current_thought_summary": thought_summary,
        "system_counts": {
            "total_tasks": persistence.count_tasks(),
            "total_thoughts": persistence.count_thoughts(),
            "pending_tasks": persistence.count_tasks(TaskStatus.PENDING),
            "pending_thoughts": persistence.count_thoughts(),
        },
        "top_pending_tasks_summary": top_tasks_list,
        "recently_completed_tasks_summary": recent_tasks_list,
        "channel_id": channel_id,
        "channel_context": channel_context,  # Preserve the full ChannelContext object
        # Identity graph data - loaded once per snapshot
        "agent_identity": identity_data,
        "identity_purpose": identity_purpose,
        "identity_capabilities": identity_capabilities,
        "identity_restrictions": identity_restrictions,
        "shutdown_context": shutdown_context,
        "service_health": service_health,
        "circuit_breaker_status": circuit_breaker_status,
        "resource_alerts": resource_alerts,  # CRITICAL mission-critical alerts
        "telemetry_summary": telemetry_summary,  # Resource usage data
        **secrets_data,
    }

    if graphql_provider:
        enriched_context = await graphql_provider.enrich_context(task, thought)
        # Convert EnrichedContext to dict for merging
        if enriched_context:
            enriched_dict = enriched_context.model_dump(exclude_none=True)
            context_data.update(enriched_dict)

    snapshot = SystemSnapshot(**context_data)

    # Note: GraphTelemetryService doesn't need update_system_snapshot
    # as it stores telemetry data directly in the graph

    return snapshot
