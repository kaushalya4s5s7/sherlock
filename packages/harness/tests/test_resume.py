from graph import GraphIndex
from harness import resume, run
from harness.private import checkpoint
from memory.public import service as memory_service


def _index():
    txn = ("T1", "2016-11-01 00:00:00", 10.0, "C", "online", "1", "a.com", 0.2, "C1", "k1")
    return GraphIndex(
        txns={"T1": txn},
        by_card={("C1", "k1"): ["T1"]},
        identity={},
        device_cards={},
        card_id_of={},
        valid_card_ids=set(),
        valid_customers={"C1"},
        closed=[],
        closed_by_card={},
        pack=[],
    )


def _case():
    return {
        "case_id": "HHG-001",
        "flagged_txn_id": "T1",
        "card_id": "C1-K1",
        "customer_id": "C1",
        "trigger_type": "risk_score",
        "trigger_text": "",
        "risk_score": "0.2",
    }


def _isolate(tmp_path, monkeypatch):
    monkeypatch.setattr(checkpoint, "_path", lambda: tmp_path / "checkpoints.pkl")
    monkeypatch.setattr(memory_service, "_store_path", lambda: tmp_path / "memory.json")


def test_crash_after_pass1_asks_once(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    calls = {"n": 0}
    from harness.public import service as harness_service

    original = harness_service.reply_for

    def counted(*args, **kwargs):
        calls["n"] += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(harness_service, "reply_for", counted)
    index = _index()
    stopped = run(_case(), index, stop_after="pass1")
    assert stopped["ask_used"] is False
    assert calls["n"] == 0

    parked = resume("HHG-001", index)
    assert calls["n"] == 1
    assert parked["demo"]["approval"] == "pending"
    waiting = [a["action"] for a in parked["answer"]["next_best_actions"]["final"] if a["route"] != "auto"]
    assert waiting

    finished = resume("HHG-001", index, action=waiting[0])
    assert calls["n"] == 1
    assert waiting[0] in finished["demo"]["approved"]
    assert finished["answer"]["case"]["written_to_graph"] is False
    assert finished["demo"]["memory_matched"] is True

    again = resume("HHG-001", index)
    assert calls["n"] == 1
    assert again["answer"]["case"]["graph_case_id"] == "EXAM-HHG-001"


def test_approve_rejects_an_action_outside_final(tmp_path, monkeypatch):
    _isolate(tmp_path, monkeypatch)
    index = _index()
    run(_case(), index, stop_after="pass1")
    resume("HHG-001", index)
    try:
        resume("HHG-001", index, action="BLOCK_ALL_CARDS")
    except ValueError as exc:
        assert "not waiting" in str(exc)
    else:
        raise AssertionError("expected the approval to be rejected")
