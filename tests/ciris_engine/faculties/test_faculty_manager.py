import pytest

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.faculties import EntropyFaculty, CoherenceFaculty, FacultyManager
from ciris_engine.schemas.epistemic_schemas_v1 import EntropyResult, CoherenceResult

class DummyLLM:
    def __init__(self, data):
        self.data = data

    async def generate_structured_response(self, messages, schema, model=None):
        return self.data

@pytest.mark.asyncio
async def test_entropy_faculty_evaluate():
    registry = ServiceRegistry()
    llm = DummyLLM({"entropy": 0.42})
    registry.register("EntropyFaculty", "llm", llm)
    faculty = EntropyFaculty(registry)
    result = await faculty.evaluate("hello")
    assert isinstance(result, EntropyResult)
    assert result.entropy == 0.42

@pytest.mark.asyncio
async def test_faculty_manager_runs_all():
    registry = ServiceRegistry()
    registry.register("EntropyFaculty", "llm", DummyLLM({"entropy": 0.1}))
    registry.register("CoherenceFaculty", "llm", DummyLLM({"coherence": 0.9}))

    manager = FacultyManager(registry)
    manager.register_faculty("entropy", EntropyFaculty(registry))
    manager.register_faculty("coherence", CoherenceFaculty(registry))

    results = await manager.run_all_faculties("test")
    assert isinstance(results["entropy"], EntropyResult)
    assert isinstance(results["coherence"], CoherenceResult)
