from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult

def test_entropy_result():
    res = EntropyResult(entropy=0.5)
    assert res.entropy == 0.5

def test_coherence_result():
    res = CoherenceResult(coherence=0.8)
    assert res.coherence == 0.8
