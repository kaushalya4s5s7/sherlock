from __future__ import annotations

def _independent(m: dict) -> int:
    families = [
        m["testing"] or m["structuring"],
        m["new_device"] or m["proxy"] or m["samsung"] or m["shared_confirmed"],
        m["new_region"] or m["home"] or m["trip"],
        m["recurring"],
        bool(m["similar"]),
        m["reply"] in {"deny", "confirm"},
    ]
    return sum(1 for f in families if f)


def reply_for(m: dict, pattern: str, p: float, asked: bool) -> dict | None:
    if not asked:
        return None
    if m["recurring"]:
        return {
            "kind": "dispute_keeps_R7",
            "assumption": "customer does not recognise the descriptor; the monthly history still matches, so R7 stands",
            "reply": None,
        }
    if pattern in {"card_testing", "undocumented"} or m["samsung"] or m["structuring"]:
        if p >= 0.85 or _independent(m) >= 2:
            return None
        return {"kind": "deny", "assumption": "R1 requires an ask; the pattern is fraud-shaped so the customer denies it", "reply": "deny"}
    if m["new_region"] and not m["trip"]:
        return {"kind": "deny", "assumption": "the purchase is in a region this card has not used, and it does not look like a trip", "reply": "deny"}
    if m["home"] and not m["proxy"]:
        return {"kind": "confirm", "assumption": "the purchase is in a region this card has used before, so the customer confirms it", "reply": "confirm"}
    if m["trip"] and not m["proxy"]:
        return {"kind": "confirm", "assumption": "several days of purchases in one new region, which reads as a trip, so the customer confirms it", "reply": "confirm"}
    if m["new_device"] and not m["proxy"] and not m["connected"] and m["prior_n"] >= 3:
        return {"kind": "confirm", "assumption": "new device, no proxy, no other cards on it, amounts look like the customer's own", "reply": "confirm"}
    if 0.15 < p < 0.85:
        return {"kind": "none", "assumption": "still ambiguous after the ask, so no reply arrives within 24 hours", "reply": "none"}
    return {"kind": "confirm", "assumption": "no fraud pattern survived, so the customer confirms", "reply": "confirm"}


def reply_text(reply: dict) -> str:
    if reply["reply"] == "deny":
        return "I did not make this purchase."
    if reply["reply"] == "confirm":
        return "Yes, that was me."
    return "No reply within 24 hours."
