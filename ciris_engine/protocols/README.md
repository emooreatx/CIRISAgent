# protocols

This module defines abstract interfaces used across the CIRIS engine. 
Implementations should depend on these contracts rather than concrete 
classes from other subpackages.

The directory provides service protocols under `services.py` and 
additional subsystem interfaces such as `ProcessorInterface`, 
`DMAEvaluatorInterface`, `GuardrailInterface`, and 
`PersistenceInterface`. Common Pydantic models are re-exported via 
`schemas.py` for convenience when implementing these protocols.
