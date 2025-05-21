# Channel-metadata approval cycle

Channel updates to the agent's graph memory are deferred on the first attempt. The DMA automatically spawns a new thought for the Wise Authority containing the original payload. When that follow-up thought arrives with `is_wa_correction` set and a `corrected_thought_id` referencing the deferred thought, the MemoryHandler applies the update without another deferral.

## Manual persistence verification

Until automated tests cover persistence, you can verify `CIRISLocalGraph` manually:

1. Run a MEMORIZE action.
2. Wait a moment for the background persist thread to finish.
3. Confirm the file timestamp updated and inspect the pickle:

```bash
ls -l memory_graph.pkl
python - <<'PY'
import pickle, networkx as nx, pathlib, pprint
g = pickle.load(pathlib.Path("memory_graph.pkl").open("rb"))
print("Loaded", g.number_of_nodes(), "nodes")
pprint.pprint(dict(g.nodes(data=True))[:3])
PY
```

You should also see a log entry like `Persisted memory graph (...)` indicating a successful write.

## Memory Actions
Every memory action now specifies a `scope` field to target one of three graphs: `local`, `identity`, or `environment`.
Example:
```json
{"action": "REMEMBER", "scope": "environment", "query": "User:1234"}
```

