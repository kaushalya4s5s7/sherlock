"""Case memory. A local file stands in until TigerGraph read-back is wired."""

from __future__ import annotations

import json
from pathlib import Path


def _store_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent / "runs" / "memory.json"
    raise FileNotFoundError("repo root")


def write_and_read(case_id: str, answer: dict) -> bool:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    store = json.loads(path.read_text()) if path.exists() else {}
    key = f"EXAM-{case_id}"
    store[key] = {
        "decision": answer["case"]["verdict"],
        "pattern": answer["case"]["pattern"],
        "fraud_probability": answer["case"]["fraud_probability"],
        "actions": [a["action"] for a in answer["next_best_actions"]["final"]],
        "sar_file": bool(answer["sar"] and answer["sar"].get("file")),
    }
    path.write_text(json.dumps(store, indent=2))
    got = json.loads(path.read_text()).get(key)
    return got == store[key]
