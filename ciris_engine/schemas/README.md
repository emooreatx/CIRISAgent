# schemas

This module contains the pydantic schemas used throughout the CIRIS Engine.
All schemas inherit from `BaseModel`, and many now extend `VersionedSchema`
which adds a `schema_version` field. The `SchemaRegistry` provides a central
mapping of schema names to classes and exposes `validate_schema` for
runtime validation.
