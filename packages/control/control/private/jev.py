"""One HTTP call to pinned Jev. Returns a probability map over the options we listed."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class JevError(RuntimeError):
    pass


def ask(cfg: dict, kind: str, state: dict, options: list[str]) -> dict[str, float]:
    body = json.dumps(
        {
            "model": cfg["version"],
            "kind": kind,
            "options": options,
            "state": state,
        }
    ).encode()
    request = Request(
        cfg["url"],
        data=body,
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=20) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise JevError(str(exc)) from exc
    raw = payload.get("probabilities") or payload.get("distribution") or {}
    if not isinstance(raw, dict) or not raw:
        raise JevError("Jev returned no probability map")
    probs = {}
    for name in options:
        try:
            probs[name] = float(raw.get(name, 0.0))
        except (TypeError, ValueError) as exc:
            raise JevError(f"bad probability for {name}") from exc
    total = sum(probs.values())
    if total <= 0:
        raise JevError("Jev probability map summed to zero")
    return {name: value / total for name, value in probs.items()}
