"""Disk checkpoint for one case. The index is not stored; resume receives it again."""

from __future__ import annotations

import pickle
from pathlib import Path


def _path() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent / "runs" / "harness_checkpoints.pkl"
    raise FileNotFoundError("repo root")


def load_all() -> dict:
    path = _path()
    if not path.exists():
        return {}
    with open(path, "rb") as handle:
        return pickle.load(handle)


def save_all(states: dict) -> None:
    path = _path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as handle:
        pickle.dump(states, handle, protocol=pickle.HIGHEST_PROTOCOL)


def load(case_id: str) -> dict | None:
    return load_all().get(case_id)


def save(state: dict) -> None:
    states = load_all()
    states[state["case_id"]] = state
    save_all(states)
