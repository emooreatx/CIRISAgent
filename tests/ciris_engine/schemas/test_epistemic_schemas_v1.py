from ciris_engine.schemas.faculty_schemas_v1 import EntropyResult, CoherenceResult

def test_entropy_result():
    res = EntropyResult(faculty_name="entropy", entropy=0.5)
    assert res.entropy == 0.5
    assert res.faculty_name == "entropy"

def test_coherence_result():
    res = CoherenceResult(faculty_name="coherence", coherence=0.8)
    assert res.coherence == 0.8
    assert res.faculty_name == "coherence"
