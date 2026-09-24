from __future__ import annotations

from contracts import RULES

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


def _route(exposure: float, fraud: bool) -> str | None:
    if not fraud:
        return None
    if exposure > 2500:
        return "L2"
    return "L1"


def exposure_of(m: dict) -> float:
    rows = m["testing_txns"] or m["structuring_txns"] or m["burst"] or [m["flagged"]]
    if not rows:
        rows = [m["flagged"]]
    return round(sum(abs(t[2]) for t in rows), 2)


def _target(action: str, m: dict) -> str:
    case = m["case"]
    if action in {"BLOCK_CARD", "MONITOR_CARD", "WARN_CUSTOMER", "VERIFY_WITH_CUSTOMER", "STEP_UP_AUTH"}:
        return case["card_id"]
    if action == "MONITOR_CONNECTED_CARDS":
        return ",".join(m["connected"][:6]) or case["card_id"]
    if action in {"DECLINE_TRANSACTION", "ALLOW_TRANSACTION"}:
        return case["flagged_txn_id"]
    if action == "CREATE_CASE":
        return case["case_id"]
    return case["customer_id"]


def _reason(name: str, fired: dict, m: dict, exposure: float) -> str:
    if name == "VERIFY_WITH_CUSTOMER" and fired["R7"]["fired"]:
        return "R7: the customer disputes a charge that matches a monthly subscription"
    if name == "WARN_CUSTOMER":
        return "R7: warn the customer, and do not block a subscription"
    if name == "VERIFY_WITH_CUSTOMER":
        return "R1: one weak signal, so verify before any block"
    if name == "DECLINE_TRANSACTION" and fired["R5"]["fired"]:
        return "R5: card testing, decline and step up"
    if name == "DECLINE_TRANSACTION" and fired["R4"]["fired"]:
        return "R4: no reply in 24 hours, so decline until the customer answers"
    if name == "STEP_UP_AUTH":
        return "R5: card testing, step-up authentication"
    if name == "BLOCK_CARD" and fired["R5"]["fired"]:
        return "R5: a purchase over $100 already cleared during card testing"
    if name == "BLOCK_CARD":
        band = "L2, exposure over $2,500" if exposure > 2500 else "L1, exposure at or under $2,500"
        return f"R2: the customer denied the purchase. {band}"
    if name == "FILE_REPORT" and fired["R9"]["fired"]:
        return "R9: coordinated activity with no named pattern"
    if name == "FILE_REPORT" and fired["R6"]["fired"]:
        return "R6: a distinctive device is shared with a confirmed fraud case"
    if name == "FILE_REPORT":
        return "R2: denial plus exposure over $1,000 or a shared confirmed case"
    if name == "MONITOR_CONNECTED_CARDS":
        return "R6: watch the other cards on this device"
    if name == "ESCALATE_TO_ANALYST" and fired["R9"]["fired"]:
        return "R9: a person should see an unnamed pattern"
    if name == "ESCALATE_TO_ANALYST":
        return "R8: still uncertain and exposure is over $500"
    if name == "CLOSE_NO_FRAUD":
        return "R3: the customer confirmed, or the history does not support fraud"
    if name == "ALLOW_TRANSACTION":
        return "The purchase matches this card's own history"
    if name == "CREATE_CASE":
        return "Open a case: probability is at least 0.30, the customer disputed, or we asked a question"
    if name == "MONITOR_CARD":
        return "R4: keep the card watched" if fired["R4"]["fired"] else "Watch the card. There is not enough to block it"
    return "Policy action"


def decide(m: dict, pattern: str, p: float, contradiction: bool, phase: str) -> tuple[list[dict], list[dict]]:
    """Pass 1 ignores the reply. Pass 2 applies R2, R3, R4."""
    fired = {rule: {"rule": rule, "fired": False, "because": "conditions not met"} for rule in RULES}
    actions: list[str] = []
    exposure = 0.0
    fraudish = pattern not in {"none"} or p >= 0.85
    reply = m["reply"] if phase == "final" else None
    trigger = m["trigger"]
    report = m["report"]
    dispute = trigger == "customer_report" and bool(report)

    def add(*names: str) -> None:
        for name in names:
            if name not in actions:
                actions.append(name)

    if m["recurring"] and dispute:
        fired["R7"] = {"rule": "R7", "fired": True, "because": "customer disputes a charge that matches a monthly subscription"}
        add("CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER")
        fraudish = False
    else:
        fired["R7"] = {"rule": "R7", "fired": False, "because": "not a disputed recurring charge"}

    if m["testing"]:
        fired["R5"] = {"rule": "R5", "fired": True, "because": f"{len(m['testing_txns'])} online charges under $5 inside one hour, then a larger one"}
        add("DECLINE_TRANSACTION", "STEP_UP_AUTH")
        if m["cleared_over_100"]:
            add("BLOCK_CARD")
    else:
        fired["R5"] = {"rule": "R5", "fired": False, "because": "no card-testing window"}

    if pattern == "undocumented" or m["shared_confirmed"]:
        if pattern == "undocumented":
            fired["R9"] = {"rule": "R9", "fired": True, "because": "coordinated pattern with no name in the policy"}
            add("CREATE_CASE", "FILE_REPORT", "ESCALATE_TO_ANALYST")
        else:
            fired["R9"] = {"rule": "R9", "fired": False, "because": "pattern is a named one"}
    else:
        fired["R9"] = {"rule": "R9", "fired": False, "because": "no undocumented coordination"}

    if m["shared_confirmed"] and not m["recurring"]:
        fired["R6"] = {"rule": "R6", "fired": True, "because": "a distinctive device on this purchase is tied to a confirmed fraud case"}
        add("CREATE_CASE", "FILE_REPORT", "MONITOR_CONNECTED_CARDS")
    else:
        fired["R6"] = {"rule": "R6", "fired": False, "because": "no confirmed fraud on a distinctive shared device"}

    signals = _independent(m)
    single = signals <= 1 and not m["testing"] and pattern != "undocumented"
    if single and p < 0.70 and not m["recurring"]:
        fired["R1"] = {"rule": "R1", "fired": True, "because": "one signal and probability under 0.70, so verify before any block"}
        add("VERIFY_WITH_CUSTOMER")
    else:
        fired["R1"] = {"rule": "R1", "fired": False, "because": "not a single weak signal"}

    if phase == "final" and reply == "confirm":
        fired["R3"] = {"rule": "R3", "fired": True, "because": "customer confirmed the purchase"}
        actions = ["CLOSE_NO_FRAUD"]
        fraudish = False
    else:
        fired["R3"] = {"rule": "R3", "fired": False, "because": "customer has not confirmed"}

    if phase == "final" and reply == "deny":
        fired["R2"] = {"rule": "R2", "fired": True, "because": "customer says they did not make the purchase"}
        add("BLOCK_CARD", "CREATE_CASE")
        if exposure_of(m) > 1000 or m["shared_confirmed"]:
            add("FILE_REPORT")
        fraudish = True
    else:
        fired["R2"] = {"rule": "R2", "fired": False, "because": "no denial on file"}

    if phase == "final" and reply == "none" and "VERIFY_WITH_CUSTOMER" in actions:
        fired["R4"] = {"rule": "R4", "fired": True, "because": "verification sent, no reply in 24 hours"}
        add("MONITOR_CARD", "DECLINE_TRANSACTION")
        actions = [a for a in actions if a != "VERIFY_WITH_CUSTOMER"]
    else:
        fired["R4"] = {"rule": "R4", "fired": False, "because": "no unanswered verification"}

    blocked = any(a in actions for a in ("BLOCK_CARD", "DECLINE_TRANSACTION", "FILE_REPORT"))
    if (contradiction or (0.15 < p < 0.85 and not blocked)) and exposure_of(m) > 500 and phase == "final":
        if not (reply == "confirm"):
            fired["R8"] = {"rule": "R8", "fired": True, "because": "still uncertain and exposure is over $500"}
            add("ESCALATE_TO_ANALYST")
    elif contradiction and exposure_of(m) > 500:
        fired["R8"] = {"rule": "R8", "fired": True, "because": "evidence conflicts and exposure is over $500"}
        add("ESCALATE_TO_ANALYST")
    else:
        if not fired["R8"]["fired"]:
            fired["R8"] = {"rule": "R8", "fired": False, "because": "no conflict above $500, or the case is already settled"}

    fired["R10"] = {"rule": "R10", "fired": False, "because": "no second card on this customer is confirmed, and there is no credential field"}

    exposure = exposure_of(m) if fraudish or any(a in actions for a in ("BLOCK_CARD", "DECLINE_TRANSACTION", "FILE_REPORT")) else 0.0

    if p >= 0.30 or dispute or trigger == "analyst_request":
        if "CLOSE_NO_FRAUD" not in actions:
            add("CREATE_CASE")

    strong = p >= 0.85 or pattern == "undocumented" or (reply == "deny" and (exposure_of(m) > 1000 or m["shared_confirmed"]))
    if fired["R7"]["fired"]:
        strong = False
    if strong and (exposure_of(m) > 1000 or m["shared_confirmed"] or pattern == "undocumented"):
        if "CLOSE_NO_FRAUD" not in actions:
            add("FILE_REPORT")

    # The opening "I never made this" is why the case exists. It is not the
    # answer to the question we have not asked yet.
    if dispute and reply is None and not m["testing"] and pattern != "undocumented" and not m["shared_confirmed"]:
        actions = [a for a in actions if a not in {"CLOSE_NO_FRAUD", "ALLOW_TRANSACTION"}]
        add("VERIFY_WITH_CUSTOMER", "CREATE_CASE")

    if "CLOSE_NO_FRAUD" in actions:
        actions = ["CLOSE_NO_FRAUD"]
        if m["trip"] or m["home"]:
            actions.append("ALLOW_TRANSACTION")
    elif not actions:
        if p <= 0.15:
            actions = ["CLOSE_NO_FRAUD", "ALLOW_TRANSACTION"]
        else:
            actions = ["MONITOR_CARD", "CREATE_CASE"]

    if "FILE_REPORT" in actions and "CREATE_CASE" not in actions:
        add("CREATE_CASE")

    exposure = exposure_of(m)
    built = []
    for name in actions:
        if name == "BLOCK_CARD":
            level = "L2" if exposure > 2500 else "L1"
        elif name in {"FILE_REPORT", "BLOCK_ALL_CARDS"}:
            level = "L2"
        elif name == "DECLINE_TRANSACTION":
            level = "L1"
        else:
            level = "auto"
        built.append({"action": name, "route": level, "reason": _reason(name, fired, m, exposure)})
    return built, [fired[r] for r in RULES]
