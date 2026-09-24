"""Case memory. Local file until TigerGraph is configured. written_to_graph stays false on the local file."""

from __future__ import annotations

import json
from pathlib import Path

from memory.private.tigergraph import GraphWriteError, upsert_and_read
from memory.public.keys import tigergraph


def _store_path() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent / "runs" / "memory.json"
    raise FileNotFoundError("repo root")


def same_case(written: dict, read: dict) -> bool:
    if read is None:
        return False
    try:
        exposure = round(float(read.get("exposure")), 2)
    except (TypeError, ValueError):
        return False
    return read.get("verdict") == written["verdict"] and exposure == round(float(written["exposure"]), 2)


def _record(case_id: str, answer: dict, card_id: str, device: str) -> dict:
    case = answer["case"]
    return {
        "verdict": case["verdict"],
        "exposure": round(float(case["exposure_usd"]), 2),
        "pattern": case["pattern"],
        "actions": [a["action"] for a in answer["next_best_actions"]["final"]],
        "sar_file": bool(answer["sar"] and answer["sar"].get("file")),
        "card_id": card_id,
        "device": device,
    }


def _load() -> dict:
    path = _store_path()
    if not path.exists():
        return {}
    return json.loads(path.read_text())


def _write(store: dict) -> None:
    path = _store_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(store, indent=2))


def _read(case_id: str) -> dict | None:
    return _load().get(f"EXAM-{case_id}")


def _outcome(verdict: str) -> str:
    if verdict == "fraud":
        return "confirmed_fraud"
    if verdict == "legitimate":
        return "cleared"
    return "uncertain"


def recall(card_id: str, device: str) -> list[dict]:
    """Exam vertices already read back, on this card or this device."""
    found = []
    for key, row in _load().items():
        if not key.startswith("EXAM-"):
            continue
        same_card = bool(card_id) and row.get("card_id") == card_id
        same_device = bool(device) and row.get("device") == device and row.get("card_id") != card_id
        if not same_card and not same_device:
            continue
        found.append(
            {
                "case_id": key,
                "pattern": row.get("pattern") or "none",
                "outcome": _outcome(row.get("verdict") or ""),
                "actions": ", ".join(row.get("actions") or []),
                "notes": "Earlier exam case, read back from memory.",
                "same_card": same_card,
                "same_device": same_device,
            }
        )
    return found


def write_and_read(case_id: str, answer: dict, *, card_id: str = "", device: str = "") -> dict:
    record = _record(case_id, answer, card_id, device)
    key = f"EXAM-{case_id}"
    cfg = tigergraph()
    if cfg is not None:
        try:
            got = upsert_and_read(cfg, case_id, record)
        except GraphWriteError:
            got = None
        matched = same_case(record, got or {})
        return {"graph_case_id": key, "matched": matched, "written_to_graph": matched}
    store = _load()
    store[key] = record
    _write(store)
    matched = same_case(record, _read(case_id) or {})
    return {"graph_case_id": key, "matched": matched, "written_to_graph": False}
