import pytest

from ciris_engine.registries.base import ServiceRegistry
from ciris_engine.faculties import EntropyFaculty, CoherenceFaculty, FacultyManager
from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult

class DummyLLM:
    def __init__(self, data):
        self.data = data

    async def call_llm_structured(self, messages, response_model, **kwargs):
        from ciris_engine.schemas.foundational_schemas_v1 import ResourceUsage
        
        # Create response instance from the data
        response_instance = response_model(**self.data)
        
        # Mock resource usage
        resource_usage = ResourceUsage(
            prompt_tokens=10,
            completion_tokens=5,
            total_tokens=None,
            cost_usd=0.001
        )
        
        return response_instance, resource_usage

@pytest.mark.asyncio
async def test_entropy_faculty_evaluate():
    registry = ServiceRegistry()
    llm = DummyLLM({"entropy": 0.42, "faculty_name": "entropy"})
    registry.register("EntropyFaculty", "llm", llm)
    faculty = EntropyFaculty(registry)
    result = await faculty.evaluate("hello")
    assert isinstance(result, EntropyResult)
    assert result.entropy == 0.42

@pytest.mark.asyncio
async def test_faculty_manager_runs_all():
    registry = ServiceRegistry()
    registry.register("EntropyFaculty", "llm", DummyLLM({"entropy": 0.1, "faculty_name": "entropy"}))
    registry.register("CoherenceFaculty", "llm", DummyLLM({"coherence": 0.9, "faculty_name": "coherence"}))

    manager = FacultyManager(registry)
    manager.register_faculty("entropy", EntropyFaculty(registry))
    manager.register_faculty("coherence", CoherenceFaculty(registry))

    results = await manager.run_all_faculties("test")
    assert isinstance(results["entropy"], EntropyResult)
    assert isinstance(results["coherence"], CoherenceResult)
