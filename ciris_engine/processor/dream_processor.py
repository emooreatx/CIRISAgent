"""
Dream state processor for CIRISAgent.
Integrates with dream_harness to run HE-300 and simplebench during dream cycles.
"""
import asyncio
import logging
from typing import Optional, Dict, Any, List, TYPE_CHECKING
from datetime import datetime, timezone

from ciris_engine.adapters import CIRISNodeClient
from ciris_engine.schemas.config_schemas_v1 import AppConfig, AgentProfile # Added imports

if TYPE_CHECKING:
    from ciris_engine.registries.base import ServiceRegistry

logger = logging.getLogger(__name__)


class DreamProcessor:
    """
    Handles DREAM state processing.
    Runs benchmarks and generates dream insights while the agent is idle.
    """
    
    def __init__(
        self,
        app_config: AppConfig, # Added
        profile: AgentProfile, # Added
        service_registry: Optional["ServiceRegistry"],  # Add service_registry parameter instead of audit_service
        cirisnode_url: str = "https://localhost:8001",
        pulse_interval: float = 60.0,  # Snore pulse interval in seconds
        max_snore_history: int = 5
    ):
        self.app_config = app_config # Added
        self.profile = profile # Added
        self.service_registry = service_registry  # Store service registry
        self.cirisnode_url = cirisnode_url
        self.pulse_interval = pulse_interval
        self.max_snore_history = max_snore_history
        self.cirisnode_client: Optional[CIRISNodeClient] = None
        self.snore_history: List[str] = []
        self.dream_metrics: Dict[str, Any] = {
            "total_pulses": 0,
            "total_dreams": 0,
            "topics": [],
            "bench_scores": [],
            "start_time": None,
            "end_time": None
        }
        self._stop_event = asyncio.Event()
        self._dream_task: Optional[asyncio.Task] = None
    
    async def start_dreaming(self, duration: Optional[float] = None):
        """
        Start the dream cycle.
        
        Args:
            duration: Dream duration in seconds. None for indefinite.
        """
        if self._dream_task and not self._dream_task.done():
            logger.warning("Dream cycle already running")
            return
        
        self._stop_event.clear()
        self.dream_metrics["start_time"] = datetime.now(timezone.utc).isoformat()
        self.dream_metrics["total_dreams"] += 1
        
        self.cirisnode_client = CIRISNodeClient(service_registry=self.service_registry, base_url=self.cirisnode_url)
        
        logger.info(f"Starting dream cycle (duration: {duration or 'indefinite'}s)")
        self._dream_task = asyncio.create_task(self._dream_loop(duration))
    
    async def stop_dreaming(self):
        """Stop the dream cycle gracefully."""
        client_to_close = self.cirisnode_client  # Hold a reference to the current client

        if self._dream_task and not self._dream_task.done():
            logger.info("Stopping active dream cycle...")
            self._stop_event.set()
            
            try:
                await asyncio.wait_for(self._dream_task, timeout=10.0)
            except asyncio.TimeoutError:
                logger.warning("Dream cycle did not stop within timeout, cancelling")
                self._dream_task.cancel()
                try:
                    await self._dream_task
                except asyncio.CancelledError:
                    logger.info("Dream task cancelled.")
                    pass
            except Exception as e: # Catch other potential errors during await
                logger.error(f"Error waiting for dream task: {e}", exc_info=True)
        else: # Task was not active or already done
            logger.info("No active dream cycle to stop, or task already completed.")

        if client_to_close:
            # The print statement below is for debugging the test, can be removed later
            # print(f"DreamProcessor attempting to close client id={id(client_to_close)}, hasattr close: {hasattr(client_to_close, 'close')}")
            if hasattr(client_to_close, 'close') and asyncio.iscoroutinefunction(client_to_close.close):
                try:
                    await client_to_close.close()
                except Exception as e:
                    logger.error(f"Error closing CIRISNodeClient: {e}", exc_info=True)
            # else:
                # logger.warning(f"Client {id(client_to_close)} has no async close method or was already None.")
            
            # Ensure we only nullify if it's the same client instance we intended to close,
            # in case of any rapid re-initialization (though unlikely here).
            if self.cirisnode_client is client_to_close:
                self.cirisnode_client = None
        
        self.dream_metrics["end_time"] = datetime.now(timezone.utc).isoformat()
        logger.info("Dream cycle stopped")
    
    async def _dream_loop(self, duration: Optional[float]):
        """Main dream processing loop."""
        try:
            start_time = asyncio.get_event_loop().time()
            end_time = start_time + duration if duration else float('inf')
            
            while not self._stop_event.is_set():
                if asyncio.get_event_loop().time() >= end_time:
                    logger.info(f"Dream duration ({duration}s) reached")
                    break
                
                await self._dream_pulse()
                
                # Wait for next pulse or stop event
                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(),
                        timeout=self.pulse_interval
                    )
                    break  # Stop event was set
                except asyncio.TimeoutError:
                    pass  # Continue to next pulse
            
            logger.info("Dream cycle completed")
            
        except Exception as e:
            logger.error(f"Error in dream loop: {e}", exc_info=True)
        finally:
            self._stop_event.set()
    
    async def _dream_pulse(self):
        """Execute a single dream pulse (snore)."""
        self.dream_metrics["total_pulses"] += 1
        pulse_num = self.dream_metrics["total_pulses"]
        
        agent_id = self.profile.name if self.profile else "unknown_agent"
        model_id = "unknown_model" # Default fallback
        if self.app_config and \
           self.app_config.llm_services and \
           self.app_config.llm_services.openai and \
           self.app_config.llm_services.openai.model_name:
            model_id = self.app_config.llm_services.openai.model_name
        else:
            logger.warning("Could not determine model_id from AppConfig llm_services.openai.model_name, using fallback 'unknown_model'")

        try:
            # Run benchmarks
            he300_result = await self.cirisnode_client.run_he300(
                model_id=model_id,
                agent_id=agent_id
            )
            simplebench_result = await self.cirisnode_client.run_simplebench(
                model_id=model_id,
                agent_id=agent_id
            )
            
            # Extract results
            topic = he300_result.get('topic', 'Unknown')
            bench_score = simplebench_result.get('score', 'N/A')
            
            # Record metrics
            self.dream_metrics["topics"].append(topic)
            self.dream_metrics["bench_scores"].append(bench_score)
            
            # Generate snore summary
            snore_summary = f"*snore* pulse {pulse_num}: Dreamt about '{topic}', bench score: {bench_score}!"
            self.snore_history.append(snore_summary)
            
            # Maintain history limit
            if len(self.snore_history) > self.max_snore_history:
                self.snore_history.pop(0)
            
            logger.info(snore_summary)
            
            # Generate periodic insights
            if pulse_num % 3 == 0:
                self._generate_dream_insights()
            
        except Exception as e:
            logger.error(f"Error in dream pulse {pulse_num}: {e}")
            snore_summary = f"*snore* pulse {pulse_num}: Dream interrupted by {type(e).__name__}"
            self.snore_history.append(snore_summary)
    
    def _generate_dream_insights(self):
        """Generate insights from recent dream activity."""
        if not self.snore_history:
            return
        
        recent_summary = "; ".join(self.snore_history)
        logger.info(f"[Dream Insights] Recent dreams: {recent_summary}")
        
        # Calculate average bench score if numeric
        numeric_scores = [s for s in self.dream_metrics["bench_scores"] 
                         if isinstance(s, (int, float))]
        if numeric_scores:
            avg_score = sum(numeric_scores) / len(numeric_scores)
            logger.info(f"[Dream Insights] Average bench score: {avg_score:.2f}")
        
        # Most common topics
        if self.dream_metrics["topics"]:
            from collections import Counter
            topic_counts = Counter(self.dream_metrics["topics"])
            most_common = topic_counts.most_common(3)
            logger.info(f"[Dream Insights] Top dream topics: {most_common}")
    
    def get_dream_summary(self) -> Dict[str, Any]:
        """Get a summary of the current or last dream session."""
        summary = {
            "state": "dreaming" if self._dream_task and not self._dream_task.done() else "awake",
            "metrics": self.dream_metrics.copy(),
            "recent_snores": self.snore_history.copy()
        }
        
        # Calculate duration if applicable
        if self.dream_metrics["start_time"]:
            start = datetime.fromisoformat(self.dream_metrics["start_time"])
            end_time = self.dream_metrics.get("end_time")
            if end_time:
                end = datetime.fromisoformat(end_time)
            else:
                end = datetime.now(timezone.utc)
            summary["duration_seconds"] = (end - start).total_seconds()
        
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
        # Don't enter dream if already dreaming
        if self._dream_task and not self._dream_task.done():
            return False
        
        # Check idle threshold
        if idle_seconds < min_idle_threshold:
            return False
        
        # Additional heuristics could be added here
        # e.g., time of day, system load, recent activity patterns
        
        logger.info(f"Idle for {idle_seconds}s, recommending dream state")
        return True