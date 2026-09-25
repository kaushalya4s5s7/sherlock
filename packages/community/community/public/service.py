"""Offline device communities. Not computed during a case."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent
    raise FileNotFoundError("repo root")


def path() -> Path:
    return _repo() / "runs" / "community.json"


def status() -> str:
    return "ready" if path().is_file() else "not run"


def lookup(card_id: str) -> dict | None:
    file = path()
    if not card_id or not file.is_file():
        return None
    return json.loads(file.read_text()).get(card_id)


def build(index) -> dict:
    parent: dict[str, str] = {}

    def find(card: str) -> str:
        parent.setdefault(card, card)
        if parent[card] != card:
            parent[card] = find(parent[card])
        return parent[card]

    def union(left: str, right: str) -> None:
        left, right = find(left), find(right)
        if left != right:
            parent[right] = left

    for profile, keys in index.device_cards.items():
        customers = {key[0] for key in keys}
        if not (2 <= len(customers) <= 8 or "SM-G935F" in profile):
            continue
        cards = []
        for key in keys:
            card_id = index.card_id_of.get(key)
            if card_id:
                cards.append(card_id)
        for card_id in cards[1:]:
            union(cards[0], card_id)
    groups: dict[str, list[str]] = {}
    for card_id in list(parent):
        groups.setdefault(find(card_id), []).append(card_id)
    confirmed = {
        case.card_id
        for case in index.closed
        if case.outcome == "confirmed_fraud"
    }
    rows = {}
    for members in groups.values():
        members = sorted(set(members))
        digest = hashlib.sha256("|".join(members).encode()).hexdigest()[:8]
        community_id = f"CM-{digest}"
        hits = sum(1 for card_id in members if card_id in confirmed)
        for card_id in members:
            rows[card_id] = {
                "community_id": community_id,
                "cards": len(members),
                "confirmed": hits,
            }
    path().parent.mkdir(parents=True, exist_ok=True)
    path().write_text(json.dumps(rows))
    return rows
