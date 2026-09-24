from memory.public import service
from memory.public.service import recall, same_case, write_and_read


def _answer(verdict="uncertain", exposure=12.5):
    return {
        "case": {
            "verdict": verdict,
            "exposure_usd": exposure,
            "pattern": "none",
        },
        "next_best_actions": {"final": [{"action": "MONITOR_CARD"}]},
        "sar": {"file": False},
    }


def test_same_case_rejects_a_different_exposure():
    written = {"verdict": "uncertain", "exposure": 12.5}
    assert same_case(written, {"verdict": "uncertain", "exposure": 12.5}) is True
    assert same_case(written, {"verdict": "fraud", "exposure": 12.5}) is False
    assert same_case(written, {"verdict": "uncertain", "exposure": 99}) is False


def test_local_readback_does_not_set_the_graph_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_store_path", lambda: tmp_path / "memory.json")
    first = write_and_read("HHG-001", _answer(), card_id="C1-K1", device="phone")
    second = write_and_read("HHG-001", _answer(verdict="fraud", exposure=40), card_id="C1-K1", device="phone")
    assert first["matched"] is True
    assert first["written_to_graph"] is False
    assert second["graph_case_id"] == "EXAM-HHG-001"
    assert second["matched"] is True
    found = recall("C1-K1", "phone")
    assert [row["case_id"] for row in found] == ["EXAM-HHG-001"]
    assert found[0]["outcome"] == "confirmed_fraud"


def test_readback_mismatch_refuses_the_flag(tmp_path, monkeypatch):
    monkeypatch.setattr(service, "_store_path", lambda: tmp_path / "memory.json")
    monkeypatch.setattr(service, "_read", lambda case_id: {"verdict": "fraud", "exposure": 1})
    result = write_and_read("HHG-002", _answer())
    assert result["matched"] is False
    assert result["written_to_graph"] is False
