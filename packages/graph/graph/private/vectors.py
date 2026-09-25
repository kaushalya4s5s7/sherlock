"""Policy documents and a stable vector so retrieval does not depend on process salt."""

from __future__ import annotations

import hashlib
import math

DIM = 32

NOTES = {
    "policy_default": (
        "These are the patterns the bank's analysts recognize. They are not the only patterns in the data. "
        "Noticing activity that fits none of them, and describing it, is part of the investigation."
    ),
    "policy_shared_device": (
        "The known patterns are not the only ones in the data. "
        "A device profile shared across many cards is worth a look, and some cases are solved only by asking what happened on other cards."
    ),
    "rule_r1": "One weak signal and a fraud chance under 70 percent means ask the customer or send a code before any block.",
    "rule_r6": "A shared device is a case, a report, and a watch on the other cards only when those other cards are tied to fraud.",
    "rule_r7": "A customer dispute that matches a regular charge is a warning and an open case. It is not a block.",
    "rule_r8": "When the case is still unsure and the money at risk is over 500 dollars, send it to an analyst.",
    "pattern_card_testing": "Three or more online charges under 5 dollars inside an hour, then a larger purchase, is card testing.",
    "pattern_undocumented": "A shape the five named patterns do not cover stays undocumented. Describe it. Do not rename it.",
}


def embed(text: str) -> list[float]:
    vector = [0.0] * DIM
    for token in text.lower().replace("|", " ").split():
        digest = hashlib.sha256(token.encode()).digest()
        slot = digest[0] % DIM
        sign = 1.0 if digest[1] % 2 == 0 else -1.0
        vector[slot] += sign
    norm = math.sqrt(sum(value * value for value in vector)) or 1.0
    return [round(value / norm, 6) for value in vector]


def rank(query: str, notes: dict[str, str]) -> tuple[str, str, float]:
    left = embed(query)
    best_id = "policy_default"
    best_score = -1.0
    for note_id, body in notes.items():
        right = embed(body)
        score = sum(a * b for a, b in zip(left, right))
        if score > best_score:
            best_id = note_id
            best_score = score
    return best_id, notes[best_id], best_score
