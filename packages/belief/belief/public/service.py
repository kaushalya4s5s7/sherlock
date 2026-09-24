from __future__ import annotations

import math

def _logit(p: float) -> float:
    p = min(max(p, 1e-4), 1 - 1e-4)
    return math.log(p / (1 - p))


def _sigmoid(x: float) -> float:
    if x > 20:
        return 1.0
    if x < -20:
        return 0.0
    return 1 / (1 + math.exp(-x))


def believe(m: dict, prior: float | None) -> tuple[float, list[dict], bool]:
    p0 = 0.5 if prior is None else prior
    odds = _logit(p0)
    steps = [{"name": "risk score prior", "delta": 0.0, "p": round(p0, 4)}]
    updates = [
        ("card testing", m["testing"], 1.6),
        ("structuring cluster", m["structuring"], 2.2),
        ("shared proxy device", m["samsung"], 2.4),
        ("new device", m["new_device"], 0.7),
        ("anonymous proxy", m["proxy"], 0.9),
        ("shared with a confirmed case", m["shared_confirmed"], 1.3),
        ("new region", m["new_region"] and not m["trip"], 0.8),
        ("home region", m["home"], -1.1),
        ("travel shape", m["trip"], -1.4),
        ("monthly subscription", m["recurring"], -1.6),
        ("long quiet history", m["prior_n"] >= 8 and not m["testing"], -0.4),
    ]
    contradiction = False
    fraud_bits = 0
    legit_bits = 0
    for name, fired, delta in updates:
        if not fired:
            continue
        odds += delta
        steps.append({"name": name, "delta": delta, "p": round(_sigmoid(odds), 4)})
        if delta > 0:
            fraud_bits += 1
        else:
            legit_bits += 1
    if m["reply"] == "deny":
        odds += 1.4
        steps.append({"name": "customer denies the purchase", "delta": 1.4, "p": round(_sigmoid(odds), 4)})
    elif m["reply"] == "confirm":
        odds -= 1.8
        steps.append({"name": "customer confirms the purchase", "delta": -1.8, "p": round(_sigmoid(odds), 4)})
    elif m["reply"] == "none":
        odds += 0.3
        steps.append({"name": "no reply in 24 hours", "delta": 0.3, "p": round(_sigmoid(odds), 4)})
    if fraud_bits and legit_bits:
        contradiction = True
    return round(_sigmoid(odds), 4), steps, contradiction


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


def prior(m: dict) -> float | None:
    raw = m["case"].get("risk_score")
    if raw is None or raw == "":
        flagged = m["flagged"]
        return flagged[7]
    return float(raw)
