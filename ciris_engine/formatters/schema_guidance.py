"""Utilities for structured output guidance blocks."""


def format_schema_guidance(schema: str) -> str:
    """Return a schema guidance block for prompts."""
    if not schema:
        return ""
    schema = schema.strip()
    return f"=== Structured Output Guidance ===\n{schema}"

__all__ = ["format_schema_guidance"]
