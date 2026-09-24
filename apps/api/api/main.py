"""HTTP only. Routes validate, call the harness, and return JSON."""

from __future__ import annotations

import json
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from graph import load_index
from harness import resume, run


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent
    raise FileNotFoundError("HHGOA_IEEE 2 dataset directory")


ROOT = _repo()
CASES = ROOT / "cases"

app = FastAPI(title="HHGOA Case Desk")
INDEX = None
RUNS: dict[str, dict] = {}


def graph_index():
    global INDEX
    if INDEX is None:
        INDEX = load_index()
    return INDEX


@app.get("/api/health")
def health():
    idx = graph_index()
    return {
        "ok": True,
        "transactions": len(idx.txns),
        "closed_cases": len(idx.closed),
        "graph": "local index — TigerGraph write-back switches on when the cluster env is set",
        "built_at": idx.built_at,
    }


@app.get("/api/cases")
def list_cases():
    idx = graph_index()
    rows = []
    for case in idx.pack:
        ran = RUNS.get(case["case_id"])
        rows.append(
            {
                "case_id": case["case_id"],
                "customer_id": case["customer_id"],
                "card_id": case["card_id"],
                "trigger_type": case["trigger_type"],
                "risk_score": case["risk_score"],
                "trigger_text": case.get("trigger_text") or "",
                "ran": ran is not None,
                "decision": ran["answer"]["case"]["verdict"] if ran else None,
            }
        )
    return {"cases": rows}


@app.post("/api/cases/{case_id}/run")
def run_case(case_id: str):
    idx = graph_index()
    case = next((c for c in idx.pack if c["case_id"] == case_id), None)
    if not case:
        raise HTTPException(404, "unknown case")
    started = time.perf_counter()
    result = run(case, idx)
    result["answer"]["latency_s"] = round(time.perf_counter() - started, 3)
    if result["demo"].get("memory_matched") is False:
        raise HTTPException(500, "case memory read-back did not match the write")
    result["demo"].setdefault("approved", [])
    _write_case(result)
    RUNS[case_id] = result
    return result


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    if case_id not in RUNS:
        raise HTTPException(404, "not run yet")
    return RUNS[case_id]


def _write_case(result: dict) -> None:
    CASES.mkdir(parents=True, exist_ok=True)
    (CASES / f"{result['answer']['case_id']}.json").write_text(json.dumps(result["answer"], indent=2))


@app.post("/api/cases/{case_id}/approve")
async def approve(case_id: str, request: Request):
    body = await request.json()
    action = body.get("action")
    try:
        result = resume(case_id, graph_index(), action=action)
    except KeyError:
        raise HTTPException(404, "not run yet") from None
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from None
    if result["demo"].get("memory_matched") is False:
        raise HTTPException(500, "case memory read-back did not match the write")
    _write_case(result)
    RUNS[case_id] = result
    return {"approved": result["demo"].get("approved") or [], "approval": result["demo"]["approval"]}


@app.get("/")
def home():
    return {"service": "HHGOA case desk", "health": "/api/health", "cases": "/api/cases"}
