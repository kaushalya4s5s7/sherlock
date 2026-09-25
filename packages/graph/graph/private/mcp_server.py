"""A small MCP endpoint the investigation calls for installed queries and policy search.

The tools are the ones the agent is allowed to use: run an installed query by name,
and retrieve one policy paragraph. The model does not write GSQL.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from graph.private.vectors import NOTES, rank

TOOLS = [
    {
        "name": "run_installed_query",
        "description": "Run one installed GSQL query on the HHGOA graph.",
    },
    {
        "name": "search_policy",
        "description": "Return the policy paragraph closest to this case.",
    },
]


def _rest_query(name: str, params: dict) -> dict:
    from graph.private.installed import rest_query

    return rest_query(name, params)


def _search(text: str) -> dict:
    stored = _graph_notes()
    if stored:
        from graph.private.vectors import embed

        left = embed(text or "policy")
        best_id, best_body, best_score = next(iter(stored)), "", -1.0
        for note_id, (body, vector) in stored.items():
            if len(vector) != len(left):
                continue
            score = sum(a * b for a, b in zip(left, vector))
            if score > best_score:
                best_id, best_body, best_score = note_id, body, score
        if best_body:
            return {"note_id": best_id, "body": best_body, "score": round(best_score, 4), "source": "tigergraph"}
    note_id, body, score = rank(text or "policy", NOTES)
    return {"note_id": note_id, "body": body, "score": round(score, 4), "source": "local"}


def _graph_notes() -> dict[str, tuple[str, list[float]]]:
    from graph.public.keys import tigergraph

    cfg = tigergraph()
    if cfg is None:
        return {}
    from urllib.request import Request, urlopen

    request = Request(
        f"{cfg['host']}/restpp/graph/{cfg['graph']}/vertices/PolicyNote?limit=20",
        headers={"Authorization": f"Bearer {cfg['token']}"},
    )
    try:
        with urlopen(request, timeout=20) as response:
            body = json.loads(response.read().decode() or "{}")
    except Exception:
        return {}
    notes = {}
    for row in body.get("results") or []:
        attrs = row.get("attributes") or {}
        text = attrs.get("body") or ""
        raw = attrs.get("emb") or ""
        if not row.get("v_id") or not text or not raw:
            continue
        try:
            vector = [float(part) for part in str(raw).split(",")]
        except ValueError:
            continue
        notes[row["v_id"]] = (text, vector)
    return notes


def dispatch(name: str, arguments: dict) -> dict:
    if name == "run_installed_query":
        return _rest_query(arguments["query_name"], arguments.get("params") or {})
    if name == "search_policy":
        return _search(arguments.get("text") or "")
    raise KeyError(name)


class _Handler(BaseHTTPRequestHandler):
    def do_POST(self) -> None:  # noqa: N802
        length = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(length) or b"{}")
        method = body.get("method")
        if method == "initialize":
            result = {"protocolVersion": "2024-11-05", "capabilities": {"tools": {}}}
        elif method == "tools/list":
            result = {"tools": TOOLS}
        elif method == "tools/call":
            params = body.get("params") or {}
            try:
                result = dispatch(params.get("name") or "", params.get("arguments") or {})
            except Exception as exc:
                result = {"error": True, "message": str(exc)}
        else:
            result = {}
        payload = json.dumps({"jsonrpc": "2.0", "id": body.get("id"), "result": result}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, fmt: str, *args) -> None:
        return


def serve(port: int) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", port), _Handler)
    return server
