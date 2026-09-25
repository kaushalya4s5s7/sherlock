"""HTTP only. Routes validate, call the harness, and return JSON."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from graph import load_index
from harness import progress, resume, run, saved, saved_verdicts


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent
    raise FileNotFoundError("HHGOA_IEEE 2 dataset directory")


ROOT = _repo()
CASES = ROOT / "cases"


def _load_env(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        name, value = stripped.split("=", 1)
        name = name.strip()
        if name and name not in os.environ:
            os.environ[name] = value.strip().strip('"').strip("'")


_load_env(ROOT / ".env")
if (ROOT / ".cache" / "queries_installed").is_file():
    os.environ["TG_INSTALLED_QUERIES"] = "1"

def _start_mcp() -> None:
    if os.environ.get("TG_MCP_URL"):
        return
    from graph.private.official_mcp import spawn

    if spawn(9012):
        return
    from graph.private.mcp_server import serve

    server = serve(9011)
    import threading

    threading.Thread(target=server.serve_forever, daemon=True).start()
    os.environ["TG_MCP_URL"] = "http://127.0.0.1:9011/mcp"


_start_mcp()

from control.public.keys import jev as _jev_config
from language.public.keys import model as _language_model

_control = _jev_config()
_language = _language_model()
print(f"control: jev {_control['version']}" if _control else "control: fallback", flush=True)
print(f"language: {_language['name']}" if _language else "language: fallback", flush=True)

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
        "graph": (
            f"TigerGraph {os.environ['TG_GRAPH']} installed queries, policy vectors, and ExamCase write-back. The agent calls them through MCP."
            if (ROOT / ".cache" / "queries_installed").is_file()
            and os.environ.get("TG_HOST")
            and os.environ.get("TG_GRAPH")
            and os.environ.get("TG_TOKEN")
            else (
                f"TigerGraph {os.environ['TG_GRAPH']} for case write-back; measurements from the local index"
                if os.environ.get("TG_HOST") and os.environ.get("TG_GRAPH") and os.environ.get("TG_TOKEN")
                else "local index — TigerGraph write-back switches on when the cluster env is set"
            )
        ),
        "built_at": idx.built_at,
    }


@app.get("/api/cases")
def list_cases():
    idx = graph_index()
    remembered = saved_verdicts()
    rows = []
    for case in idx.pack:
        ran = RUNS.get(case["case_id"])
        verdict = ran["answer"]["case"]["verdict"] if ran else remembered.get(case["case_id"])
        rows.append(
            {
                "case_id": case["case_id"],
                "customer_id": case["customer_id"],
                "card_id": case["card_id"],
                "trigger_type": case["trigger_type"],
                "risk_score": case["risk_score"],
                "trigger_text": case.get("trigger_text") or "",
                "ran": verdict is not None,
                "decision": verdict,
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


@app.get("/api/cases/{case_id}/progress")
def case_progress(case_id: str):
    return progress(case_id)


@app.get("/api/closed/{case_id}")
def get_closed(case_id: str):
    idx = graph_index()
    found = next((item for item in idx.closed if item.case_id == case_id), None)
    if found is None:
        raise HTTPException(404, "unknown closed case")
    return {
        "case_id": found.case_id,
        "customer_id": found.customer_id,
        "card_id": found.card_id,
        "outcome": found.outcome,
        "pattern": found.pattern,
        "txn_ids": found.txn_ids,
        "connected": found.connected,
        "exposure_usd": found.exposure,
        "actions": [part for part in found.actions.split("|") if part],
        "notes": found.notes,
    }


@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    if case_id not in RUNS:
        found = saved(case_id)
        if found is None:
            raise HTTPException(404, "not run yet")
        RUNS[case_id] = found
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
