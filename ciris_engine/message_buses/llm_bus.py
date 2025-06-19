"""
LLM message bus - handles all LLM service operations with redundancy and distribution
"""

import logging
import uuid
import time
import asyncio
from typing import Optional, Dict, Any, List, Type, Tuple
from datetime import datetime
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

from pydantic import BaseModel

from ciris_engine.schemas.foundational_schemas_v1 import ServiceType, ResourceUsage
from ciris_engine.schemas.capability_schemas_v1 import LLMCapabilities
from ciris_engine.protocols.services import LLMService
from .base_bus import BaseBus, BusMessage

logger = logging.getLogger(__name__)


class DistributionStrategy(str, Enum):
    """Strategy for distributing requests among services at the same priority"""
    ROUND_ROBIN = "round_robin"
    LATENCY_BASED = "latency_based"
    RANDOM = "random"
    LEAST_LOADED = "least_loaded"


@dataclass
class ServiceMetrics:
    """Metrics for a single LLM service instance"""
    total_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    last_request_time: Optional[datetime] = None
    last_failure_time: Optional[datetime] = None
    consecutive_failures: int = 0
    
    @property
    def average_latency_ms(self) -> float:
        """Calculate average latency"""
        if self.total_requests == 0:
            return 0.0
        return self.total_latency_ms / self.total_requests
    
    @property
    def failure_rate(self) -> float:
        """Calculate failure rate"""
        if self.total_requests == 0:
            return 0.0
        return self.failed_requests / self.total_requests


@dataclass
class LLMRequest(BusMessage):
    """Request for LLM generation"""
    messages: List[Dict[str, str]]
    response_model: Type[BaseModel]
    max_tokens: int = 1024
    temperature: float = 0.0
    kwargs: Dict[str, Any] = field(default_factory=dict)
    # For async responses
    future: Optional[asyncio.Future] = None


class CircuitBreaker:
    """Circuit breaker for individual services"""
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "closed"  # closed, open, half_open
        self.half_open_calls = 0
    
    def record_success(self) -> None:
        """Record a successful call"""
        if self.state == "half_open":
            self.half_open_calls += 1
            if self.half_open_calls >= self.half_open_max_calls:
                # Enough successful calls, close the circuit
                self.state = "closed"
                self.failure_count = 0
                self.half_open_calls = 0
        else:
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record a failed call"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        
        if self.failure_count >= self.failure_threshold:
            self.state = "open"
        elif self.state == "half_open":
            # Failed in half-open, go back to open
            self.state = "open"
            self.half_open_calls = 0
    
    def can_execute(self) -> bool:
        """Check if we can execute a call"""
        if self.state == "closed":
            return True
            
        if self.state == "open":
            # Check if we should transition to half-open
            if self.last_failure_time and \
               (time.time() - self.last_failure_time) >= self.recovery_timeout:
                self.state = "half_open"
                self.half_open_calls = 0
                return True
            return False
            
        # half_open state
        return self.half_open_calls < self.half_open_max_calls


class LLMBus(BaseBus):
    """
    Message bus for all LLM operations with redundancy and distribution.
    
    Features:
    - Multiple redundant LLM providers
    - Priority-based selection
    - Distribution strategies (round-robin, latency-based)
    - Circuit breakers per service
    - Automatic failover
    - Metrics tracking
    """
    
    def __init__(
        self,
        service_registry: Any,
        distribution_strategy: DistributionStrategy = DistributionStrategy.LATENCY_BASED,
        circuit_breaker_config: Optional[Dict[str, Any]] = None,
        telemetry_bus: Optional[Any] = None
    ):
        super().__init__(
            service_type=ServiceType.LLM,
            service_registry=service_registry
        )
        
        self.distribution_strategy = distribution_strategy
        self.circuit_breaker_config = circuit_breaker_config or {}
        self.telemetry_bus = telemetry_bus
        
        # Service metrics and circuit breakers
        self.service_metrics: Dict[str, ServiceMetrics] = defaultdict(ServiceMetrics)
        self.circuit_breakers: Dict[str, CircuitBreaker] = {}
        
        # Round-robin state
        self.round_robin_index: Dict[int, int] = defaultdict(int)  # priority -> index
        
        logger.info(
            f"LLMBus initialized with {distribution_strategy} distribution strategy"
        )
    
    async def generate_structured(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        handler_name: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> Tuple[BaseModel, ResourceUsage]:
        """
        Generate structured output using LLM.
        
        This method handles:
        - Service discovery by priority
        - Distribution based on strategy
        - Circuit breaker checks
        - Automatic failover
        - Metrics collection
        """
        start_time = time.time()
        
        # Get all available LLM services
        services = await self._get_prioritized_services(handler_name)
        
        if not services:
            raise RuntimeError(f"No LLM services available for {handler_name}")
        
        # Group services by priority
        priority_groups = self._group_by_priority(services)
        
        # Try each priority group in order
        last_error = None
        for priority, service_group in sorted(priority_groups.items()):
            # Select service from this priority group based on strategy
            selected_service = await self._select_service(
                service_group,
                priority,
                handler_name
            )
            
            if not selected_service:
                continue
                
            service_name = type(selected_service).__name__
            
            # Check circuit breaker
            if not self._check_circuit_breaker(service_name):
                logger.warning(
                    f"Circuit breaker OPEN for {service_name}, skipping"
                )
                continue
            
            try:
                # Make the LLM call
                logger.debug(
                    f"Calling LLM service {service_name} for {handler_name}"
                )
                
                result, usage = await selected_service.call_llm_structured(
                    messages=messages,
                    response_model=response_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    **kwargs
                )
                
                # Record success
                latency_ms = (time.time() - start_time) * 1000
                self._record_success(service_name, latency_ms)
                
                # Record telemetry for resource usage
                await self._record_resource_telemetry(
                    service_name=service_name,
                    handler_name=handler_name,
                    usage=usage,
                    latency_ms=latency_ms
                )
                
                logger.debug(
                    f"LLM call successful via {service_name} "
                    f"(latency: {latency_ms:.2f}ms)"
                )
                
                return result, usage
                
            except Exception as e:
                # Record failure
                self._record_failure(service_name)
                last_error = e
                
                logger.error(
                    f"LLM service {service_name} failed: {e}",
                    exc_info=True
                )
                
                # Continue to next service
                continue
        
        # All services failed
        raise RuntimeError(
            f"All LLM services failed for {handler_name}. "
            f"Last error: {last_error}"
        )
    
    async def generate_structured_sync(
        self,
        messages: List[Dict[str, str]],
        response_model: Type[BaseModel],
        handler_name: str,
        max_tokens: int = 1024,
        temperature: float = 0.0,
        **kwargs: Any
    ) -> Tuple[BaseModel, ResourceUsage]:
        """
        Synchronous version of generate_structured.
        
        This is what the handlers will call directly.
        """
        return await self.generate_structured(
            messages=messages,
            response_model=response_model,
            handler_name=handler_name,
            max_tokens=max_tokens,
            temperature=temperature,
            **kwargs
        )
    
    async def _get_prioritized_services(
        self,
        handler_name: str
    ) -> List[Tuple[Any, int]]:
        """Get all available LLM services with their priorities"""
        services = []
        
        # For now, just get a single service from the registry
        # In the future, we could enhance the registry to return multiple services
        service = await self.service_registry.get_service(
            handler=handler_name,
            service_type=ServiceType.LLM,
            required_capabilities=[LLMCapabilities.CALL_LLM_STRUCTURED],
            fallback_to_global=True
        )
        
        if service and await self._is_service_healthy(service):
            # Default priority for now
            services.append((service, 0))
        
        return services
    
    def _group_by_priority(
        self,
        services: List[Tuple[Any, int]]
    ) -> Dict[int, List[Any]]:
        """Group services by priority"""
        groups = defaultdict(list)
        for service, priority in services:
            groups[priority].append(service)
        return groups
    
    async def _select_service(
        self,
        services: List[Any],
        priority: int,
        handler_name: str
    ) -> Optional[Any]:
        """Select a service from a priority group based on distribution strategy"""
        if not services:
            return None
            
        if len(services) == 1:
            return services[0]
        
        if self.distribution_strategy == DistributionStrategy.ROUND_ROBIN:
            # Round-robin selection
            index = self.round_robin_index[priority] % len(services)
            self.round_robin_index[priority] += 1
            return services[index]
            
        elif self.distribution_strategy == DistributionStrategy.LATENCY_BASED:
            # Select service with lowest average latency
            best_service = None
            best_latency = float('inf')
            
            for service in services:
                service_name = type(service).__name__
                metrics = self.service_metrics[service_name]
                
                # New services get a chance
                if metrics.total_requests == 0:
                    return service
                    
                if metrics.average_latency_ms < best_latency:
                    best_latency = metrics.average_latency_ms
                    best_service = service
            
            return best_service or services[0]
            
        elif self.distribution_strategy == DistributionStrategy.RANDOM:
            # Random selection
            import random
            return random.choice(services)
            
        else:  # DistributionStrategy.LEAST_LOADED
            # Select service with fewest active requests
            # This would require tracking active requests
            # For now, use the one with fewest total requests
            return min(
                services,
                key=lambda s: self.service_metrics[type(s).__name__].total_requests
            )
    
    async def _is_service_healthy(self, service: Any) -> bool:
        """Check if a service is healthy"""
        try:
            result = await service.is_healthy()
            return bool(result)
        except Exception:
            return False
    
    def _check_circuit_breaker(self, service_name: str) -> bool:
        """Check if circuit breaker allows execution"""
        if service_name not in self.circuit_breakers:
            self.circuit_breakers[service_name] = CircuitBreaker(
                **self.circuit_breaker_config
            )
        
        return self.circuit_breakers[service_name].can_execute()
    
    def _record_success(self, service_name: str, latency_ms: float) -> None:
        """Record successful call metrics"""
        metrics = self.service_metrics[service_name]
        metrics.total_requests += 1
        metrics.total_latency_ms += latency_ms
        metrics.last_request_time = datetime.utcnow()
        metrics.consecutive_failures = 0
        
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name].record_success()
    
    def _record_failure(self, service_name: str) -> None:
        """Record failed call metrics"""
        metrics = self.service_metrics[service_name]
        metrics.total_requests += 1
        metrics.failed_requests += 1
        metrics.last_failure_time = datetime.utcnow()
        metrics.consecutive_failures += 1
        
        if service_name in self.circuit_breakers:
            self.circuit_breakers[service_name].record_failure()
    
    async def _record_resource_telemetry(
        self,
        service_name: str,
        handler_name: str,
        usage: ResourceUsage,
        latency_ms: float
    ) -> None:
        """Record detailed telemetry for resource usage"""
        if not self.telemetry_bus:
            return
            
        try:
            # Record token usage
            await self.telemetry_bus.record_metric(
                metric_name="llm.tokens.total",
                value=float(usage.tokens_used),
                handler_name=handler_name,
                tags={
                    "service": service_name,
                    "model": usage.model_used or "unknown",
                    "handler": handler_name
                }
            )
            
            # Record input/output tokens separately
            if usage.tokens_input > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.tokens.input",
                    value=float(usage.tokens_input),
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            if usage.tokens_output > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.tokens.output",
                    value=float(usage.tokens_output),
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            # Record cost
            if usage.cost_cents > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.cost.cents",
                    value=usage.cost_cents,
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            # Record environmental impact
            if usage.water_ml > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.environmental.water_ml",
                    value=usage.water_ml,
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            if usage.carbon_g > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.environmental.carbon_g",
                    value=usage.carbon_g,
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            if usage.energy_kwh > 0:
                await self.telemetry_bus.record_metric(
                    metric_name="llm.environmental.energy_kwh",
                    value=usage.energy_kwh,
                    handler_name=handler_name,
                    tags={"service": service_name, "model": usage.model_used or "unknown"}
                )
            
            # Record latency
            await self.telemetry_bus.record_metric(
                metric_name="llm.latency.ms",
                value=latency_ms,
                handler_name=handler_name,
                tags={"service": service_name, "model": usage.model_used or "unknown"}
            )
            
        except Exception as e:
            logger.warning(f"Failed to record telemetry: {e}")
    
    def get_service_stats(self) -> Dict[str, Any]:
        """Get detailed statistics for all services"""
        stats = {}
        
        for service_name, metrics in self.service_metrics.items():
            circuit_breaker = self.circuit_breakers.get(service_name)
            
            stats[service_name] = {
                "total_requests": metrics.total_requests,
                "failed_requests": metrics.failed_requests,
                "failure_rate": f"{metrics.failure_rate * 100:.2f}%",
                "average_latency_ms": f"{metrics.average_latency_ms:.2f}",
                "consecutive_failures": metrics.consecutive_failures,
                "circuit_breaker_state": circuit_breaker.state if circuit_breaker else "none",
                "last_request": metrics.last_request_time.isoformat() if metrics.last_request_time else None,
                "last_failure": metrics.last_failure_time.isoformat() if metrics.last_failure_time else None
            }
        
        return stats
    
    async def _process_message(self, message: BusMessage) -> None:
        """Process an LLM message from the queue"""
        if isinstance(message, LLMRequest):
            # For async processing, we would handle the request here
            # and set the result on the future
            # For now, LLM calls are synchronous
            logger.warning("Async LLM processing not yet implemented")
        else:
            logger.error(f"Unknown message type: {type(message)}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get bus statistics including service stats"""
        base_stats = super().get_stats()
        base_stats["service_stats"] = self.get_service_stats()
        base_stats["distribution_strategy"] = self.distribution_strategy.value
        return base_stats