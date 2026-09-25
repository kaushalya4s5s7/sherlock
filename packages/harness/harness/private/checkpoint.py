"""Disk checkpoint for one case. The index is not stored; resume receives it again."""

from __future__ import annotations

import os
import pickle
import threading
from pathlib import Path

_LOCK = threading.Lock()


def _path() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent / "runs" / "harness_checkpoints.pkl"
    raise FileNotFoundError("repo root")


def load_all() -> dict:
    path = _path()
    if not path.exists():
        return {}
    try:
        with open(path, "rb") as handle:
            loaded = pickle.load(handle)
    except (pickle.UnpicklingError, EOFError, OSError):
        return {}
    return loaded if isinstance(loaded, dict) else {}


def save_all(states: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.{threading.get_ident()}.tmp")
    with open(temporary, "wb") as handle:
        pickle.dump(states, handle, protocol=pickle.HIGHEST_PROTOCOL)
    temporary.replace(path)


def load(case_id: str) -> dict | None:
    return load_all().get(case_id)


def save(state: dict) -> None:
    with _LOCK:
        states = load_all()
        states[state["case_id"]] = state
        save_all(states)
