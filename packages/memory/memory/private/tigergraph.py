"""Upsert one ExamCase vertex and read it back. Used only when TigerGraph is configured."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class GraphWriteError(RuntimeError):
    pass


def _request(cfg: dict, path: str, payload: dict | None = None) -> dict:
    data = None if payload is None else json.dumps(payload).encode()
    request = Request(
        f"{cfg['host']}/restpp/graph/{cfg['graph']}{path}",
        data=data,
        headers={"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"},
        method="POST" if payload is not None else "GET",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read().decode() or "{}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise GraphWriteError(str(exc)) from exc


def upsert_and_read(cfg: dict, case_id: str, record: dict) -> dict:
    vertex = f"EXAM-{case_id}"
    attributes = {
        "verdict": {"value": record["verdict"]},
        "exposure_usd": {"value": record["exposure"]},
        "pattern": {"value": record["pattern"]},
    }
    body: dict = {"vertices": {"ExamCase": {vertex: attributes}}}
    if record.get("card_id"):
        body["edges"] = {
            "ExamCase": {
                vertex: {
                    "ON_CARD": {"Card": {record["card_id"]: {}}},
                }
            }
        }
    _request(cfg, "", body)
    loaded = _request(cfg, f"/vertices/ExamCase/{vertex}")
    attrs = {}
    results = loaded.get("results") or []
    if results:
        attrs = results[0].get("attributes") or {}
    return {
        "verdict": attrs.get("verdict"),
        "exposure": attrs.get("exposure_usd"),
    }
