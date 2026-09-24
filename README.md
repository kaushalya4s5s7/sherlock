# Case Desk

A fraud investigation desk for the twenty HHGOA exam cases. Open it, pick a case, and the screen shows the evidence, the probability, every policy rule, and the action before and after the customer is asked.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
PYTHONPATH=packages/graph .venv/bin/python -m graph.private.local_index
PYTHONPATH=packages/contracts:packages/intake:packages/graph:packages/belief:packages/pattern:packages/control:packages/policy:packages/reply:packages/stop:packages/language:packages/memory:packages/answer:packages/harness:apps/api .venv/bin/uvicorn api.main:app --port 8787
```

Then open http://127.0.0.1:8787

The first index build reads the full transaction file once and caches it in `.cache/`. After that the desk starts in seconds.

TigerGraph is not required to demonstrate. The badge on the desk says the history is a local index. `written_to_graph` stays false until a cluster read-back exists. Case files land in `cases/`.

Run the policy tests with:

```bash
.venv/bin/python -m pytest
```
