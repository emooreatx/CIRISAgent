"""CIRIS Agent service and subsystem protocols."""

from typing import Any, TYPE_CHECKING

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
if TYPE_CHECKING:
    from .dma_interface import (
        BaseDMAInterface as _BaseDMAInterface,
        EthicalDMAInterface as _EthicalDMAInterface,
        CSDMAInterface as _CSDMAInterface, 
        DSDMAInterface as _DSDMAInterface,
        ActionSelectionDMAInterface as _ActionSelectionDMAInterface,
    )
    from .telemetry_interface import (
        TelemetryInterface as _TelemetryInterface,
        ProcessorControlInterface as _ProcessorControlInterface,
        TelemetrySnapshot as _TelemetrySnapshot,
        AdapterInfo as _AdapterInfo,
        ServiceInfo as _ServiceInfo,
        ProcessorState as _ProcessorState,
        ConfigurationSnapshot as _ConfigurationSnapshot,
    )
else:
    try:
        from .dma_interface import (
            BaseDMAInterface as _BaseDMAInterface,
            EthicalDMAInterface as _EthicalDMAInterface,
            CSDMAInterface as _CSDMAInterface, 
            DSDMAInterface as _DSDMAInterface,
            ActionSelectionDMAInterface as _ActionSelectionDMAInterface,
        )
    except ImportError:
        # Define dummy values to prevent import errors during initialization
        _BaseDMAInterface = Any
        _EthicalDMAInterface = Any
        _CSDMAInterface = Any
        _DSDMAInterface = Any
        _ActionSelectionDMAInterface = Any

    try:
        from .telemetry_interface import (
            TelemetryInterface as _TelemetryInterface,
            ProcessorControlInterface as _ProcessorControlInterface,
            TelemetrySnapshot as _TelemetrySnapshot,
            AdapterInfo as _AdapterInfo,
            ServiceInfo as _ServiceInfo,
            ProcessorState as _ProcessorState,
            ConfigurationSnapshot as _ConfigurationSnapshot,
        )
    except ImportError:
        # Define dummy values to prevent import errors during initialization
        _TelemetryInterface = Any
        _ProcessorControlInterface = Any
        _TelemetrySnapshot = Any
        _AdapterInfo = Any
        _ServiceInfo = Any
        _ProcessorState = Any
        _ConfigurationSnapshot = Any

# Re-export with original names
BaseDMAInterface = _BaseDMAInterface
EthicalDMAInterface = _EthicalDMAInterface
CSDMAInterface = _CSDMAInterface
DSDMAInterface = _DSDMAInterface
ActionSelectionDMAInterface = _ActionSelectionDMAInterface
TelemetryInterface = _TelemetryInterface
ProcessorControlInterface = _ProcessorControlInterface
TelemetrySnapshot = _TelemetrySnapshot
AdapterInfo = _AdapterInfo
ServiceInfo = _ServiceInfo
ProcessorState = _ProcessorState
ConfigurationSnapshot = _ConfigurationSnapshot

from .guardrail_interface import GuardrailInterface
from .persistence_interface import PersistenceInterface
from .secrets_interface import (
    SecretsFilterInterface,
    SecretsStoreInterface,
    SecretsServiceInterface,
    SecretsEncryptionInterface
)

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
