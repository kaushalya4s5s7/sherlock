from __future__ import annotations

def draft_summary(m: dict, pattern: str, desc: str, p: float, actions: list[dict], reply: dict | None) -> list[dict]:
    """Sentences the control gate can check. Each one cites one evidence ref."""
    flagged = m["flagged"]
    names = ", ".join(a["action"] for a in actions)
    lead = (
        f"Case {m['case']['case_id']} on card {m['case']['card_id']}: "
        f"${flagged[2]:.2f} {flagged[4].replace('_', ' ')} at {flagged[1]}."
    )
    middle = f"{desc} Fraud probability is {p:.2f}."
    sentences = [
        {"text": lead, "ref": "query:card_history", "claim": lead},
        {"text": middle, "ref": "query:pattern_window", "claim": desc or lead},
    ]
    if reply:
        assumed = f"We assumed: {reply['assumption']}."
        sentences.append({"text": assumed, "ref": "reply:assumption", "claim": reply["assumption"]})
    tail = f"Final actions: {names}."
    sentences.append({"text": tail, "ref": "policy:final_actions", "claim": tail})
    return sentences


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
    amount = f"Suspicious amount on the affected transactions is ${exposure:.2f}."
    filed = "The report is filed because the final action list includes FILE_REPORT."
    memory = "Closed cases guided the search and are not treated as proof by themselves."
    sentences = [
        {"text": narrative.strip(), "ref": "query:card_history", "claim": narrative.strip()},
        {"text": amount, "ref": "query:pattern_window", "claim": amount},
        {"text": filed, "ref": "policy:final_actions", "claim": filed},
        {"text": memory, "ref": "query:prior_cases", "claim": memory},
    ]
    return {
        "file": True,
        "reason": next(a["reason"] for a in actions if a["action"] == "FILE_REPORT"),
        "narrative": " ".join(item["text"] for item in sentences),
        "sentences": sentences,
        "subjects": subjects,
        "total_amount_usd": exposure,
        "activity_dates": [dates[0], dates[-1]] if dates else [],
    }
