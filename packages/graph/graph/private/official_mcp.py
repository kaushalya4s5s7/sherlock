"""Talk to the official TigerGraph MCP server over streamable HTTP.

The investigation asks this server to run an installed query. It does not
write GSQL, and it does not keep its own copy of the database tools.
"""

from __future__ import annotations

import json
import os
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

_SESSION = ""
_READY = False


def spawn(port: int = 9012) -> bool:
    """Start the official TigerGraph MCP HTTP server if the package is installed."""
    import shutil
    import subprocess
    import sys
    from pathlib import Path

    binary = shutil.which("tigergraph-mcp")
    if binary is None:
        beside = Path(sys.executable).parent / "tigergraph-mcp"
        binary = str(beside) if beside.is_file() else ""
    if not binary:
        return False
    import socket

    probe = socket.socket()
    probe.settimeout(0.3)
    try:
        probe.connect(("127.0.0.1", port))
    except OSError:
        probe.close()
    else:
        probe.close()
        os.environ["TG_MCP_URL"] = f"http://127.0.0.1:{port}/mcp/"
        os.environ["TG_MCP_OFFICIAL"] = "1"
        return True
    host = os.environ.get("TG_HOST", "").strip()
    graph = os.environ.get("TG_GRAPH", "").strip()
    token = os.environ.get("TG_TOKEN", "").strip()
    if not host or not graph or not token:
        return False
    folder = None
    for parent in Path(__file__).resolve().parents:
        if (parent / ".cache").is_dir() or (parent / "gsql").is_dir():
            folder = parent / ".cache"
            break
    if folder is None:
        return False
    folder.mkdir(parents=True, exist_ok=True)
    env_file = folder / "mcp.env"
    env_file.write_text(
        "\n".join(
            [
                f"TG_HOST={host}",
                f"TG_GRAPHNAME={graph}",
                f"TG_API_TOKEN={token}",
                "TG_TGCLOUD=true",
                "TG_SSL_PORT=443",
            ]
        )
        + "\n"
    )
    subprocess.Popen(
        [
            binary,
            "--transport",
            "streamable-http",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--env-file",
            str(env_file),
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    os.environ["TG_MCP_URL"] = f"http://127.0.0.1:{port}/mcp/"
    os.environ["TG_MCP_OFFICIAL"] = "1"
    return True


def enabled() -> bool:
    return os.environ.get("TG_MCP_OFFICIAL") == "1" and bool(os.environ.get("TG_MCP_URL", "").strip())


def _url() -> str:
    return os.environ["TG_MCP_URL"].strip()


def _post(payload: dict, *, session: str = "") -> tuple[dict, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json, text/event-stream",
    }
    if session:
        headers["Mcp-Session-Id"] = session
    request = Request(_url(), data=json.dumps(payload).encode(), headers=headers, method="POST")
    with urlopen(request, timeout=90) as response:
        raw = response.read().decode() or ""
        session_id = response.headers.get("Mcp-Session-Id") or response.headers.get("mcp-session-id") or session
    if not raw.strip():
        return {}, session_id
    return _decode(raw), session_id


def _decode(raw: str) -> dict:
    text = raw.strip()
    if text.startswith("{"):
        return json.loads(text)
    for line in text.splitlines():
        if line.startswith("data:"):
            chunk = line[5:].strip()
            if chunk and chunk != "[DONE]":
                return json.loads(chunk)
    raise RuntimeError("TigerGraph MCP returned no JSON")


def _ensure() -> str:
    global _SESSION, _READY
    if _READY and _SESSION:
        return _SESSION
    body, session = _post(
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-03-26",
                "capabilities": {},
                "clientInfo": {"name": "hhgoa", "version": "1"},
            },
        }
    )
    if body.get("error"):
        raise RuntimeError(str(body["error"]))
    _SESSION = session
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"}, session=_SESSION)
    _READY = True
    return _SESSION


def call_tool(name: str, arguments: dict) -> dict:
    session = _ensure()
    body, _session = _post(
        {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {"name": name, "arguments": arguments},
        },
        session=session,
    )
    if body.get("error"):
        raise RuntimeError(str(body["error"]))
    result = body.get("result") or {}
    if result.get("isError"):
        raise RuntimeError(_text(result) or "TigerGraph MCP tool failed")
    parsed = _text(result).strip()
    if parsed.startswith("```"):
        parsed = parsed.split("\n", 1)[-1]
        if parsed.endswith("```"):
            parsed = parsed[: parsed.rfind("```")]
        parsed = parsed.strip()
    if not parsed:
        return {}
    try:
        loaded = json.loads(parsed)
    except json.JSONDecodeError:
        return {"message": parsed}
    data = loaded.get("data") if isinstance(loaded, dict) else None
    query_result = data.get("result") if isinstance(data, dict) else None
    if isinstance(query_result, dict) and "results" in query_result:
        return query_result
    if isinstance(query_result, list):
        return {"results": query_result}
    return loaded if isinstance(loaded, dict) else {}


def _text(result: dict) -> str:
    chunks = []
    for block in result.get("content") or []:
        if isinstance(block, dict) and block.get("text"):
            chunks.append(block["text"])
    return "\n".join(chunks)
