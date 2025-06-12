"""Service registry management resource for CIRIS SDK."""

from typing import Dict, Any, Optional, List
from ..transport import Transport


class ServicesResource:
    """Resource for managing service registry operations."""

    def __init__(self, transport: Transport):
        self._transport = transport

    async def list_services(self, handler: Optional[str] = None, service_type: Optional[str] = None) -> Dict[str, Any]:
        """
        List all registered services with their configuration.
        
        Args:
            handler: Optional handler filter
            service_type: Optional service type filter
            
        Returns:
            Dictionary containing service registry information
        """
        params = {}
        if handler:
            params['handler'] = handler
        if service_type:
            params['service_type'] = service_type
            
        response = await self._transport.request("GET", "/v1/runtime/services", params=params)
        return response.json() if hasattr(response, 'json') else response

    async def get_service_health(self) -> Dict[str, Any]:
        """
        Get health status of all registered services.
        
        Returns:
            Dictionary containing service health information
        """
        response = await self._transport.request("GET", "/v1/runtime/services/health")
        return response.json() if hasattr(response, 'json') else response

    async def get_selection_explanation(self) -> Dict[str, Any]:
        """
        Get explanation of how service selection works with priorities and strategies.
        
        Returns:
            Dictionary explaining service selection logic
        """
        response = await self._transport.request("GET", "/v1/runtime/services/selection-logic")
        return response.json() if hasattr(response, 'json') else response

    async def reset_circuit_breakers(self, service_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Reset circuit breakers for services.
        
        Args:
            service_type: Optional service type filter
            
        Returns:
            Operation result
        """
        params = {}
        if service_type:
            params['service_type'] = service_type
            
        response = await self._transport.request("POST", "/v1/runtime/services/circuit-breakers/reset", params=params)
        return response.json() if hasattr(response, 'json') else response

    async def update_service_priority(
        self, 
        provider_name: str, 
        priority: Optional[str] = None,
        priority_group: Optional[int] = None,
        strategy: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Update service provider priority and selection strategy.
        
        Args:
            provider_name: Name of the service provider
            priority: New priority level (CRITICAL, HIGH, NORMAL, LOW, FALLBACK)
            priority_group: New priority group number
            strategy: New selection strategy (FALLBACK, ROUND_ROBIN)
            
        Returns:
            Operation result
        """
        data = {}
        if priority:
            data['priority'] = priority
        if priority_group is not None:
            data['priority_group'] = priority_group
        if strategy:
            data['strategy'] = strategy
            
        response = await self._transport.request("PUT", f"/v1/runtime/services/{provider_name}/priority", json=data)
        return response.json() if hasattr(response, 'json') else response

    async def get_service_metrics(self, service_name: Optional[str] = None) -> Dict[str, Any]:  # noqa: ARG002
        """
        Get performance metrics for services.
        
        Args:
            service_name: Optional service name filter
            
        Returns:
            Service metrics data
        """
        # This would be a separate endpoint for service metrics
        # For now, return placeholder
        return {
            "message": "Service metrics endpoint not yet implemented",
            "suggestion": "Use general telemetry endpoints for system metrics"
        }

    # Convenience methods for common service management tasks
    async def get_llm_services(self) -> List[Dict[str, Any]]:
        """Get all LLM service providers."""
        services = await self.list_services(service_type="llm")
        
        # Handle None response gracefully
        if not services:
            return []
        llm_services = []
        
        # Extract LLM services from both handlers and global services
        for handler, service_types in services.get("handlers", {}).items():
            if "llm" in service_types:
                for service in service_types["llm"]:
                    llm_services.append({
                        "scope": f"handler:{handler}",
                        **service
                    })
        
        for service in services.get("global_services", {}).get("llm", []):
            llm_services.append({
                "scope": "global",
                **service
            })
            
        return llm_services

    async def get_communication_services(self) -> List[Dict[str, Any]]:
        """Get all communication service providers."""
        services = await self.list_services(service_type="communication")
        comm_services = []
        
        # Extract communication services from both handlers and global services
        for handler, service_types in services.get("handlers", {}).items():
            if "communication" in service_types:
                for service in service_types["communication"]:
                    comm_services.append({
                        "scope": f"handler:{handler}",
                        **service
                    })
        
        for service in services.get("global_services", {}).get("communication", []):
            comm_services.append({
                "scope": "global",
                **service
            })
            
        return comm_services

    async def get_memory_services(self) -> List[Dict[str, Any]]:
        """Get all memory service providers."""
        services = await self.list_services(service_type="memory")
        memory_services = []
        
        # Extract memory services from both handlers and global services
        for handler, service_types in services.get("handlers", {}).items():
            if "memory" in service_types:
                for service in service_types["memory"]:
                    memory_services.append({
                        "scope": f"handler:{handler}",
                        **service
                    })
        
        for service in services.get("global_services", {}).get("memory", []):
            memory_services.append({
                "scope": "global",
                **service
            })
            
        return memory_services

    async def diagnose_service_issues(self) -> Dict[str, Any]:
        """
        Diagnose common service configuration issues.
        
        Returns:
            Diagnostic information and recommendations
        """
        health = await self.get_service_health()
        services = await self.list_services()
        
        issues = []
        recommendations = []
        
        # Check for unhealthy services
        if health.get("unhealthy_services", 0) > 0:
            issues.append(f"{health['unhealthy_services']} services are unhealthy")
            recommendations.append("Check circuit breaker states and service logs")
        
        # Check for missing critical services
        required_services = ["llm", "communication", "memory", "audit"]
        for service_type in required_services:
            has_service = False
            
            # Check global services
            if services.get("global_services", {}).get(service_type):
                has_service = True
            
            # Check handler services
            for handler_services in services.get("handlers", {}).values():
                if service_type in handler_services:
                    has_service = True
                    break
            
            if not has_service:
                issues.append(f"No {service_type} services registered")
                recommendations.append(f"Ensure adapters providing {service_type} services are loaded")
        
        return {
            "overall_health": health.get("overall_health", "unknown"),
            "total_services": health.get("total_services", 0),
            "healthy_services": health.get("healthy_services", 0),
            "issues_found": len(issues),
            "issues": issues,
            "recommendations": recommendations,
            "service_summary": {
                "global_services": len(services.get("global_services", {})),
                "handler_specific_services": sum(
                    len(service_types) for service_types in services.get("handlers", {}).values()
                )
            }
        }