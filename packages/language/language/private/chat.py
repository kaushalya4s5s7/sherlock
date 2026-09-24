"""One chat call. OpenAI-shaped request, so the key can point at any compatible model."""

from __future__ import annotations

import json
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelError(RuntimeError):
    pass


def complete(cfg: dict, messages: list[dict]) -> tuple[str, int]:
    body = json.dumps(
        {
            "model": cfg["name"],
            "temperature": 0,
            "messages": messages,
        }
    ).encode()
    request = Request(
        f"{cfg['base_url']}/chat/completions",
        data=body,
        headers={"Authorization": f"Bearer {cfg['key']}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode())
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise ModelError(str(exc)) from exc
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError("model returned no message") from exc
    usage = payload.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)
    return text, tokens
