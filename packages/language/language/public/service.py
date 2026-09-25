"""Summary and SAR only. The model may rephrase a claim. It may not add a fact."""

from __future__ import annotations

import json

from language.private.chat import ModelError, complete
from language.public.keys import model


def _summary_claims(m: dict, pattern: str, desc: str, p: float, actions: list[dict], reply: dict | None) -> list[dict]:
    flagged = m["flagged"]
    names = ", ".join(a["action"] for a in actions)
    lead = (
        f"Case {m['case']['case_id']} on card {m['case']['card_id']}: "
        f"${flagged[2]:.2f} {flagged[4].replace('_', ' ')} at {flagged[1]}."
    )
    middle = f"{desc} Fraud probability is {p:.2f}. Pattern is {pattern}."
    sentences = [
        {"text": lead, "ref": "query:card_history", "claim": lead},
        {"text": middle, "ref": "query:pattern_window", "claim": desc or lead},
    ]
    if reply:
        assumed = f"We assumed: {reply['assumption']}."
        sentences.append({"text": assumed, "ref": "reply:assumption", "claim": reply["assumption"]})
    tail = f"Final actions: {names}."
    sentences.append({"text": tail, "ref": "policy:final_actions", "claim": tail})
    policy = (m.get("policy_context") or "").strip()
    if policy:
        sentences.append({"text": policy, "ref": "query:policy_passage", "claim": policy})
    return sentences


def _sar_claims(m: dict, desc: str, exposure: float) -> list[dict]:
    flagged = m["flagged"]
    narrative = (
        f"Customer {m['case']['customer_id']} used card {m['case']['card_id']}. "
        f"{desc} The flagged transaction is {flagged[0]} for ${flagged[2]:.2f} on {flagged[1]}, "
        f"channel {flagged[4].replace('_', ' ')}, billing region {flagged[5] or 'not recorded'}."
    )
    if m["profile"]:
        narrative += f" The device profile is {m['profile']}."
    if m["connected"]:
        narrative += f" The same profile appears on cards {', '.join(m['connected'][:4])}."
    amount = f"Suspicious amount on the affected transactions is ${exposure:.2f}."
    filed = "The report is filed because the final action list includes FILE_REPORT."
    memory = "Closed cases guided the search and are not treated as proof by themselves."
    return [
        {"text": narrative, "ref": "query:card_history", "claim": narrative},
        {"text": amount, "ref": "query:pattern_window", "claim": amount},
        {"text": filed, "ref": "policy:final_actions", "claim": filed},
        {"text": memory, "ref": "query:prior_cases", "claim": memory},
    ]


def _json_object(raw: str) -> dict | None:
    text = raw.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1]
        if text.endswith("```"):
            text = text[: -3]
        text = text.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _parse(raw: str, claims: list[dict]) -> list[dict] | None:
    payload = _json_object(raw)
    if payload is None:
        return None
    rows = payload.get("sentences") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        return None
    allowed = {item["ref"]: item for item in claims}
    drafted = []
    for row in rows:
        if not isinstance(row, dict):
            return None
        ref = row.get("ref")
        text = (row.get("text") or "").strip()
        if ref not in allowed or not text:
            return None
        drafted.append({"text": text, "ref": ref, "claim": allowed[ref]["claim"]})
    if len(drafted) != len(claims):
        return None
    return drafted


def _rewrite(claims: list[dict], kind: str, allow_fallback: bool) -> dict:
    cfg = model()
    if cfg is None:
        if not allow_fallback:
            raise RuntimeError("language model is not configured")
        return {"sentences": claims, "fallback": True, "tokens": 0}
    instruction = (
        "Rewrite each claim as one plain sentence. Return JSON only: "
        '{"sentences":[{"ref":"...","text":"..."}]}. '
        "Use every ref once, in the same order. Do not add a fact, an id, a probability, a pattern, or an action."
    )
    if kind == "sar":
        instruction += " This is a suspicious activity report. Keep who, what, when, where, and the amount."
    messages = [
        {"role": "system", "content": instruction},
        {"role": "user", "content": json.dumps({"sentences": [{"ref": c["ref"], "text": c["claim"]} for c in claims]})},
    ]
    try:
        raw, tokens = complete(cfg, messages)
    except ModelError:
        if not allow_fallback:
            raise
        return {"sentences": claims, "fallback": True, "tokens": 0}
    drafted = _parse(raw, claims)
    if drafted is None:
        if not allow_fallback:
            raise RuntimeError("language model returned sentences that do not match the claims")
        return {"sentences": claims, "fallback": True, "tokens": tokens}
    return {"sentences": drafted, "fallback": False, "tokens": tokens}


def draft_summary(
    m: dict,
    pattern: str,
    desc: str,
    p: float,
    actions: list[dict],
    reply: dict | None,
    *,
    allow_fallback: bool = True,
) -> dict:
    claims = _summary_claims(m, pattern, desc, p, actions, reply)
    return _rewrite(claims, "summary", allow_fallback)


def draft_sar(
    m: dict,
    actions: list[dict],
    desc: str,
    exposure: float,
    txn_ids: list[str],
    *,
    allow_fallback: bool = True,
) -> dict:
    filing = any(a["action"] == "FILE_REPORT" for a in actions)
    if not filing:
        return {
            "file": False,
            "reason": "FILE_REPORT is not in the final actions.",
            "narrative": "",
            "subjects": [],
            "total_amount_usd": 0,
            "activity_dates": [],
            "sentences": [],
            "fallback": False,
            "tokens": 0,
        }
    flagged = m["flagged"]
    dates = sorted({t[1][:10] for t in (m["structuring_txns"] or m["testing_txns"] or [flagged])})
    subjects = [m["case"]["customer_id"], m["case"]["card_id"], *m["connected"][:4]]
    if m["profile"]:
        subjects.append(m["profile"][:80])
    drafted = _rewrite(_sar_claims(m, desc, exposure), "sar", allow_fallback)
    return {
        "file": True,
        "reason": next(a["reason"] for a in actions if a["action"] == "FILE_REPORT"),
        "narrative": " ".join(item["text"] for item in drafted["sentences"]),
        "sentences": drafted["sentences"],
        "subjects": subjects,
        "total_amount_usd": exposure,
        "activity_dates": [dates[0], dates[-1]] if dates else [],
        "fallback": drafted["fallback"],
        "tokens": drafted["tokens"],
    }
