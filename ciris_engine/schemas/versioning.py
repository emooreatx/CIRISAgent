from enum import Enum
from pydantic import BaseModel, Field

class SchemaVersion(str, Enum):
    """Track schema versions."""
    V1_0 = "1.0"

class VersionedSchema(BaseModel):
    """Base model with schema version metadata."""
    schema_version: SchemaVersion = Field(default=SchemaVersion.V1_0)
