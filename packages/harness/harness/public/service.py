"""One case, checkpointed. The engines decide. This module spends one hop, one ask, and one rewrite."""

from __future__ import annotations

from copy import deepcopy

from answer import build
from belief import believe, prior
from control import hop as control_hop
from control import pattern_gate, sentences
from graph import measurement_pack, second_hop
from harness.private import checkpoint
from intake import open_case
from language import draft_sar, draft_summary
from memory import recall, write_and_read
from pattern import pattern_of
from policy import decide
from reply import reply_for, reply_text
from stop import commit as stop_commit


def _commitment(m: dict, pattern: str, final_names: list[str]) -> dict:
    base = set(final_names)
    drops = {
        "sequence": {"testing": False, "structuring": False, "structuring_txns": [], "testing_txns": []},
        "device": {"new_device": False, "proxy": False, "samsung": False, "shared_confirmed": False, "connected": []},
        "region": {"new_region": False, "home": False, "trip": False},
        "recurring": {"recurring": False},
        "prior_case": {"similar": []},
        "customer_reply": {"reply": None},
    }
    for family, patch in drops.items():
        alt = deepcopy(m)
        alt.update(patch)
        pname, _, _ = pattern_of(alt)
        p, _, contra = believe(alt, prior(alt))
        acts, _ = decide(alt, pname, p, contra, "final")
        names = [a["action"] for a in acts]
        if set(names) != base:
            return {
                "family": family,
                "without_it": names,
                "text": f"Drop the {family.replace('_', ' ')} evidence and the action list changes. That family is the point of commitment.",
            }
    return {
        "family": "none",
        "without_it": final_names,
        "text": "No single family changes the action list on its own. The decision is the combination.",
    }


def _counterfactuals(m: dict, pattern: str) -> list[dict]:
    """What the other replies would have done. These are not what happened."""
    out = []
    for kind in ("confirm", "deny", "none"):
        alt = deepcopy(m)
        alt["reply"] = kind
        p, _, contra = believe(alt, prior(alt))
        acts, _ = decide(alt, pattern, p, contra, "final")
        out.append(
            {
                "reply": kind,
                "label": "not what happened",
                "actions": [a["action"] for a in acts],
                "p": p,
            }
        )
    return out


def _locked(m: dict, pattern: str) -> bool:
    return bool(
        m["testing"]
        or m["structuring"]
        or m["samsung"]
        or m["recurring"]
        or m["trip"]
        or m["new_region"]
        or m["takeover"]
        or pattern not in {"none"}
    )


def _shared(m: dict) -> bool:
    if m["samsung"] or m["connected"]:
        return True
    customers = m.get("device_customers") or 0
    return 1 < customers <= 8


def _merge_hop(m: dict, extra: dict) -> None:
    if not extra:
        return
    m.setdefault("hops", []).append(
        {
            "name": extra.get("hop"),
            "claim": extra.get("claim"),
            "ref": extra.get("ref"),
            "source": extra.get("source") or "graph",
            "entity_ids": extra.get("entity_ids") or [],
        }
    )
    for card_id in extra.get("connected") or []:
        if card_id not in m["connected"]:
            m["connected"].append(card_id)
    have = {row["case_id"] for row in m["similar"]}
    for row in extra.get("similar_extra") or []:
        if row["case_id"] not in have:
            m["similar"].append(row)
            have.add(row["case_id"])
    m["similar"] = m["similar"][:8]
    if extra.get("shared_confirmed"):
        m["shared_confirmed"] = True
    if extra.get("memory_rate") is not None and m.get("memory_rate") is None:
        m["memory_rate"] = extra["memory_rate"]
        m["memory_n"] = extra.get("memory_n") or 0


def _attach_exam_memory(m: dict) -> None:
    card_id = m["case"]["card_id"]
    device = m.get("profile") or ""
    recalled = recall(card_id, device)
    have = {row["case_id"] for row in m["similar"]}
    own = f"EXAM-{m['case']['case_id']}"
    for row in recalled:
        if row["case_id"] in have or row["case_id"] == own:
            continue
        m["similar"].append({key: row[key] for key in ("case_id", "pattern", "outcome", "actions", "notes")})
        have.add(row["case_id"])
        if row["same_device"] and row["outcome"] == "confirmed_fraud":
            m["shared_confirmed"] = True
    m["similar"] = m["similar"][:8]


def _ground(items: list[dict], rewrite_used: bool, allow_fallback: bool) -> tuple[str, bool, bool]:
    judged = sentences(items, allow_fallback=allow_fallback)
    texts = [item["text"] for item in judged["kept"]]
    fallback = bool(judged["fallback"])
    for item in judged["rejected"]:
        claim = item.get("claim") or item.get("text") or ""
        if not rewrite_used:
            rewrite_used = True
            again = sentences([{**item, "text": claim}], allow_fallback=allow_fallback)
            fallback = fallback or bool(again["fallback"])
            if again["kept"]:
                texts.append(again["kept"][0]["text"])
                continue
        if claim:
            texts.append(claim)
    return " ".join(texts).strip(), rewrite_used, fallback


def _families(m: dict) -> int:
    return sum(
        1
        for flag in (
            m["testing"] or m["structuring"],
            m["new_device"] or m["proxy"] or m["samsung"] or m["shared_confirmed"],
            m["new_region"] or m["home"] or m["trip"],
            m["recurring"],
            bool(m["similar"]),
            m["reply"] in {"deny", "confirm"},
        )
        if flag
    )


def _waiting(result: dict) -> list[str]:
    final = result["answer"]["next_best_actions"]["final"]
    approved = set(result["demo"].get("approved") or [])
    return [a["action"] for a in final if a["route"] != "auto" and a["action"] not in approved]


def _fresh(case: dict) -> dict:
    return {
        "case_id": case["case_id"],
        "case": case,
        "phase": "intake",
        "hop_used": False,
        "hop_name": "none",
        "ask_used": False,
        "rewrite_used": False,
        "gate_used": False,
        "fallback": False,
        "measured": None,
        "pattern": "none",
        "desc": "",
        "reply": None,
        "evidence_requests": [],
        "result": None,
    }


def _approve(state: dict, action: str) -> None:
    result = state.get("result")
    if not result:
        raise ValueError("that action is not waiting for approval")
    final = result["answer"]["next_best_actions"]["final"]
    match = next((a for a in final if a["action"] == action and a["route"] != "auto"), None)
    if not match:
        raise ValueError("that action is not waiting for approval")
    approved = result["demo"].setdefault("approved", [])
    if action not in approved:
        approved.append(action)
    still = _waiting(result)
    result["demo"]["approval"] = "approved" if not still else "pending"


def _step_intake(state: dict) -> None:
    state["case"] = open_case(state["case"])
    state["phase"] = "pack"


def _step_pack(state: dict, index) -> None:
    measured = measurement_pack(state["case"], index)
    _attach_exam_memory(measured)
    state["measured"] = measured
    state["phase"] = "pattern"


def _step_pattern(state: dict, allow_fallback: bool) -> None:
    measured = state["measured"]
    pattern, desc, why = pattern_of(measured)
    if not _locked(measured, pattern) and not state["gate_used"]:
        gate = pattern_gate(
            {"pattern": pattern, "shared_device": _shared(measured), "testing": measured["testing"]},
            allow_fallback=allow_fallback,
        )
        state["gate_used"] = True
        state["fallback"] = state["fallback"] or gate["fallback"]
        state["why_not"] = gate["why_not"]
        if gate["label"] not in {"", "insufficient", "none"}:
            pattern = gate["label"]
    else:
        state["why_not"] = why
    state["pattern"] = pattern
    state["desc"] = desc
    state["phase"] = "hop"


def _step_hop(state: dict, index, allow_fallback: bool) -> None:
    measured = state["measured"]
    if not state["hop_used"]:
        decision = control_hop(
            {
                "shared_device": _shared(measured),
                "device_customers": measured.get("device_customers") or 0,
                "samsung": measured["samsung"],
                "pattern": state["pattern"],
            },
            allow_fallback=allow_fallback,
        )
        state["fallback"] = state["fallback"] or decision["fallback"]
        name = decision["query"]
        if name == "none" and _shared(measured):
            name = "component_cards"
        if name != "none":
            _merge_hop(measured, second_hop(name, state["case"], index))
            state["hop_used"] = True
            state["hop_name"] = name
            pattern, desc, _why = pattern_of(measured)
            if _locked(measured, pattern):
                state["pattern"] = pattern
                state["desc"] = desc
    state["phase"] = "pass1"


def _step_pass1(state: dict) -> None:
    measured = state["measured"]
    p1, steps1, contra1 = believe(measured, prior(measured))
    initial, register1 = decide(measured, state["pattern"], p1, contra1, "pass1")
    state["p1"] = p1
    state["steps1"] = steps1
    state["initial"] = initial
    state["register1"] = register1
    state["phase"] = "reply"


def _step_reply(state: dict) -> None:
    if state["ask_used"]:
        state["phase"] = "pass2"
        return
    measured = state["measured"]
    asked = any(a["action"] == "VERIFY_WITH_CUSTOMER" for a in state["initial"])
    reply = reply_for(measured, state["pattern"], state["p1"], asked)
    evidence_requests = []
    if reply and reply["reply"] is not None:
        measured["reply"] = reply["reply"]
        evidence_requests.append(
            {
                "type": "customer_validation",
                "asked_after_step": 4,
                "assumed_response": f"{reply_text(reply)} Assumption: {reply['assumption']}.",
            }
        )
    elif reply and reply["kind"] == "dispute_keeps_R7":
        evidence_requests.append(
            {
                "type": "customer_validation",
                "asked_after_step": 4,
                "assumed_response": "Customer does not recognise the descriptor. The amount and the monthly gap still match, so R7 stands and the card is not blocked.",
            }
        )
    state["reply"] = reply
    state["evidence_requests"] = evidence_requests
    state["ask_used"] = True
    state["phase"] = "pass2"


def _step_pass2(state: dict) -> None:
    measured = state["measured"]
    p2, steps2, contra2 = believe(measured, prior(measured))
    final, register = decide(measured, state["pattern"], p2, contra2, "final")
    state["p2"] = p2
    state["steps2"] = steps2
    state["contra2"] = contra2
    state["final"] = final
    state["register"] = register
    state["phase"] = "prose"


def _step_prose(state: dict, allow_fallback: bool) -> None:
    measured = state["measured"]
    pattern = state["pattern"]
    desc = state["desc"]
    final = state["final"]
    reply = state["reply"]
    _kind, stop_text = stop_commit(state["p2"], _families(measured), measured["reply"], pattern)
    if state["fallback"]:
        stop_text += " Control gates used the deterministic fallback."
    point = _commitment(measured, pattern, [a["action"] for a in final])
    drafted = draft_summary(measured, pattern, desc, state["p2"], final, reply, allow_fallback=allow_fallback)
    summary, rewrite_used, summary_fallback = _ground(drafted["sentences"], state["rewrite_used"], allow_fallback)
    state["rewrite_used"] = rewrite_used
    state["fallback"] = state["fallback"] or summary_fallback
    state["tokens"] = int(drafted.get("tokens") or 0)
    language_fallback = bool(drafted["fallback"])
    exposure_for_sar = round(abs(measured["flagged"][2]), 2)
    sar = draft_sar(measured, final, desc, exposure_for_sar, [], allow_fallback=allow_fallback)
    state["tokens"] += int(sar.get("tokens") or 0)
    language_fallback = language_fallback or bool(sar.get("fallback"))
    if sar.get("sentences"):
        narrative, rewrite_used, sar_fallback = _ground(sar["sentences"], state["rewrite_used"], allow_fallback)
        state["rewrite_used"] = rewrite_used
        state["fallback"] = state["fallback"] or sar_fallback
        sar["narrative"] = narrative
    sar = {key: value for key, value in sar.items() if key not in {"sentences", "fallback", "tokens"}}
    if language_fallback:
        stop_text += " The summary used the evidence claims because the language-model key was not used."
    state["language_fallback"] = language_fallback
    result = build(
        state["case"],
        measured,
        pattern,
        desc,
        state["p1"],
        state["p2"],
        state["steps2"],
        state["initial"],
        final,
        state["register"],
        reply,
        state["evidence_requests"],
        stop_text,
        point,
        summary,
        sar,
        _counterfactuals(measured, pattern),
        written_to_graph=False,
    )
    result["answer"]["tool_calls"] = 8 + (1 if state["hop_used"] else 0)
    result["answer"]["tokens"] = state.get("tokens") or 0
    result["demo"]["approved"] = []
    result["demo"]["hop"] = state["hop_name"]
    result["demo"]["control_fallback"] = state["fallback"]
    result["demo"]["language_fallback"] = state.get("language_fallback", False)
    result["demo"]["why_not"] = state.get("why_not") or []
    state["result"] = result
    state["phase"] = "approval"


def _step_memory(state: dict) -> None:
    measured = state["measured"]
    result = state["result"]
    mem = write_and_read(
        state["case_id"],
        result["answer"],
        card_id=measured["case"]["card_id"],
        device=measured.get("profile") or "",
    )
    result["demo"]["memory_matched"] = mem["matched"]
    result["answer"]["case"]["graph_case_id"] = mem["graph_case_id"]
    if not mem["matched"]:
        result["answer"]["case"]["written_to_graph"] = False
        result["demo"]["memory_error"] = "read-back mismatch"
        state["phase"] = "memory"
        return
    result["answer"]["case"]["written_to_graph"] = mem["written_to_graph"]
    state["phase"] = "done"


def _step(state: dict, index, allow_fallback: bool) -> bool:
    """Run the current phase. Return True when the caller should hand the result back."""
    phase = state["phase"]
    if phase == "intake":
        _step_intake(state)
    elif phase == "pack":
        _step_pack(state, index)
    elif phase == "pattern":
        _step_pattern(state, allow_fallback)
    elif phase == "hop":
        _step_hop(state, index, allow_fallback)
    elif phase == "pass1":
        _step_pass1(state)
    elif phase == "reply":
        _step_reply(state)
    elif phase == "pass2":
        _step_pass2(state)
    elif phase == "prose":
        _step_prose(state, allow_fallback)
    elif phase == "approval":
        if _waiting(state["result"]):
            return True
        state["phase"] = "memory"
        return _step(state, index, allow_fallback)
    elif phase == "memory":
        _step_memory(state)
        if state["phase"] == "memory":
            return True
    return False


def _continue(state: dict, index, allow_fallback: bool, stop_after: str | None) -> dict:
    while state["phase"] != "done":
        running = state["phase"]
        pause = _step(state, index, allow_fallback)
        checkpoint.save(state)
        if stop_after and running == stop_after:
            return {"stopped_after": stop_after, "ask_used": state["ask_used"], "case_id": state["case_id"]}
        if pause:
            return state["result"]
    return state["result"]


def run(case: dict, index, *, allow_fallback: bool = True, stop_after: str | None = None) -> dict:
    case = open_case(case)
    return _continue(_fresh(case), index, allow_fallback, stop_after)


def resume(case_id: str, index, *, action: str | None = None, allow_fallback: bool = True) -> dict:
    state = checkpoint.load(case_id)
    if state is None:
        raise KeyError(case_id)
    if action:
        _approve(state, action)
        checkpoint.save(state)
    if state["phase"] == "done":
        return state["result"]
    return _continue(state, index, allow_fallback, None)
