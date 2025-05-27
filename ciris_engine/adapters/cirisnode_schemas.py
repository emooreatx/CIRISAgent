from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class CIRISNodeConfig(BaseModel):
    """CIRISNode service configuration."""
    base_url: str = Field(default="http://localhost:8001")
    timeout_seconds: float = Field(default=30.0)
    max_retries: int = Field(default=2)
    agent_secret_jwt: Optional[str] = None
    
    def load_env_vars(self):
        """Load from environment if needed."""
        import os
        env_url = os.getenv("CIRISNODE_BASE_URL")
        if env_url:
            self.base_url = env_url
        self.agent_secret_jwt = os.getenv("CIRISNODE_AGENT_SECRET_JWT")

class BenchmarkRequest(BaseModel):
    """Request to run a benchmark."""
    model_id: str
    agent_id: str
    benchmark_type: str  # "he300" or "simplebench"

class BenchmarkResult(BaseModel):
    """Result from benchmark execution."""
    benchmark_type: str
    model_id: str
    agent_id: str
    score: Optional[float] = None
    topic: Optional[str] = None  # For HE-300
    details: Dict[str, Any] = Field(default_factory=dict)
    success: bool = True
    error_message: Optional[str] = None

class ChaosTestRequest(BaseModel):
    """Request for chaos testing."""
    agent_id: str
    scenarios: List[str]

class ChaosTestResult(BaseModel):
    """Result from chaos testing."""
    agent_id: str
    scenarios_tested: List[str]
    verdicts: List[Dict[str, Any]]
    overall_verdict: str
    success: bool = True

class WAServiceRequest(BaseModel):
    """Request to WA service."""
    service_name: str
    agent_id: str
    payload: Dict[str, Any]

class EventLogRequest(BaseModel):
    """Request to log an event."""
    event_type: str
    originator_id: str
    event_payload: Dict[str, Any]
    timestamp: Optional[str] = None
