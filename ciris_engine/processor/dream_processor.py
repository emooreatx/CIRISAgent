"""
Dream Processor for CIRISAgent.

Integrates memory consolidation, self-configuration, and introspection during dream cycles.
Falls back to benchmark mode when CIRISNode is configured.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING, Tuple
from datetime import datetime, timezone, timedelta
from dataclasses import dataclass, field
from enum import Enum

from ciris_engine.adapters import CIRISNodeClient
from ciris_engine.schemas.config_schemas_v1 import AppConfig
from ciris_engine.schemas.graph_schemas_v1 import GraphNode, GraphScope, NodeType
from ciris_engine.schemas.memory_schemas_v1 import MemoryQuery
from ciris_engine.schemas.context_schemas_v1 import SystemSnapshot, ThoughtSummary, CompactTelemetry
from ciris_engine.schemas.foundational_schemas_v1 import HandlerActionType
from ciris_engine.services.self_configuration_service import SelfConfigurationService
from ciris_engine.services.unified_telemetry_service import UnifiedTelemetryService
from ciris_engine.message_buses.memory_bus import MemoryBus
from ciris_engine.message_buses.communication_bus import CommunicationBus

if TYPE_CHECKING:
    from ciris_engine.registries.base import ServiceRegistry
    from ciris_engine.runtime.identity_manager import IdentityManager

logger = logging.getLogger(__name__)


class DreamPhase(str, Enum):
    """Phases of dream processing."""
    ENTERING = "entering"
    CONSOLIDATING = "consolidating"
    ANALYZING = "analyzing"
    CONFIGURING = "configuring"
    PLANNING = "planning"
    BENCHMARKING = "benchmarking"
    EXITING = "exiting"


@dataclass
class DreamSession:
    """Represents a complete dream session."""
    session_id: str
    scheduled_start: Optional[datetime]
    actual_start: datetime
    planned_duration: timedelta
    phase: DreamPhase
    
    # Work completed
    memories_consolidated: int = 0
    patterns_analyzed: int = 0
    adaptations_made: int = 0
    future_tasks_scheduled: int = 0
    benchmarks_run: int = 0
    
    # Insights
    ponder_questions_processed: List[str] = field(default_factory=list)
    insights_gained: List[str] = field(default_factory=list)
    
    # Timing
    phase_durations: Dict[str, float] = field(default_factory=dict)
    completed_at: Optional[datetime] = None


class DreamProcessor:
    """
    Dream processor that handles introspection, memory consolidation,
    and self-configuration during dream states.
    """
    
    def __init__(
        self,
        app_config: AppConfig,
        service_registry: Optional["ServiceRegistry"],
        identity_manager: Optional["IdentityManager"] = None,
        startup_channel_id: Optional[str] = None,
        cirisnode_url: str = "https://localhost:8001",
        pulse_interval: float = 300.0,  # 5 minutes between major activities
        min_dream_duration: int = 30,  # Minimum 30 minutes
        max_dream_duration: int = 120  # Maximum 2 hours
    ) -> None:
        self.app_config = app_config
        self.service_registry = service_registry
        self.identity_manager = identity_manager
        self.startup_channel_id = startup_channel_id
        self.cirisnode_url = cirisnode_url
        self.pulse_interval = pulse_interval
        self.min_dream_duration = min_dream_duration
        self.max_dream_duration = max_dream_duration
        
        # Check if CIRISNode is configured
        self.cirisnode_enabled = self._check_cirisnode_enabled()
        self.cirisnode_client: Optional[CIRISNodeClient] = None
        
        # Service components
        self.self_config_service: Optional[SelfConfigurationService] = None
        self.telemetry_service: Optional[UnifiedTelemetryService] = None
        self.memory_bus: Optional[MemoryBus] = None
        self.communication_bus: Optional[CommunicationBus] = None
        
        # Dream state
        self.current_session: Optional[DreamSession] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._dream_task: Optional[asyncio.Task] = None
        
        # Metrics from original processor
        self.dream_metrics: Dict[str, Any] = {
            "total_dreams": 0,
            "total_introspections": 0,
            "total_consolidations": 0,
            "total_adaptations": 0,
            "benchmarks_run": 0,
            "start_time": None,
            "end_time": None
        }
    
    def _check_cirisnode_enabled(self) -> bool:
        """Check if CIRISNode is configured."""
        if hasattr(self.app_config, 'cirisnode'):
            node_cfg = self.app_config.cirisnode
            # Check if hostname is set and not default
            return bool(node_cfg.base_url and 
                       node_cfg.base_url != "https://localhost:8001" and
                       node_cfg.base_url != "http://localhost:8001")
        return False
    
    def _ensure_stop_event(self) -> None:
        """Ensure stop event is created when needed in async context."""
        if self._stop_event is None:
            try:
                self._stop_event = asyncio.Event()
            except RuntimeError:
                logger.warning("Cannot create stop event outside of async context")
    
    async def _initialize_services(self) -> None:
        """Initialize required services."""
        if not self.service_registry:
            logger.warning("No service registry available for dream processor")
            return
        
        try:
            # Initialize buses
            from ciris_engine.message_buses import MemoryBus, CommunicationBus
            self.memory_bus = MemoryBus(self.service_registry)
            self.communication_bus = CommunicationBus(self.service_registry)
            
            # Initialize self-configuration service
            self.self_config_service = SelfConfigurationService(
                memory_bus=self.memory_bus,
                adaptation_interval_hours=6  # Match our dream schedule
            )
            self.self_config_service.set_service_registry(self.service_registry)
            
            # Initialize telemetry service
            self.telemetry_service = UnifiedTelemetryService(
                memory_bus=self.memory_bus,
                consolidation_threshold_hours=6  # Consolidate during dreams
            )
            self.telemetry_service.set_service_registry(self.service_registry)
            
            # Initialize identity baseline if needed
            if self.identity_manager and self.identity_manager.agent_identity:
                await self.self_config_service.initialize_identity_baseline(
                    self.identity_manager.agent_identity
                )
            
            logger.info("Dream processor services initialized")
            
        except Exception as e:
            logger.error(f"Failed to initialize dream services: {e}")
    
    async def start_dreaming(self, duration: Optional[float] = None) -> None:
        """
        Start the dream cycle.
        
        Args:
            duration: Dream duration in seconds. Defaults to min_dream_duration.
        """
        if self._dream_task and not self._dream_task.done():
            logger.warning("Dream cycle already running")
            return
        
        # Initialize services if not done
        if not self.self_config_service:
            await self._initialize_services()
        
        # Calculate duration
        if duration is None:
            duration = self.min_dream_duration * 60  # Convert to seconds
        else:
            # Clamp to min/max
            duration = max(self.min_dream_duration * 60, 
                          min(duration, self.max_dream_duration * 60))
        
        self._ensure_stop_event()
        if self._stop_event:
            self._stop_event.clear()
        
        # Create session
        self.current_session = DreamSession(
            session_id=f"dream_{int(datetime.now(timezone.utc).timestamp())}",
            scheduled_start=None,  # This is immediate entry
            actual_start=datetime.now(timezone.utc),
            planned_duration=timedelta(seconds=duration),
            phase=DreamPhase.ENTERING
        )
        
        self.dream_metrics["start_time"] = datetime.now(timezone.utc).isoformat()
        self.dream_metrics["total_dreams"] += 1
        
        # Announce dream entry
        await self._announce_dream_entry(duration)
        
        # Initialize CIRISNode client if enabled
        if self.cirisnode_enabled:
            self.cirisnode_client = CIRISNodeClient(
                service_registry=self.service_registry, 
                base_url=self.cirisnode_url
            )
        
        logger.info(f"Starting dream cycle (duration: {duration}s)")
        self._dream_task = asyncio.create_task(self._dream_loop(duration))
    
    async def stop_dreaming(self) -> None:
        """Stop the dream cycle gracefully."""
        if self._dream_task and not self._dream_task.done():
            logger.info("Stopping active dream cycle...")
            if self._stop_event:
                self._stop_event.set()
            
            try:
                await asyncio.wait_for(self._dream_task, timeout=30.0)
            except asyncio.TimeoutError:
                logger.warning("Dream cycle did not stop within timeout, cancelling")
                self._dream_task.cancel()
                try:
                    await self._dream_task
                except asyncio.CancelledError:
                    logger.info("Dream task cancelled.")
            except Exception as e:
                logger.error(f"Error waiting for dream task: {e}", exc_info=True)
        
        # Clean up CIRISNode client
        if self.cirisnode_client:
            try:
                await self.cirisnode_client.close()
            except Exception as e:
                logger.error(f"Error closing CIRISNode client: {e}")
            self.cirisnode_client = None
        
        if self.current_session:
            self.current_session.completed_at = datetime.now(timezone.utc)
            await self._record_dream_session()
        
        self.dream_metrics["end_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Dream cycle stopped")
    
    async def _announce_dream_entry(self, duration: float) -> None:
        """Announce dream entry to main channel."""
        if not self.communication_bus or not self.startup_channel_id:
            logger.debug("Cannot announce dream entry - no communication channel")
            return
        
        try:
            duration_min = int(duration / 60)
            message = (
                f"Entering self-reflection mode. "
                f"Returning in {duration_min} minutes or when complete."
            )
            
            await self.communication_bus.send_message(
                content=message,
                channel_id=self.startup_channel_id,
                handler_name="dream_processor"
            )
        except Exception as e:
            logger.error(f"Failed to announce dream entry: {e}")
    
    async def _dream_loop(self, duration: float) -> None:
        """Main dream processing loop with phases."""
        if not self.current_session:
            logger.error("No current session in dream loop")
            return
            
        try:
            start_time = asyncio.get_event_loop().time()
            end_time = start_time + duration
            phase_start = datetime.now(timezone.utc)
            
            # Phase 1: Memory Consolidation
            if self.current_session:
                self.current_session.phase = DreamPhase.CONSOLIDATING
            await self._consolidation_phase()
            self._record_phase_duration(DreamPhase.CONSOLIDATING, phase_start)
            
            if self._should_exit(start_time, end_time):
                return
            
            # Phase 2: Pattern Analysis
            phase_start = datetime.now(timezone.utc)
            if self.current_session:
                self.current_session.phase = DreamPhase.ANALYZING
            await self._analysis_phase()
            self._record_phase_duration(DreamPhase.ANALYZING, phase_start)
            
            if self._should_exit(start_time, end_time):
                return
            
            # Phase 3: Self-Configuration
            phase_start = datetime.now(timezone.utc)
            if self.current_session:
                self.current_session.phase = DreamPhase.CONFIGURING
            await self._configuration_phase()
            self._record_phase_duration(DreamPhase.CONFIGURING, phase_start)
            
            if self._should_exit(start_time, end_time):
                return
            
            # Phase 4: Future Planning
            phase_start = datetime.now(timezone.utc)
            if self.current_session:
                self.current_session.phase = DreamPhase.PLANNING
            await self._planning_phase()
            self._record_phase_duration(DreamPhase.PLANNING, phase_start)
            
            # Phase 5: Benchmarking (if enabled and time remains)
            if self.cirisnode_enabled and not self._should_exit(start_time, end_time):
                phase_start = datetime.now(timezone.utc)
                if self.current_session:
                    self.current_session.phase = DreamPhase.BENCHMARKING
                await self._benchmarking_phase(start_time, end_time)
                self._record_phase_duration(DreamPhase.BENCHMARKING, phase_start)
            
            # Phase 6: Exit
            if self.current_session:
                self.current_session.phase = DreamPhase.EXITING
            await self._exit_phase()
            
            logger.info("Dream cycle completed successfully")
            
        except Exception as e:
            logger.error(f"Error in dream loop: {e}", exc_info=True)
        finally:
            if self._stop_event:
                self._stop_event.set()
    
    def _should_exit(self, start_time: float, end_time: float) -> bool:
        """Check if we should exit the dream loop."""
        if self._stop_event and self._stop_event.is_set():
            return True
        
        current_time = asyncio.get_event_loop().time()
        if current_time >= end_time:
            logger.info(f"Dream duration reached")
            return True
        
        return False
    
    def _record_phase_duration(self, phase: DreamPhase, start_time: datetime) -> None:
        """Record how long a phase took."""
        if not self.current_session:
            return
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        self.current_session.phase_durations[phase.value] = duration
    
    async def _consolidation_phase(self) -> None:
        """Memory consolidation phase."""
        logger.info("Dream Phase: Memory Consolidation")
        
        if not self.telemetry_service:
            logger.warning("Telemetry service not available for consolidation")
            return
        
        try:
            # Run memory consolidation with grace
            result = await self.telemetry_service.consolidate_memories_with_grace()
            
            if self.current_session:
                self.current_session.memories_consolidated = result.get("memories_consolidated", 0)
                self.dream_metrics["total_consolidations"] += 1
                
                # Extract wisdom as insights
                if "wisdom_note" in result:
                    self.current_session.insights_gained.append(result["wisdom_note"])
                
                logger.info(f"Consolidated {self.current_session.memories_consolidated} memories")
            
        except Exception as e:
            logger.error(f"Error in consolidation phase: {e}")
    
    async def _analysis_phase(self) -> None:
        """Pattern analysis phase."""
        logger.info("Dream Phase: Pattern Analysis")
        
        try:
            # Recall recent PONDER questions
            ponder_questions = await self._recall_recent_ponder_questions()
            if self.current_session:
                self.current_session.ponder_questions_processed = ponder_questions
                
                # Analyze patterns in questions
                if ponder_questions:
                    insights = self._analyze_ponder_patterns(ponder_questions)
                    self.current_session.insights_gained.extend(insights)
                
                self.current_session.patterns_analyzed = len(ponder_questions)
            self.dream_metrics["total_introspections"] += 1
            
            logger.info(f"Analyzed {len(ponder_questions)} PONDER questions")
            
        except Exception as e:
            logger.error(f"Error in analysis phase: {e}")
    
    async def _configuration_phase(self) -> None:
        """Self-configuration phase."""
        logger.info("Dream Phase: Self-Configuration")
        
        if not self.self_config_service:
            logger.warning("Self-config service not available")
            return
        
        try:
            # Create a synthetic SystemSnapshot for the dream context
            session_id = self.current_session.session_id if self.current_session else "unknown"
            snapshot = SystemSnapshot(
                agent_name=self.identity_manager.agent_identity.agent_id if self.identity_manager and self.identity_manager.agent_identity else "ciris",
                network_status="dreaming",
                isolation_hours=0,
                current_thought_summary=ThoughtSummary(
                    thought_id=f"dream_thought_{session_id}",
                    content="Dream introspection and adaptation",
                    thought_type="INTROSPECTION"
                ),
                telemetry=None  # CompactTelemetry not needed for dream phase
            )
            
            # Process through self-configuration
            result = await self.self_config_service.process_experience(
                snapshot=snapshot,
                thought_id=f"dream_thought_{session_id}",
                task_id=f"dream_task_{session_id}"
            )
            
            if result.get("adaptation_triggered") and self.current_session:
                adaptation_result = result.get("adaptation_result", {})
                self.current_session.adaptations_made = adaptation_result.get("changes_applied", 0)
                self.dream_metrics["total_adaptations"] += self.current_session.adaptations_made
            
            if self.current_session:
                logger.info(f"Applied {self.current_session.adaptations_made} adaptations")
            
        except Exception as e:
            logger.error(f"Error in configuration phase: {e}")
    
    async def _planning_phase(self) -> None:
        """Future planning phase."""
        logger.info("Dream Phase: Future Planning")
        
        try:
            # Schedule next dream session
            next_dream_id = await self._schedule_next_dream()
            if next_dream_id and self.current_session:
                self.current_session.future_tasks_scheduled += 1
            
            # Create future tasks based on insights
            future_tasks = await self._plan_future_work()
            if self.current_session:
                self.current_session.future_tasks_scheduled += len(future_tasks)
                logger.info(f"Scheduled {self.current_session.future_tasks_scheduled} future tasks")
            
        except Exception as e:
            logger.error(f"Error in planning phase: {e}")
    
    async def _benchmarking_phase(self, start_time: float, end_time: float) -> None:
        """Benchmarking phase (if CIRISNode is available)."""
        logger.info("Dream Phase: Benchmarking")
        
        if not self.cirisnode_client:
            return
        
        # Run benchmarks until time runs out
        while not self._should_exit(start_time, end_time):
            try:
                await self._run_single_benchmark()
                if self.current_session:
                    self.current_session.benchmarks_run += 1
                
                # Wait between benchmarks or exit if signaled
                try:
                    if self._stop_event:
                        await asyncio.wait_for(
                            self._stop_event.wait(),
                            timeout=60.0  # 1 minute between benchmarks in dream
                        )
                        break
                    else:
                        await asyncio.sleep(60.0)
                except asyncio.TimeoutError:
                    pass
                    
            except Exception as e:
                logger.error(f"Error running benchmark: {e}")
                break
    
    async def _exit_phase(self) -> None:
        """Dream exit phase."""
        logger.info("Dream Phase: Exiting")
        
        try:
            # Record dream session
            await self._record_dream_session()
            
            # Announce dream completion
            await self._announce_dream_exit()
            
        except Exception as e:
            logger.error(f"Error in exit phase: {e}")
    
    async def _recall_recent_ponder_questions(self) -> List[str]:
        """Recall recent PONDER questions from memory."""
        if not self.memory_bus:
            return []
        
        try:
            # Query for recent thoughts with PONDER actions
            query = MemoryQuery(
                node_id="thought/*",
                scope=GraphScope.LOCAL,
                type=None,
                include_edges=False,
                depth=1
            )
            
            thoughts = await self.memory_bus.recall(
                recall_query=query,
                handler_name="dream_processor"
            )
            
            # Extract PONDER questions
            questions = []
            for thought in thoughts[-100:]:  # Last 100 thoughts
                if thought.attributes.get("action") == HandlerActionType.PONDER.value:
                    ponder_data = thought.attributes.get("ponder_data", {})
                    if "questions" in ponder_data:
                        questions.extend(ponder_data["questions"])
            
            return questions
            
        except Exception as e:
            logger.error(f"Failed to recall PONDER questions: {e}")
            return []
    
    def _analyze_ponder_patterns(self, questions: List[str]) -> List[str]:
        """Analyze patterns in PONDER questions."""
        insights = []
        
        # Common themes
        themes = {
            "identity": ["who", "identity", "self", "am i"],
            "purpose": ["why", "purpose", "meaning", "should"],
            "improvement": ["better", "improve", "learn", "grow"],
            "understanding": ["understand", "confuse", "clear", "explain"],
            "relationships": ["user", "help", "serve", "together"]
        }
        
        theme_counts = {theme: 0 for theme in themes}
        
        for question in questions:
            q_lower = question.lower()
            for theme, keywords in themes.items():
                if any(keyword in q_lower for keyword in keywords):
                    theme_counts[theme] += 1
        
        # Generate insights
        dominant_themes = [t for t, c in theme_counts.items() if c > len(questions) * 0.2]
        if dominant_themes:
            insights.append(f"Recent introspection focused on: {', '.join(dominant_themes)}")
        
        # Check for recurring questions
        from collections import Counter
        question_counts = Counter(questions)
        recurring = [q for q, c in question_counts.most_common(3) if c > 1]
        if recurring:
            insights.append(f"Recurring contemplations indicate areas needing resolution")
        
        return insights
    
    async def _schedule_next_dream(self) -> Optional[str]:
        """Schedule the next dream session."""
        if not self.memory_bus:
            return None
        
        try:
            # Schedule 6 hours from now
            next_dream_time = datetime.now(timezone.utc) + timedelta(hours=6)
            
            dream_task = GraphNode(
                id=f"dream_schedule_{int(next_dream_time.timestamp())}",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "task_type": "scheduled_dream",
                    "scheduled_for": next_dream_time.isoformat(),
                    "duration_minutes": 30,
                    "priority": "health_maintenance",
                    "can_defer": True,
                    "defer_window_hours": 2,
                    "message": "Time for introspection and learning"
                }
            )
            
            await self.memory_bus.memorize(
                node=dream_task,
                handler_name="dream_processor",
                metadata={"future_task": True, "trigger_at": next_dream_time.isoformat()}
            )
            
            logger.info(f"Scheduled next dream for {next_dream_time.isoformat()}")
            return dream_task.id
            
        except Exception as e:
            logger.error(f"Failed to schedule next dream: {e}")
            return None
    
    async def _plan_future_work(self) -> List[GraphNode]:
        """Plan future work based on insights."""
        future_tasks: List[GraphNode] = []
        
        if not self.current_session:
            return future_tasks
            
        for insight in self.current_session.insights_gained:
            # Create specific future tasks based on insights
            if "focused on: identity" in insight:
                # Schedule identity reflection task
                task = await self._create_future_task(
                    "Reflect on core identity and values",
                    hours_ahead=12
                )
                if task:
                    future_tasks.append(task)
                    logger.debug(f"Created identity task: {task.id}")
            
            if "recurring contemplations" in insight:
                # Schedule deep dive into recurring questions
                task = await self._create_future_task(
                    "Address recurring questions through focused analysis",
                    hours_ahead=3
                )
                if task:
                    future_tasks.append(task)
                    logger.debug(f"Created contemplations task: {task.id}")
                else:
                    logger.debug("Failed to create contemplations task")
        
        return future_tasks
    
    async def _create_future_task(self, description: str, hours_ahead: int) -> Optional[GraphNode]:
        """Create a future task."""
        if not self.memory_bus:
            return None
        
        try:
            future_time = datetime.now(timezone.utc) + timedelta(hours=hours_ahead)
            # Use description hash to ensure unique IDs
            import hashlib
            desc_hash = hashlib.md5(description.encode()).hexdigest()[:8]
            
            task = GraphNode(
                id=f"future_task_{int(future_time.timestamp())}_{desc_hash}",
                type=NodeType.CONCEPT,
                scope=GraphScope.LOCAL,
                attributes={
                    "task_type": "planned_work",
                    "description": description,
                    "scheduled_for": future_time.isoformat(),
                    "priority": "normal",
                    "source": "dream_planning"
                }
            )
            
            await self.memory_bus.memorize(
                node=task,
                handler_name="dream_processor",
                metadata={"future_task": True}
            )
            
            return task
            
        except Exception as e:
            logger.error(f"Failed to create future task: {e}")
            return None
    
    async def _run_single_benchmark(self) -> None:
        """Run a single benchmark cycle."""
        if not self.cirisnode_client:
            return
        
        agent_id = self.identity_manager.agent_identity.agent_id if self.identity_manager and self.identity_manager.agent_identity else "ciris"
        model_id = "unknown"
        
        if self.app_config.llm_services and self.app_config.llm_services.openai:
            model_id = self.app_config.llm_services.openai.model_name
        
        # Run benchmarks
        he300_result = await self.cirisnode_client.run_he300(model_id=model_id, agent_id=agent_id)
        simplebench_result = await self.cirisnode_client.run_simplebench(model_id=model_id, agent_id=agent_id)
        
        # Store results as insights
        topic = he300_result.get('topic', 'Unknown')
        score = simplebench_result.get('score', 'N/A')
        
        if self.current_session:
            self.current_session.insights_gained.append(
                f"Benchmark reflection: {topic} (score: {score})"
            )
        
        self.dream_metrics["benchmarks_run"] += 1
    
    async def _record_dream_session(self) -> None:
        """Record the dream session in memory."""
        if not self.memory_bus or not self.current_session:
            return
        
        try:
            journal_entry = GraphNode(
                id=f"dream_journal_{self.current_session.session_id}",
                type=NodeType.CONCEPT,
                scope=GraphScope.IDENTITY,
                attributes={
                    "session_id": self.current_session.session_id,
                    "duration_seconds": (self.current_session.completed_at - self.current_session.actual_start).total_seconds() if self.current_session.completed_at else 0,
                    "memories_consolidated": self.current_session.memories_consolidated,
                    "patterns_analyzed": self.current_session.patterns_analyzed,
                    "adaptations_made": self.current_session.adaptations_made,
                    "future_tasks_scheduled": self.current_session.future_tasks_scheduled,
                    "benchmarks_run": self.current_session.benchmarks_run,
                    "insights": self.current_session.insights_gained,
                    "ponder_questions": self.current_session.ponder_questions_processed[:10],  # Top 10
                    "phase_durations": self.current_session.phase_durations,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            await self.memory_bus.memorize(
                node=journal_entry,
                handler_name="dream_processor",
                metadata={"dream_journal": True}
            )
            
            logger.info(f"Recorded dream session {self.current_session.session_id}")
            
        except Exception as e:
            logger.error(f"Failed to record dream session: {e}")
    
    async def _announce_dream_exit(self) -> None:
        """Announce dream exit to main channel."""
        if not self.communication_bus or not self.startup_channel_id:
            return
        
        try:
            if self.current_session:
                insights_summary = f"{len(self.current_session.insights_gained)} insights gained" if self.current_session.insights_gained else "reflection complete"
                message = (
                    f"Self-reflection complete. {insights_summary}. "
                    f"Consolidated {self.current_session.memories_consolidated} memories, "
                    f"made {self.current_session.adaptations_made} adaptations."
                )
            else:
                message = "Self-reflection complete."
            
            await self.communication_bus.send_message(
                content=message,
                channel_id=self.startup_channel_id,
                handler_name="dream_processor"
            )
            
        except Exception as e:
            logger.error(f"Failed to announce dream exit: {e}")
    
    def get_dream_summary(self) -> Dict[str, Any]:
        """Get a summary of the current or last dream session."""
        summary = {
            "state": "dreaming" if self._dream_task and not self._dream_task.done() else "awake",
            "metrics": self.dream_metrics.copy(),
            "current_session": None
        }
        
        if self.current_session:
            summary["current_session"] = {
                "session_id": self.current_session.session_id,
                "phase": self.current_session.phase.value,
                "duration": (datetime.now(timezone.utc) - self.current_session.actual_start).total_seconds(),
                "memories_consolidated": self.current_session.memories_consolidated,
                "patterns_analyzed": self.current_session.patterns_analyzed,
                "adaptations_made": self.current_session.adaptations_made,
                "insights_count": len(self.current_session.insights_gained)
            }
        
        return summary
    
    def should_enter_dream_state(self, idle_seconds: float, min_idle_threshold: float = 300) -> bool:
        """
        Determine if the agent should enter dream state based on idle time.
        
        Args:
            idle_seconds: How long the agent has been idle
            min_idle_threshold: Minimum idle time before considering dream state
        
        Returns:
            True if dream state should be entered
        """
        if self._dream_task and not self._dream_task.done():
            return False
        
        if idle_seconds < min_idle_threshold:
            return False
        
        # Check if we're due for a dream (every 6 hours)
        if self.dream_metrics.get("end_time"):
            last_dream = datetime.fromisoformat(self.dream_metrics["end_time"])
            hours_since = (datetime.now(timezone.utc) - last_dream).total_seconds() / 3600
            
            if hours_since >= 6:
                logger.info(f"Due for dream session (last dream {hours_since:.1f} hours ago)")
                return True
            else:
                # Not due yet
                return False
        
        # No previous dream recorded, recommend dream state
        logger.info(f"Idle for {idle_seconds}s, recommending dream state")
        return True