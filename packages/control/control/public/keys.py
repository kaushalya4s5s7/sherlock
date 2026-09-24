"""Jev configuration. Engines call this module instead of reading the environment."""

from __future__ import annotations

import os

PINNED_VERSION = "jev-1.13.0"


def jev() -> dict | None:
    url = os.environ.get("JEV_API_URL", "").strip()
    key = os.environ.get("JEV_API_KEY", "").strip()
    if not url or not key:
        return None
    version = os.environ.get("JEV_MODEL_VERSION", "").strip() or PINNED_VERSION
    return {"url": url, "key": key, "version": version}
