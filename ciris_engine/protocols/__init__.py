"""CIRIS Agent service and subsystem protocols."""

from .services import (
    CommunicationService,
    WiseAuthorityService,
    MemoryService,
    ToolService,
    AuditService,
    LLMService,
    NetworkService,
    CommunityService,
)
from .processor_interface import ProcessorInterface
# Import DMA interfaces conditionally to avoid circular imports
try:
    from .dma_interface import (
        BaseDMAInterface,
        EthicalDMAInterface,
        CSDMAInterface, 
        DSDMAInterface,
        ActionSelectionDMAInterface,
    )
except ImportError:
    # Define dummy classes to prevent import errors during initialization
    BaseDMAInterface = None
    EthicalDMAInterface = None
    CSDMAInterface = None
    DSDMAInterface = None
    ActionSelectionDMAInterface = None
from .guardrail_interface import GuardrailInterface
from .persistence_interface import PersistenceInterface
from .secrets_interface import (
    SecretsFilterInterface,
    SecretsStoreInterface,
    SecretsServiceInterface,
    SecretsEncryptionInterface
)

# Import telemetry interfaces
try:
    from .telemetry_interface import (
        TelemetryInterface,
        ProcessorControlInterface,
        TelemetrySnapshot,
        AdapterInfo,
        ServiceInfo,
        ProcessorState,
        ConfigurationSnapshot,
    )
except ImportError:
    # Define dummy classes to prevent import errors during initialization
    TelemetryInterface = None
    ProcessorControlInterface = None
    TelemetrySnapshot = None
    AdapterInfo = None
    ServiceInfo = None
    ProcessorState = None
    ConfigurationSnapshot = None

__all__ = [
    "CommunicationService",
    "WiseAuthorityService",
    "MemoryService",
    "ToolService",
    "AuditService",
    "LLMService",
    "NetworkService",
    "CommunityService",
    "ProcessorInterface",
    "BaseDMAInterface",
    "EthicalDMAInterface", 
    "CSDMAInterface",
    "DSDMAInterface",
    "ActionSelectionDMAInterface",
    "GuardrailInterface",
    "PersistenceInterface",
    "SecretsFilterInterface",
    "SecretsStoreInterface",
    "SecretsServiceInterface",
    "SecretsEncryptionInterface",
    "TelemetryInterface",
    "ProcessorControlInterface",
    "TelemetrySnapshot",
    "AdapterInfo",
    "ServiceInfo",
    "ProcessorState",
    "ConfigurationSnapshot",
]
