from __future__ import annotations

def draft_summary(m: dict, pattern: str, desc: str, p: float, actions: list[dict], reply: dict | None) -> str:
    flagged = m["flagged"]
    names = ", ".join(a["action"] for a in actions)
    lead = (
        f"Case {m['case']['case_id']} on card {m['case']['card_id']}: "
        f"${flagged[2]:.2f} {flagged[4].replace('_', ' ')} at {flagged[1]}."
    )
    middle = f" {desc} Fraud probability is {p:.2f}."
    ask = ""
    if reply:
        ask = f" We assumed: {reply['assumption']}."
    tail = f" Final actions: {names}."
    text = (lead + middle + ask + tail).strip()
    return text


def draft_sar(m: dict, actions: list[dict], desc: str, exposure: float, txn_ids: list[str]) -> dict:
    filing = any(a["action"] == "FILE_REPORT" for a in actions)
    if not filing:
        return {"file": False, "reason": "FILE_REPORT is not in the final actions.", "narrative": "", "subjects": [], "total_amount_usd": 0, "activity_dates": []}
    flagged = m["flagged"]
    dates = sorted({t[1][:10] for t in (m["structuring_txns"] or m["testing_txns"] or [flagged])})
    subjects = [m["case"]["customer_id"], m["case"]["card_id"], *m["connected"][:4]]
    if m["profile"]:
        subjects.append(m["profile"][:80])
    narrative = (
        f"Customer {m['case']['customer_id']} used card {m['case']['card_id']}. "
        f"{desc} The flagged transaction is {flagged[0]} for ${flagged[2]:.2f} on {flagged[1]}, "
        f"channel {flagged[4].replace('_', ' ')}, billing region {flagged[5] or 'not recorded'}. "
    )
    if m["profile"]:
        narrative += f"The device profile is {m['profile']}. "
    if m["connected"]:
        narrative += f"The same profile appears on cards {', '.join(m['connected'][:4])}. "
    narrative += (
        f"Suspicious amount on the affected transactions is ${exposure:.2f}. "
        "The report is filed because the final action list includes FILE_REPORT. "
        "Closed cases guided the search and are not treated as proof by themselves."
    )
    return {
        "file": True,
        "reason": next(a["reason"] for a in actions if a["action"] == "FILE_REPORT"),
        "narrative": narrative,
        "subjects": subjects,
        "total_amount_usd": exposure,
        "activity_dates": [dates[0], dates[-1]] if dates else [],
    }
