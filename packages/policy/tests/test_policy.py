"""Policy is a pure function. These lock the rules a judge will score."""

from policy import decide


def _m(**over):
    base = {
        "testing": False,
        "testing_txns": [],
        "cleared_over_100": False,
        "structuring": False,
        "structuring_txns": [],
        "samsung": False,
        "shared_confirmed": False,
        "connected": [],
        "recurring": False,
        "reply": None,
        "trigger": "risk_score",
        "report": "",
        "new_device": False,
        "proxy": False,
        "new_region": False,
        "home": True,
        "trip": False,
        "similar": [],
        "burst": [],
        "prior_n": 4,
        "flagged": ("T1", "2016-11-01 12:00:00", 80.0, "W", "in_person", "444", "", 0.4, "C1", "1"),
        "case": {
            "case_id": "HHG-001",
            "card_id": "C1-K1",
            "customer_id": "C1",
            "flagged_txn_id": "T1",
        },
    }
    base.update(over)
    return base


def names(actions):
    return [a["action"] for a in actions]


def test_subscription_dispute_does_not_block():
    m = _m(recurring=True, trigger="customer_report", report="I don't recognize this charge")
    actions, register = decide(m, "none", 0.42, False, "final")
    got = names(actions)
    assert "BLOCK_CARD" not in got
    assert "FILE_REPORT" not in got
    assert "VERIFY_WITH_CUSTOMER" in got
    assert "WARN_CUSTOMER" in got
    assert next(r for r in register if r["rule"] == "R7")["fired"]


def test_card_testing_declines_and_blocks_only_after_a_large_clear():
    small = ("T1", "2016-11-01 12:00:00", 2.0, "H", "online", "", "", 0.8, "C1", "1")
    m = _m(testing=True, testing_txns=[small, small, small], flagged=small)
    actions, _ = decide(m, "card_testing", 0.9, False, "pass1")
    got = names(actions)
    assert "DECLINE_TRANSACTION" in got
    assert "STEP_UP_AUTH" in got
    assert "BLOCK_CARD" not in got
    m["cleared_over_100"] = True
    actions, _ = decide(m, "card_testing", 0.9, False, "pass1")
    assert "BLOCK_CARD" in names(actions)


def test_block_route_flips_at_2500():
    low = ("T1", "2016-11-01 12:00:00", 2500.0, "H", "online", "", "", 0.9, "C1", "1")
    m = _m(flagged=low, burst=[low], reply="deny", new_device=True, proxy=True)
    actions, _ = decide(m, "card_not_present_fraud", 0.9, False, "final")
    block = next(a for a in actions if a["action"] == "BLOCK_CARD")
    assert block["route"] == "L1"
    high = ("T1", "2016-11-01 12:00:00", 2500.01, "H", "online", "", "", 0.9, "C1", "1")
    m["flagged"] = high
    m["burst"] = [high]
    actions, _ = decide(m, "card_not_present_fraud", 0.9, False, "final")
    block = next(a for a in actions if a["action"] == "BLOCK_CARD")
    assert block["route"] == "L2"


def test_confirm_closes_without_a_block():
    m = _m(reply="confirm", home=True, new_region=False)
    actions, register = decide(m, "none", 0.22, False, "final")
    assert names(actions)[0] == "CLOSE_NO_FRAUD"
    assert "BLOCK_CARD" not in names(actions)
    assert next(r for r in register if r["rule"] == "R3")["fired"]
