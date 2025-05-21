import sys
from pathlib import Path
import pytest # Import pytest for potential future fixture use
import os

# Ensure OpenAI client can initialize during tests
os.environ.setdefault("OPENAI_API_KEY", "test")

# Add the project root directory (parent of 'tests' directory) to sys.path
# This ensures that the 'ciris_engine' package can be imported by tests.
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# Note: The pytest.ini with `pythonpath = .` should ideally handle this.
# This conftest.py modification is an alternative or supplementary way.
# If both are present, this sys.path.insert might take precedence or be redundant
# depending on pytest's internal order of operations.


@pytest.fixture
def mocker():
    """Lightweight substitute for the pytest-mock fixture."""
    from unittest.mock import patch, MagicMock as _MagicMock, AsyncMock as _AsyncMock

    patches = []

    class _PatchProxy:
        def __call__(self, target, *args, **kwargs):
            p = patch(target, *args, **kwargs)
            patches.append(p)
            return p.start()

        def object(self, target, attribute, *args, **kwargs):
            p = patch.object(target, attribute, *args, **kwargs)
            patches.append(p)
            return p.start()

        def dict(self, in_dict, values, **kwargs):
            p = patch.dict(in_dict, values, **kwargs)
            patches.append(p)
            return p.start()

    class Mocker:
        MagicMock = _MagicMock
        AsyncMock = _AsyncMock

        def __init__(self):
            self.patch = _PatchProxy()

    m = Mocker()
    yield m
    for p in patches:
        p.stop()
