"""Run the installed measurement queries. Tests keep the local index."""

from __future__ import annotations

import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from graph.private.local_index import ClosedCase, GraphIndex
from graph.public.keys import tigergraph

PACK = (
    "txn_and_card",
    "card_window",
    "device_profile",
    "device_neighbors",
    "region_history",
    "recurring_match",
    "prior_cases",
    "exposure_episode",
)


def live_ready() -> bool:
    return os.environ.get("TG_INSTALLED_QUERIES") == "1" and tigergraph() is not None


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "gsql").is_dir():
            return parent
    raise FileNotFoundError("gsql directory")


def rest_query(name: str, params: dict[str, str]) -> dict:
    last = ""
    for _attempt in range(2):
        try:
            return _rest_once(name, params)
        except RuntimeError as exc:
            last = str(exc)
    raise RuntimeError(last)


def _rest_once(name: str, params: dict[str, str]) -> dict:
    cfg = tigergraph()
    if cfg is None:
        raise RuntimeError("TigerGraph is not configured")
    query = urlencode(params)
    url = f"{cfg['host']}/restpp/query/{cfg['graph']}/{name}?{query}"
    request = Request(url, headers={"Authorization": f"Bearer {cfg['token']}"})
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode() or "{}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"{name}: {exc}") from exc
    if body.get("error"):
        raise RuntimeError(f"{name}: {body.get('message') or 'query failed'}")
    return body


def rest_post(name: str, payload: dict) -> dict:
    cfg = tigergraph()
    if cfg is None:
        raise RuntimeError("TigerGraph is not configured")
    url = f"{cfg['host']}/restpp/query/{cfg['graph']}/{name}"
    request = Request(
        url,
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {cfg['token']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode() or "{}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"{name}: {exc}") from exc
    if body.get("error"):
        raise RuntimeError(f"{name}: {body.get('message') or 'query failed'}")
    return body


def run_query(name: str, params: dict) -> dict:
    if os.environ.get("TG_MCP_OFFICIAL") == "1":
        from graph.private.official_mcp import call_tool

        try:
            found = call_tool(
                "tigergraph__run_installed_query",
                {"query_name": name, "params": params, "graph_name": "HHGOA"},
            )
            if "results" in found:
                return found
        except (RuntimeError, HTTPError, URLError, TimeoutError, ConnectionError, OSError):
            pass
    mcp = os.environ.get("TG_MCP_URL", "").strip()
    if not mcp or os.environ.get("TG_MCP_OFFICIAL") == "1":
        if isinstance(params, dict) and any(isinstance(value, (list, dict, int, float)) for value in params.values()):
            return rest_post(name, params)
        return rest_query(name, {key: str(value) for key, value in params.items()})
    payload = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {"name": "run_installed_query", "arguments": {"query_name": name, "params": params}},
        }
    ).encode()
    request = Request(mcp, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=60) as response:
            body = json.loads(response.read().decode() or "{}")
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, ConnectionError, OSError) as exc:
        raise RuntimeError(f"{name}: {exc}") from exc
    if body.get("error"):
        raise RuntimeError(f"{name}: {body['error']}")
    return body.get("result") or {}


def _vertices(body: dict, key: str) -> list[dict]:
    found = []
    for block in body.get("results") or []:
        rows = block.get(key)
        if isinstance(rows, list):
            found.extend(rows)
        elif isinstance(rows, dict) and rows.get("v_id"):
            found.append(rows)
    return found


def _accum(body: dict, key: str):
    for block in body.get("results") or []:
        if key in block:
            return block[key]
    return None


def _txn(row: dict) -> tuple:
    attrs = row.get("attributes") or {}
    return (
        row.get("v_id"),
        attrs.get("ts") or "",
        float(attrs.get("amount") or 0),
        attrs.get("product") or "",
        attrs.get("channel") or "",
        attrs.get("addr") or "",
        attrs.get("email") or "",
        float(attrs.get("risk_score") or 0),
        attrs.get("customer_id") or "",
        attrs.get("card1") or "",
    )


def _case(row: dict) -> ClosedCase:
    attrs = row.get("attributes") or {}
    return ClosedCase(
        case_id=row.get("v_id") or "",
        customer_id=attrs.get("customer_id") or "",
        card_id=attrs.get("card_id") or "",
        outcome=attrs.get("outcome") or "",
        pattern=attrs.get("pattern") or "",
        txn_ids=[],
        connected=[],
        exposure=float(attrs.get("exposure") or 0),
        actions=attrs.get("actions") or "",
        notes=attrs.get("notes") or "",
    )


def _index_from(case: dict, window: list[dict], profile: str, id15: str, id23: str, customers: set[str], cards: set[str], closed: list[ClosedCase]) -> GraphIndex:
    txns = {}
    by_card: dict[tuple[str, str], list[str]] = {}
    for row in window:
        item = _txn(row)
        if not item[0]:
            continue
        txns[item[0]] = item
        by_card.setdefault((item[8], item[9]), []).append(item[0])
    flagged_id = case["flagged_txn_id"]
    if flagged_id not in txns and window:
        pass
    identity = {flagged_id: (profile, id15, id23)}
    device_cards: dict[str, set[tuple[str, str]]] = {}
    card_id_of: dict[tuple[str, str], str] = {}
    if profile:
        keys = set()
        flagged = txns.get(flagged_id)
        if flagged:
            own = (flagged[8], flagged[9])
            keys.add(own)
            card_id_of[own] = case.get("card_id") or ""
        people = [customer for customer in customers if customer]
        if flagged and flagged[8] not in people:
            people.append(flagged[8])
        for customer in people:
            keys.add((customer, "on-device"))
        owners = people or ["device"]
        for index, card_id in enumerate(cards):
            if card_id == case.get("card_id"):
                continue
            key = (owners[index % len(owners)], f"card:{card_id}")
            keys.add(key)
            card_id_of[key] = card_id
        device_cards[profile] = keys
    closed_by_card: dict[str, list[int]] = {}
    for index, item in enumerate(closed):
        closed_by_card.setdefault(item.card_id, []).append(index)
    valid = set(cards)
    if case.get("card_id"):
        valid.add(case["card_id"])
    return GraphIndex(
        txns=txns,
        by_card=by_card,
        identity=identity,
        device_cards=device_cards,
        card_id_of=card_id_of,
        valid_card_ids=valid,
        valid_customers=set(customers),
        closed=closed,
        closed_by_card=closed_by_card,
        pack=[],
        built_at="tigergraph",
    )


def live_measure(case: dict) -> dict:
    seed = case["flagged_txn_id"]
    params = {"seed": seed}
    window = _vertices(run_query("card_window", params), "Window")
    if not window:
        window = _vertices(run_query("txn_and_card", params), "seed")
    devices = _vertices(run_query("device_profile", params), "Dev")
    profile = devices[0]["v_id"] if devices else ""
    try:
        flag = run_query("identity_flag", {"seed": seed})
    except RuntimeError:
        flag = {}
    if flag.get("error"):
        flag = {}
    flags = _vertices(flag, "Found") or _vertices(flag, "Start")
    attrs = (flags[0].get("attributes") if flags else {}) or {}
    neighbors = run_query("device_neighbors", params)
    customers = set(_accum(neighbors, "@@customers") or [])
    cards = set(_accum(neighbors, "@@cards") or [])
    run_query("region_history", params)
    run_query("recurring_match", params)
    prior = run_query("prior_cases", params)
    seen: set[str] = set()
    cases = []
    for row in _vertices(prior, "Mine") + _vertices(prior, "Linked"):
        item = _case(row)
        if item.case_id and item.case_id not in seen:
            seen.add(item.case_id)
            cases.append(item)
    run_query("exposure_episode", params)
    from graph.public.service import measurement_pack

    measured = measurement_pack(
        case,
        _index_from(case, window, profile, attrs.get("id_15") or "", attrs.get("id_23") or "", customers, cards, cases),
    )
    measured["queries_run"] = [{"name": name, "kind": "pack"} for name in PACK]
    measured["graph_source"] = "tigergraph"
    return measured


def policy_by_vector(text: str) -> tuple[str, str, float]:
    from graph.private.vectors import embed

    body = run_query("policy_vector_search", {"query_vector": embed(text or "policy"), "k": 1})
    rows = _vertices(body, "Found")
    if not rows:
        return "", "", 0.0
    attrs = rows[0].get("attributes") or {}
    return rows[0].get("v_id") or "", attrs.get("body") or "", 0.0


def card_community(card_id: str) -> list[str]:
    if not card_id:
        return []
    body = run_query("card_community", {"card": card_id})
    found = _accum(body, "@@cards") or []
    return [str(card) for card in found if card]


def policy_text(note_id: str) -> str:
    body = run_query("policy_passage", {"note": note_id})
    rows = _vertices(body, "Start")
    if not rows:
        return ""
    return ((rows[0].get("attributes") or {}).get("body")) or ""


def marker_path() -> Path:
    return _repo() / ".cache" / "queries_installed"
