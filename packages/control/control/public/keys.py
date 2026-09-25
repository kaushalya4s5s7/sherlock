"""Jev configuration. Engines call this module instead of reading the environment."""

from __future__ import annotations

import os

PINNED_VERSION = "jev-1.13.0"
BEATAPI_SYSTEMONE = "https://api.beatapi.io/v1/systemone"
BEATAPI_MODEL = "jev-1.13-free"


def jev() -> dict | None:
    url = os.environ.get("JEV_API_URL", "").strip()
    key = os.environ.get("JEV_API_KEY", "").strip() or os.environ.get("BEATAPI_API_KEY", "").strip()
    if key and not url and os.environ.get("BEATAPI_API_KEY", "").strip():
        url = BEATAPI_SYSTEMONE
    if not url or not key:
        return None
    version = os.environ.get("JEV_MODEL_VERSION", "").strip()
    if not version:
        version = BEATAPI_MODEL if "beatapi.io" in url else PINNED_VERSION
    return {"url": url, "key": key, "version": version}
