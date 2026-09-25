"""One chat call. OpenAI-shaped request, so the key can point at any compatible model."""

from __future__ import annotations

import json
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ModelError(RuntimeError):
    pass


def _post(request: Request) -> dict:
    with urlopen(request, timeout=60) as response:
        return json.loads(response.read().decode())


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
        payload = _post(request)
    except HTTPError as exc:
        if exc.code not in {429, 502, 503, 504}:
            raise ModelError(str(exc)) from exc
        time.sleep(3)
        try:
            payload = _post(request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as again:
            raise ModelError(str(again)) from again
    except (URLError, TimeoutError, json.JSONDecodeError) as exc:
        time.sleep(3)
        try:
            payload = _post(request)
        except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as again:
            raise ModelError(str(again)) from again
    try:
        text = payload["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError) as exc:
        raise ModelError("model returned no message") from exc
    usage = payload.get("usage") or {}
    tokens = int(usage.get("total_tokens") or 0)
    return text, tokens
