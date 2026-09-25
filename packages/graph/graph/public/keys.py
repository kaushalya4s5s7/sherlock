"""TigerGraph configuration for installed queries. Empty when the cluster is unset."""

from __future__ import annotations

import os


def tigergraph() -> dict | None:
    host = os.environ.get("TG_HOST", "").strip()
    graph = os.environ.get("TG_GRAPH", "").strip()
    token = os.environ.get("TG_TOKEN", "").strip()
    if not host or not graph or not token:
        return None
    return {"host": host.rstrip("/"), "graph": graph, "token": token}
