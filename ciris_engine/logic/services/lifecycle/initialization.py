"""
Initialization Service for CIRIS Trinity Architecture.

Manages system initialization coordination with verification at each phase.
This replaces the initialization_manager.py utility with a proper service.
"""
import asyncio
import logging
from typing import Dict, List, Optional, Callable, Awaitable
from datetime import datetime
from dataclasses import dataclass

from ciris_engine.protocols.services import InitializationServiceProtocol
from ciris_engine.protocols.runtime.base import ServiceProtocol
from ciris_engine.protocols.services.lifecycle.time import TimeServiceProtocol
from ciris_engine.schemas.services.core import ServiceCapabilities, ServiceStatus
from ciris_engine.schemas.services.lifecycle.initialization import (
    InitializationStatus, InitializationVerification
)
from ciris_engine.schemas.services.operations import InitializationPhase

logger = logging.getLogger(__name__)

@dataclass
class InitializationStep:
    """Represents a single initialization step."""
    phase: InitializationPhase
    name: str
    handler: Callable[[], Awaitable[None]]
    verifier: Optional[Callable[[], Awaitable[bool]]] = None
    critical: bool = True
    timeout: float = 30.0

class InitializationService(InitializationServiceProtocol, ServiceProtocol):
    """Service for coordinating system initialization."""

    def __init__(self, time_service: TimeServiceProtocol):
        """Initialize the initialization service."""
        self.time_service = time_service
        self._steps: List[InitializationStep] = []
        self._completed_steps: List[str] = []
        self._phase_status: Dict[InitializationPhase, str] = {}
        self._start_time: Optional[datetime] = None
        self._initialization_complete = False
        self._error: Optional[Exception] = None
        self._running = False

    async def start(self) -> None:
        """Start the service."""
        self._running = True
        logger.info("InitializationService started")

    async def stop(self) -> None:
        """Stop the service."""
        self._running = False
        logger.info("InitializationService stopped")

    def get_capabilities(self) -> ServiceCapabilities:
        """Get service capabilities."""
        return ServiceCapabilities(
            service_name="InitializationService",
            actions=[
                "register_step",
                "initialize",
                "is_initialized",
                "get_initialization_status"
            ],
            version="1.0.0",
            dependencies=["TimeService"],
            metadata=None
        )

    def get_status(self) -> ServiceStatus:
        """Get service status."""
        duration = None
        if self._start_time:
            duration = (self.time_service.now() - self._start_time).total_seconds()

        return ServiceStatus(
            service_name="InitializationService",
            service_type="core_service",
            is_healthy=self._running and (self._initialization_complete or self._error is None),
            uptime_seconds=duration or 0.0,
            metrics={
                "initialization_complete": self._initialization_complete,
                "completed_steps": len(self._completed_steps),
                "total_steps": len(self._steps),
                "has_error": self._error is not None
            },
            last_error=str(self._error) if self._error else None,
            last_health_check=self.time_service.now()
        )

    async def is_healthy(self) -> bool:
        """Check if service is healthy."""
        return self._running and (self._initialization_complete or self._error is None)

    def register_step(
        self,
        phase: InitializationPhase,
        name: str,
        handler: Callable[[], Awaitable[None]],
        verifier: Optional[Callable[[], Awaitable[bool]]] = None,
        critical: bool = True,
        timeout: float = 30.0
    ) -> None:
        """
        Register an initialization step.

        Args:
            phase: Initialization phase
            name: Step name
            handler: Async function to execute
            verifier: Optional async function to verify step
            critical: If True, failure stops initialization
            timeout: Maximum time for step execution
        """
        step = InitializationStep(
            phase=phase,
            name=name,
            handler=handler,
            verifier=verifier,
            critical=critical,
            timeout=timeout
        )
        self._steps.append(step)
        logger.debug(f"Registered initialization step: {phase.value}/{name}")

    async def initialize(self) -> bool:
        """Initialize the entire system."""
        self._start_time = self.time_service.now()
        logger.info("=" * 60)
        logger.info("CIRIS Agent Initialization Sequence Starting")
        logger.info("=" * 60)

        try:
            # Group steps by phase
            phases: Dict[InitializationPhase, List[InitializationStep]] = {}
            for step in self._steps:
                if step.phase not in phases:
                    phases[step.phase] = []
                phases[step.phase].append(step)

            # Execute phases in order
            for phase in InitializationPhase:
                if phase not in phases:
                    continue

                await self._execute_phase(phase, phases[phase])

                if self._error and phase != InitializationPhase.VERIFICATION:
                    raise self._error

            # Set initialization complete
            self._initialization_complete = True
            duration = (self.time_service.now() - self._start_time).total_seconds()

            logger.info("=" * 60)
            logger.info(f"✓ CIRIS Agent Initialization Complete ({duration:.1f}s)")
            logger.info("=" * 60)

        except Exception as e:
            duration = (self.time_service.now() - self._start_time).total_seconds()
            logger.error("=" * 60)
            logger.error(f"✗ CIRIS Agent Initialization Failed ({duration:.1f}s)")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            self._error = e
            return False

        return True

    async def verify_initialization(self) -> InitializationVerification:
        """Verify all components are initialized."""
        # Check each phase
        phase_results = {}
        for phase, status in self._phase_status.items():
            phase_results[phase.value] = (status == "completed")

        # Check all registered steps completed
        total_steps = len(self._steps)
        completed_steps = len(self._completed_steps)

        return InitializationVerification(
            system_initialized=self._initialization_complete,
            no_errors=(self._error is None),
            all_steps_completed=(total_steps == completed_steps),
            phase_results=phase_results
        )

    def _is_initialized(self) -> bool:
        """Check if initialization is complete (internal)."""
        return self._initialization_complete

    async def get_initialization_status(self) -> InitializationStatus:
        """Get detailed initialization status."""
        duration = None
        if self._start_time:
            duration = (self.time_service.now() - self._start_time).total_seconds()

        return InitializationStatus(
            complete=self._initialization_complete,
            start_time=self._start_time,
            duration_seconds=duration,
            completed_steps=self._completed_steps,
            phase_status={phase.value: status for phase, status in self._phase_status.items()},
            error=str(self._error) if self._error else None,
            total_steps=len(self._steps)
        )

    async def _execute_phase(self, phase: InitializationPhase, steps: List[InitializationStep]) -> None:
        """Execute all steps in a phase."""
        logger.info("-" * 60)
        logger.info(f"Phase: {phase.value.upper()}")
        logger.info("-" * 60)

        self._phase_status[phase] = "running"

        for step in steps:
            await self._execute_step(step)

            if self._error and step.critical:
                self._phase_status[phase] = "failed"
                return

        self._phase_status[phase] = "completed"
        logger.info(f"✓ Phase {phase.value} completed successfully")

    async def _execute_step(self, step: InitializationStep) -> None:
        """Execute a single initialization step with timeout and verification."""
        step_name = f"{step.phase.value}/{step.name}"
        logger.info(f"→ {step.name}...")

        try:
            # Execute the step with timeout
            await asyncio.wait_for(step.handler(), timeout=step.timeout)

            # Verify if provided
            if step.verifier:
                logger.debug(f"  Verifying {step.name}...")
                verified = await asyncio.wait_for(step.verifier(), timeout=10.0)

                if not verified:
                    raise Exception(f"Verification failed for {step.name}")

            self._completed_steps.append(step_name)
            logger.info(f"  ✓ {step.name} initialized")

        except asyncio.TimeoutError:
            error_msg = f"{step.name} timed out after {step.timeout}s"
            logger.error(f"  ✗ {error_msg}")

            if step.critical:
                self._error = Exception(error_msg)
                raise self._error

        except Exception as e:
            logger.error(f"  ✗ {step.name} failed: {e}")

            if step.critical:
                self._error = e
                raise
