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


def _edges(record: dict) -> dict:
    edges: dict = {}
    if record.get("card_id"):
        edges["ON_CARD"] = {"BankCard": {record["card_id"]: {}}}
    others = {
        card: {}
        for card in record.get("connected") or []
        if card and card != record.get("card_id")
    }
    if others:
        edges["EXAM_OTHER"] = {"BankCard": others}
    txns = {txn: {} for txn in record.get("txn_ids") or [] if txn}
    if txns:
        edges["EXAM_TXN"] = {"Transaction": txns}
    if record.get("device"):
        edges["EXAM_DEVICE"] = {"DeviceProfile": {record["device"]: {}}}
    return edges


def upsert_and_read(cfg: dict, case_id: str, record: dict) -> dict:
    vertex = f"EXAM-{case_id}"
    attributes = {
        "verdict": {"value": record["verdict"]},
        "exposure_usd": {"value": record["exposure"]},
        "pattern": {"value": record["pattern"]},
    }
    body: dict = {"vertices": {"ExamCase": {vertex: attributes}}}
    edges = _edges(record)
    if edges:
        body["edges"] = {"ExamCase": {vertex: edges}}
    try:
        _request(cfg, "", body)
    except GraphWriteError:
        if not edges:
            raise
        _request(cfg, "", {"vertices": body["vertices"]})
    loaded = _request(cfg, f"/vertices/ExamCase/{vertex}")
    attrs = {}
    results = loaded.get("results") or []
    if results:
        attrs = results[0].get("attributes") or {}
    return {
        "verdict": attrs.get("verdict"),
        "exposure": attrs.get("exposure_usd"),
    }
