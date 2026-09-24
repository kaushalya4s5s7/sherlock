"""Language-model configuration. The prose engine reads this module, not the environment."""

from __future__ import annotations

import os


def model() -> dict | None:
    key = os.environ.get("LANGUAGE_API_KEY", "").strip()
    base = os.environ.get("LANGUAGE_BASE_URL", "").strip().rstrip("/")
    name = os.environ.get("LANGUAGE_MODEL", "").strip()
    if not key or not base or not name:
        return None
    return {"key": key, "base_url": base, "name": name}
