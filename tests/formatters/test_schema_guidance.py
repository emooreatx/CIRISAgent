from ciris_engine.formatters.schema_guidance import format_schema_guidance


def test_format_schema_guidance():
    schema = "{\"a\": \"b\"}"
    block = format_schema_guidance(schema)
    assert "Structured Output Guidance" in block
    assert schema in block
