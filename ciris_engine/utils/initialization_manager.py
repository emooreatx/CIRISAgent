"""
Graceful initialization manager for CIRIS Agent.

Provides a structured, step-by-step initialization process with verification
at each stage, mirroring the graceful shutdown manager pattern.
"""

import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable, Awaitable
from datetime import datetime, timezone
from enum import Enum
from dataclasses import dataclass

logger = logging.getLogger(__name__)


class InitializationPhase(Enum):
    """Phases of the initialization process."""
    DATABASE = "database"
    MEMORY = "memory"
    IDENTITY = "identity"
    SECURITY = "security"
    SERVICES = "services"
    COMPONENTS = "components"
    VERIFICATION = "verification"
    READY = "ready"


@dataclass
class InitializationStep:
    """Represents a single initialization step."""
    phase: InitializationPhase
    name: str
    handler: Callable[[], Awaitable[None]]
    verifier: Optional[Callable[[], Awaitable[bool]]] = None
    critical: bool = True
    timeout: float = 30.0


class InitializationError(Exception):
    """Raised when initialization fails."""
    pass


class InitializationManager:
    """
    Manages the graceful initialization of the CIRIS Agent.
    
    This ensures all components are initialized in the correct order
    with proper verification at each step.
    """
    
    def __init__(self) -> None:
        self._steps: List[InitializationStep] = []
        self._completed_steps: List[str] = []
        self._phase_status: Dict[InitializationPhase, str] = {}
        self._start_time: Optional[datetime] = None
        self._initialization_complete = False
        self._error: Optional[Exception] = None
        
    def register_step(
        self,
        phase: InitializationPhase,
        name: str,
        handler: Callable[[], Awaitable[None]],
        verifier: Optional[Callable[[], Awaitable[bool]]] = None,
        critical: bool = True,
        timeout: float = 30.0
    ) -> None:
        """Register an initialization step."""
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
    
    async def initialize(self) -> None:
        """
        Execute the initialization sequence.
        
        Runs all registered initialization steps in order, with verification
        after each critical step.
        """
        self._start_time = datetime.now(timezone.utc)
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
            
            # Set initialization complete BEFORE the final status logging
            self._initialization_complete = True
            duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            
            logger.info("=" * 60)
            logger.info(f"✓ CIRIS Agent Initialization Complete ({duration:.1f}s)")
            logger.info("=" * 60)
            
        except Exception as e:
            duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()
            logger.error("=" * 60)
            logger.error(f"✗ CIRIS Agent Initialization Failed ({duration:.1f}s)")
            logger.error(f"Error: {e}")
            logger.error("=" * 60)
            raise InitializationError(f"Initialization failed: {e}") from e
    
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
                    raise InitializationError(f"Verification failed for {step.name}")
            
            self._completed_steps.append(step_name)
            logger.info(f"  ✓ {step.name} initialized")
            
        except asyncio.TimeoutError:
            error_msg = f"{step.name} timed out after {step.timeout}s"
            logger.error(f"  ✗ {error_msg}")
            
            if step.critical:
                self._error = InitializationError(error_msg)
                raise self._error
            else:
                logger.warning(f"  Continuing despite non-critical failure: {step.name}")
                
        except Exception as e:
            logger.error(f"  ✗ {step.name} failed: {e}")
            
            if step.critical:
                self._error = e
                raise
            else:
                logger.warning(f"  Continuing despite non-critical failure: {step.name}")
    
    def get_status(self) -> Dict[str, Any]:
        """Get the current initialization status."""
        duration = None
        if self._start_time:
            duration = (datetime.now(timezone.utc) - self._start_time).total_seconds()
        
        return {
            "complete": self._initialization_complete,
            "start_time": self._start_time.isoformat() if self._start_time else None,
            "duration_seconds": duration,
            "completed_steps": self._completed_steps,
            "phase_status": {phase.value: status for phase, status in self._phase_status.items()},
            "error": str(self._error) if self._error else None
        }
    
    def is_initialized(self) -> bool:
        """Check if initialization is complete."""
        return self._initialization_complete
    
    def get_error(self) -> Optional[Exception]:
        """Get any error that occurred during initialization."""
        return self._error


# Global initialization manager instance
_initialization_manager: Optional[InitializationManager] = None


def get_initialization_manager() -> InitializationManager:
    """Get the global initialization manager instance."""
    global _initialization_manager
    if _initialization_manager is None:
        _initialization_manager = InitializationManager()
    return _initialization_manager


async def register_initialization_handler(
    phase: InitializationPhase,
    name: str,
    handler: Callable[[], Awaitable[None]],
    verifier: Optional[Callable[[], Awaitable[bool]]] = None,
    critical: bool = True,
    timeout: float = 30.0
) -> None:
    """Register an initialization handler with the global manager."""
    manager = get_initialization_manager()
    manager.register_step(phase, name, handler, verifier, critical, timeout)


async def run_initialization() -> None:
    """Run the initialization sequence."""
    manager = get_initialization_manager()
    await manager.initialize()


def is_initialization_complete() -> bool:
    """Check if initialization is complete."""
    manager = get_initialization_manager()
    return manager.is_initialized()


def get_initialization_status() -> Dict[str, Any]:
    """Get the initialization status."""
    manager = get_initialization_manager()
    return manager.get_status()