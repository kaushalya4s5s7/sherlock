"""One case, one path. Checkpoints come later. This module only orders the engines."""

from __future__ import annotations

from copy import deepcopy

from answer import build
from belief import believe, prior
from graph import measurement_pack
from intake import open_case
from language import draft_sar, draft_summary
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



def run(case: dict, index) -> dict:
    case = open_case(case)
    m = measurement_pack(case, index)
    pattern, desc, _why = pattern_of(m)
    p1, _steps1, contra1 = believe(m, prior(m))
    initial, _register1 = decide(m, pattern, p1, contra1, "pass1")
    asked = any(a["action"] == "VERIFY_WITH_CUSTOMER" for a in initial)
    reply = reply_for(m, pattern, p1, asked)
    evidence_requests = []
    if reply and reply["reply"] is not None:
        m["reply"] = reply["reply"]
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
    p2, steps2, contra2 = believe(m, prior(m))
    final, register = decide(m, pattern, p2, contra2, "final")
    families = sum(
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
    _kind, stop_text = stop_commit(p2, families, m["reply"], pattern)
    point = _commitment(m, pattern, [a["action"] for a in final])
    summary = draft_summary(m, pattern, desc, p2, final, reply)
    exposure_for_sar = round(abs(m["flagged"][2]), 2)
    sar = draft_sar(m, final, desc, exposure_for_sar, [])
    return build(
        case,
        m,
        pattern,
        desc,
        p1,
        p2,
        steps2,
        initial,
        final,
        register,
        reply,
        evidence_requests,
        stop_text,
        point,
        summary,
        sar,
        _counterfactuals(m, pattern),
    )
