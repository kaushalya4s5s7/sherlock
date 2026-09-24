from language.public import service
from language.public.service import draft_summary


def _measured():
    return {
        "case": {"case_id": "HHG-001", "card_id": "C1-K1", "customer_id": "C1"},
        "flagged": ("T1", "2016-11-01 00:00:00", 10.0, "C", "online", "1", "a.com", 0.2, "C1", "k1"),
        "profile": "",
        "connected": [],
        "structuring_txns": [],
        "testing_txns": [],
    }


def test_missing_key_uses_the_claims():
    drafted = draft_summary(_measured(), "none", "No fraud pattern.", 0.2, [{"action": "MONITOR_CARD"}], None)
    assert drafted["fallback"] is True
    assert drafted["tokens"] == 0
    refs = {row["ref"] for row in drafted["sentences"]}
    assert "query:card_history" in refs
    assert "policy:final_actions" in refs
    assert all(row["claim"] for row in drafted["sentences"])


def test_missing_key_refuses_without_fallback():
    try:
        draft_summary(_measured(), "none", "No fraud pattern.", 0.2, [], None, allow_fallback=False)
    except RuntimeError as exc:
        assert "language model" in str(exc)
    else:
        raise AssertionError("expected the language model to be required")


def test_model_text_keeps_every_ref(monkeypatch):
    claims_holder = {}

    def fake_complete(cfg, messages):
        import json

        body = json.loads(messages[1]["content"])
        claims_holder["n"] = len(body["sentences"])
        rewritten = [{"ref": row["ref"], "text": "Reworded. " + row["text"]} for row in body["sentences"]]
        return json.dumps({"sentences": rewritten}), 40

    monkeypatch.setattr(service, "model", lambda: {"key": "test", "base_url": "http://example/v1", "name": "test-model"})
    monkeypatch.setattr(service, "complete", fake_complete)
    drafted = draft_summary(_measured(), "none", "No fraud pattern.", 0.2, [{"action": "MONITOR_CARD"}], None)
    assert drafted["fallback"] is False
    assert drafted["tokens"] == 40
    assert len(drafted["sentences"]) == claims_holder["n"]
    assert all(row["text"].startswith("Reworded.") for row in drafted["sentences"])
    assert all(row["claim"] for row in drafted["sentences"])
