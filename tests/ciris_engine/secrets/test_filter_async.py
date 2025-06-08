import pytest

from ciris_engine.secrets.filter import SecretsFilter
from ciris_engine.schemas.secrets_schemas_v1 import SecretPattern
from ciris_engine.schemas.foundational_schemas_v1 import SensitivityLevel
from ciris_engine.schemas.secrets_schemas_v1 import SecretsFilterResult

@pytest.mark.asyncio
async def test_filter_content_async():
    f = SecretsFilter()
    text = "API key api_key=sk_test_1234567890123456"
    result = await f.filter_content(text)
    assert isinstance(result, SecretsFilterResult)
    assert result.secrets_found >= 1
    assert "SECRET:" in result.filtered_content

@pytest.mark.asyncio
async def test_add_and_remove_pattern_async():
    f = SecretsFilter()
    pattern = SecretPattern(
        name="test_async",
        regex=r"ID_[0-9]+",
        description="Async pattern",
        sensitivity=SensitivityLevel.LOW,
        context_hint="async",
        enabled=True,
    )
    added = await f.add_pattern(pattern)
    assert added is True
    res = await f.filter_content("see ID_1234")
    assert res.secrets_found == 1
    removed = await f.remove_pattern("test_async")
    assert removed is True
    res2 = await f.filter_content("see ID_1234")
    assert res2.secrets_found == 0

