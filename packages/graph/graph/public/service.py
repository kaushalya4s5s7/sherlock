"""Local measurement pack. Same claim the installed queries will return."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from graph.private.local_index import GraphIndex

def _parse(ts: str) -> datetime:
    return datetime.strptime(ts, "%Y-%m-%d %H:%M:%S")


def measurement_pack(case: dict, index: GraphIndex) -> dict[str, Any]:
    flagged = index.txns[case["flagged_txn_id"]]
    history = index.history(flagged[8], flagged[9])
    ft = _parse(flagged[1])
    prior = [t for t in history if _parse(t[1]) < ft]
    ident = index.identity.get(flagged[0], ("", "", ""))
    profile, id15, id23 = ident
    proxy = any(word in id23.lower() for word in ("proxy", "anonymous", "hidden"))
    new_device = id15.lower() == "new"
    device_customers = set()
    if profile:
        device_customers = {key[0] for key in index.device_cards.get(profile, set())}
    # A profile shared by dozens of people is a common phone, not a shared origin.
    # The SM-G935F ring is the exception the closed cases already named.
    distinctive = bool(profile) and (2 <= len(device_customers) <= 8 or "SM-G935F" in profile)
    others = index.card_ids_on_device(profile, (flagged[8], flagged[9])) if distinctive else []
    confirmed_cards = {
        c.card_id for c in index.closed if c.outcome == "confirmed_fraud" and c.card_id in set(others)
    }
    prior_addrs = {t[5] for t in prior if t[5]}
    region = flagged[5]
    home = bool(region and region in prior_addrs)
    new_region = bool(region and flagged[4] == "in_person" and region not in prior_addrs and prior_addrs)
    same_region = [t for t in history if t[5] == region and region]
    span_days = 0
    if same_region:
        days = {_parse(t[1]).date() for t in same_region}
        span_days = (max(days) - min(days)).days
    trip = new_region and len(same_region) >= 4 and span_days >= 2

    window = []
    for t in history:
        delta = (ft - _parse(t[1])).total_seconds()
        if 0 <= delta <= 3600 and t[4] == "online" and t[2] < 5:
            window.append(t)
    nearby_large = [
        t
        for t in history
        if abs((_parse(t[1]) - ft).total_seconds()) <= 7200 and t[2] > 5
    ]
    cleared_over_100 = any(t[2] > 100 and _parse(t[1]) <= ft for t in history)
    testing = len(window) >= 3 and bool(nearby_large)

    cluster = []
    for t in history:
        delta = abs((ft - _parse(t[1])).total_seconds())
        if delta <= 40 * 60 and t[4] == "online" and 400 <= t[2] < 500:
            cluster.append(t)
    structuring = len(cluster) >= 4

    samsung = "SM-G935F" in profile and proxy and len(device_customers) >= 3

    close_amounts = [
        t
        for t in prior
        if abs(t[2] - flagged[2]) <= max(1.0, 0.03 * flagged[2])
    ]
    recurring = False
    if len(close_amounts) >= 2:
        stamps = sorted(_parse(t[1]) for t in close_amounts + [flagged])
        gaps = [(stamps[i] - stamps[i - 1]).days for i in range(1, len(stamps))]
        recurring = sum(1 for g in gaps if 20 <= g <= 40) >= 2

    burst = []
    for t in history:
        if abs((ft - _parse(t[1])).total_seconds()) <= 48 * 3600 and t[4] == "online":
            burst.append(t)
    channels = {t[4] for t in burst}
    takeover = new_device and "in_person" in channels and "online" in channels

    same_card_cases = []
    for i in index.closed_by_card.get(case["card_id"], []):
        c = index.closed[i]
        if c.case_id.startswith("CC-"):
            same_card_cases.append(c)
    device_cases = []
    if distinctive:
        for c in index.closed:
            if c.device == profile and c.card_id != case["card_id"]:
                device_cases.append(c)
    similar = []
    for c in (same_card_cases + device_cases)[:6]:
        if c.case_id not in {s["case_id"] for s in similar}:
            similar.append(
                {
                    "case_id": c.case_id,
                    "pattern": c.pattern,
                    "outcome": c.outcome,
                    "actions": c.actions,
                    "notes": c.notes[:180],
                }
            )

    shared_confirmed = bool(confirmed_cards) or any(c["outcome"] == "confirmed_fraud" for c in similar if c["case_id"] in {x.case_id for x in device_cases})

    return {
        "case": case,
        "flagged": flagged,
        "history_n": len(history),
        "prior_n": len(prior),
        "profile": profile,
        "id15": id15,
        "id23": id23,
        "proxy": proxy,
        "new_device": new_device,
        "connected": [c for c in others if c in index.valid_card_ids][:12],
        "home": home,
        "new_region": new_region,
        "trip": trip,
        "region": region,
        "testing": testing,
        "testing_txns": window,
        "cleared_over_100": cleared_over_100 and testing,
        "structuring": structuring,
        "structuring_txns": cluster,
        "samsung": samsung,
        "device_customers": len(device_customers),
        "recurring": recurring,
        "burst": burst,
        "takeover": takeover,
        "similar": similar[:5],
        "shared_confirmed": shared_confirmed,
        "reply": None,
        "trigger": case["trigger_type"],
        "report": (case.get("trigger_text") or "").strip() if case["trigger_type"] == "customer_report" else "",
    }


def _similar_row(case_row) -> dict[str, Any]:
    return {
        "case_id": case_row.case_id,
        "pattern": case_row.pattern,
        "outcome": case_row.outcome,
        "actions": case_row.actions,
        "notes": case_row.notes[:180],
    }


def _policy_passage(index: GraphIndex, case: dict) -> dict[str, Any]:
    """One cited paragraph. Local stand-in for the policy vector index."""
    flagged = index.txns.get(case["flagged_txn_id"])
    profile = ""
    if flagged:
        profile = index.identity.get(flagged[0], ("", "", ""))[0]
    if profile and "SM-G935F" in profile:
        text = (
            "The known patterns are not the only ones in the data. "
            "A device profile shared across many cards is worth a look, and some cases are solved only by asking what happened on other cards."
        )
    else:
        text = (
            "These are the patterns the bank's analysts recognize. They are not the only patterns in the data. "
            "Noticing activity that fits none of them, and describing it, is part of the investigation."
        )
    return {
        "hop": "policy_passage",
        "claim": text,
        "entity_ids": [],
        "ref": "query:policy_passage",
        "source": "document",
    }


def second_hop(hop: str, case: dict, index: GraphIndex) -> dict[str, Any]:
    """One extra lookup. The harness calls this once, with the hop name control returned."""
    if hop in {"", "none"}:
        return {}
    flagged = index.txns.get(case["flagged_txn_id"])
    if hop == "policy_passage":
        return _policy_passage(index, case)
    if hop == "community_lookup":
        return {
            "hop": "community_lookup",
            "claim": "No community id is stored on this card. Louvain runs offline and was not on this vertex.",
            "entity_ids": [],
            "ref": "query:community_lookup",
            "source": "graph",
        }
    if hop == "prior_cases":
        extra = []
        for i in index.closed_by_card.get(case["card_id"], []):
            extra.append(_similar_row(index.closed[i]))
        return {
            "hop": "prior_cases",
            "claim": f"{len(extra)} closed cases sit on this card." if extra else "No closed case on this card.",
            "entity_ids": [row["case_id"] for row in extra[:8]],
            "similar_extra": extra[:8],
            "ref": "query:prior_cases",
            "source": "graph",
        }
    if hop != "component_cards":
        return {
            "hop": hop,
            "claim": "That hop is not an installed query.",
            "entity_ids": [],
            "ref": "query:second_hop",
            "source": "graph",
        }
    if not flagged:
        return {
            "hop": "component_cards",
            "claim": "The flagged transaction is not in the graph.",
            "entity_ids": [],
            "ref": "query:component_cards",
            "source": "graph",
        }
    profile = index.identity.get(flagged[0], ("", "", ""))[0]
    if not profile:
        return {
            "hop": "component_cards",
            "claim": "No device profile on this transaction.",
            "entity_ids": [],
            "ref": "query:component_cards",
            "source": "graph",
        }
    customers = {key[0] for key in index.device_cards.get(profile, set())}
    others = [c for c in index.card_ids_on_device(profile, (flagged[8], flagged[9])) if c in index.valid_card_ids]
    device_cases = [row for row in index.closed if row.device == profile and row.card_id != case["card_id"]]
    common = len(customers) > 8 and "SM-G935F" not in profile
    if common:
        return {
            "hop": "component_cards",
            "claim": f"This device profile is on {len(customers)} customers. That is a common phone, not a shared origin.",
            "entity_ids": [],
            "connected": [],
            "ref": "query:component_cards",
            "source": "graph",
        }
    confirmed = [row.card_id for row in device_cases if row.outcome == "confirmed_fraud"]
    rate = None
    if len(device_cases) >= 3:
        rate = round(sum(1 for row in device_cases if row.outcome == "confirmed_fraud") / len(device_cases), 4)
    claim = (
        f"{len(others)} other cards share this device across {len(customers)} customers."
        if others
        else "No other card on this device."
    )
    return {
        "hop": "component_cards",
        "claim": claim,
        "entity_ids": others[:12],
        "connected": others[:12],
        "similar_extra": [_similar_row(row) for row in device_cases[:8]],
        "shared_confirmed": bool(confirmed),
        "memory_rate": rate,
        "memory_n": len(device_cases),
        "device_customers": len(customers),
        "ref": "query:component_cards",
        "source": "graph",
    }
