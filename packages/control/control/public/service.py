"""Three gates. Jev when it is configured. Otherwise the deterministic fallback, recorded on the result."""

from __future__ import annotations

from control.private.jev import JevError, ask
from control.public.keys import jev

HOP_OPTIONS = ["device_component", "community", "prior_cases", "policy_text", "none"]
HOP_QUERY = {
    "device_component": "component_cards",
    "community": "community_lookup",
    "prior_cases": "prior_cases",
    "policy_text": "policy_passage",
    "none": "none",
}
PATTERN_OPTIONS = [
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "insufficient",
]


def _flat(options: list[str]) -> dict[str, float]:
    share = round(1 / len(options), 4)
    return {name: share for name in options}


def _too_close(probs: dict[str, float]) -> bool:
    ranked = sorted(probs, key=probs.get, reverse=True)
    return len(ranked) >= 2 and probs[ranked[0]] - probs[ranked[1]] < 0.1


def _map(kind: str, state: dict, options: list[str], allow_fallback: bool) -> tuple[dict[str, float], bool]:
    cfg = jev()
    if cfg is None:
        if not allow_fallback:
            raise RuntimeError("Jev is not configured")
        return _flat(options), True
    try:
        return ask(cfg, kind, state, options), False
    except JevError:
        if not allow_fallback:
            raise
        return _flat(options), True


def hop(state: dict, *, allow_fallback: bool = True) -> dict:
    probs, fallback = _map("hop", state, HOP_OPTIONS, allow_fallback)
    choice = "none" if fallback or _too_close(probs) else max(probs, key=probs.get)
    return {
        "choice": choice,
        "query": HOP_QUERY[choice],
        "probabilities": probs,
        "fallback": fallback,
    }


def pattern_gate(state: dict, *, allow_fallback: bool = True) -> dict:
    probs, fallback = _map("pattern", state, PATTERN_OPTIONS, allow_fallback)
    close = _too_close(probs)
    label = "insufficient" if fallback or close else max(probs, key=probs.get)
    ranked = sorted(probs, key=probs.get, reverse=True)
    why = []
    if label == "insufficient":
        shown = ranked[:2] if close and not fallback else [name for name in ranked if name != "insufficient"]
        for name in shown:
            if name == "insufficient":
                continue
            why.append({"pattern": name, "reason": "the pattern gate did not separate this label from the next one"})
    return {"label": label, "probabilities": probs, "fallback": fallback, "why_not": why[:5]}


def sentences(items: list[dict], *, allow_fallback: bool = True) -> dict:
    """Keep a sentence when it carries an evidence ref. A missing ref is a rejection, not a guess."""
    cfg = jev()
    fallback = cfg is None
    drop_all = False
    if cfg is None and not allow_fallback:
        raise RuntimeError("Jev is not configured")
    if cfg is not None:
        try:
            probs = ask(cfg, "sentence", {"count": len(items)}, ["keep", "drop"])
            fallback = False
            drop_all = not _too_close(probs) and max(probs, key=probs.get) == "drop"
        except JevError:
            if not allow_fallback:
                raise
            fallback = True
    kept = []
    rejected = []
    for item in items:
        row = {**item, "supported": bool(item.get("ref")) and not drop_all}
        if row["supported"]:
            kept.append(row)
        else:
            rejected.append(row)
    return {"kept": kept, "rejected": rejected, "fallback": fallback}
