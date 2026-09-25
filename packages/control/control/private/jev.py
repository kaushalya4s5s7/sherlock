"""One HTTP call to pinned Jev. Returns a probability map over the options we listed."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class JevError(RuntimeError):
    pass


_INSTRUCTIONS = {
    "hop": "Which one graph lookup should run next? Choose none when another lookup would not change the case.",
    "pattern": "Which fraud pattern fits this state? Choose insufficient when the evidence does not separate a pattern.",
    "sentence": "Do these sentences stay inside the evidence? Choose keep when they only restate a claim. Choose drop when they add a fact.",
}


def _post(request: Request) -> dict:
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode())


def ask(cfg: dict, kind: str, state: dict, options: list[str]) -> dict[str, float]:
    body = json.dumps(
        {
            "model": cfg["version"],
            "state": state,
            "questions": {
                "gate": {
                    "type": "choice",
                    "instructions": _INSTRUCTIONS.get(kind, "Which option fits this state?"),
                    "criteria": {name: None for name in options},
                }
            },
        }
    ).encode()
    request = Request(
        cfg["url"],
        data=body,
        headers={
            "Authorization": f"Bearer {cfg['key']}",
            "Content-Type": "application/json",
            "User-Agent": "tiger-task/1.0",
        },
        method="POST",
    )
    try:
        payload = _post(request)
    except HTTPError as exc:
        if exc.code not in {429, 502, 503, 504}:
            raise JevError(str(exc)) from exc
        # jev-1.13-free allows one decision per minute. One retry waits out that window.
        time.sleep(61 if exc.code == 429 else 3)
        try:
            payload = _post(request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as again:
            raise JevError(str(again)) from again
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise JevError(str(exc)) from exc
    answers = payload.get("answers") if isinstance(payload, dict) else None
    gate = answers.get("gate") if isinstance(answers, dict) else None
    raw = gate.get("probabilities") if isinstance(gate, dict) else None
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
