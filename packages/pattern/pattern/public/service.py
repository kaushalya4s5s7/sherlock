from __future__ import annotations

def pattern_of(m: dict) -> tuple[str, str, list[dict]]:
    why = []
    if m["structuring"]:
        name, desc = "undocumented", (
            f"{len(m['structuring_txns'])} online purchases between $400 and $500 "
            "inside 40 minutes. That shape is not one of the five named patterns."
        )
    elif m["samsung"]:
        name, desc = "undocumented", (
            "Samsung SM-G935F on Chrome for Android through an anonymous proxy, "
            f"seen on {m['device_customers']} cardholders."
        )
    elif m["testing"]:
        name, desc = "card_testing", (
            f"{len(m['testing_txns'])} online purchases under $5 inside one hour, "
            "then a larger purchase."
        )
    elif m["recurring"]:
        name, desc = "none", "The amount repeats on a roughly monthly gap. This looks like a subscription."
    elif m["trip"]:
        name, desc = "none", "Several days of purchases in one new region, which reads as travel."
    elif m["new_region"] and m["trigger"] != "customer_report":
        name, desc = "out_of_region_use", f"In-person purchase in region {m['region']}, which is not in this card's history."
    elif m["takeover"]:
        name, desc = "account_takeover", "In-person and online purchases in the same two days, from a device this card has not used."
    elif m["new_device"] and m["flagged"][4] == "online" and (m["proxy"] or m["shared_confirmed"]) and len(m["burst"]) >= 2:
        name, desc = "card_not_present_new_device", "A burst of online purchases from a new device that is also a proxy or shared with another card."
    elif m["flagged"][4] == "online" and (m["proxy"] or m["shared_confirmed"]) and not m["recurring"]:
        name, desc = "card_not_present_fraud", "Online purchase from a proxy or a device shared with a confirmed case."
    elif m["home"] and m["flagged"][4] == "in_person":
        name, desc = "none", f"In-person purchase in region {m['region']}, which this card has used before."
    elif m["home"]:
        name, desc = "none", "Online purchase in a region this card already uses. No proxy and no distinctive shared device."
    else:
        name, desc = "none", "No fraud pattern in this card's history."

    catalog = {
        "card_testing": m["testing"],
        "card_not_present_fraud": name == "card_not_present_fraud",
        "card_not_present_new_device": name == "card_not_present_new_device",
        "out_of_region_use": name == "out_of_region_use",
        "account_takeover": name == "account_takeover",
    }
    for label, hit in catalog.items():
        if not hit and label != name:
            why.append({"pattern": label, "reason": "the measurement for this pattern did not fire"})
    if name != "undocumented":
        why.append({"pattern": "undocumented", "reason": "no structuring cluster and no SM-G935F proxy ring"})
    return name, desc, why[:5]
