from control import hop, pattern_gate, sentences


def test_hop_fallback_is_none():
    result = hop({"shared_device": False})
    assert result["choice"] == "none"
    assert result["query"] == "none"
    assert result["fallback"] is True
    assert set(result["probabilities"]) == {
        "device_component",
        "community",
        "prior_cases",
        "policy_text",
        "none",
    }


def test_pattern_gate_fallback_is_insufficient():
    result = pattern_gate({"pattern": "none"})
    assert result["label"] == "insufficient"
    assert result["fallback"] is True
    assert result["why_not"]


def test_sentences_keep_only_a_ref():
    result = sentences(
        [
            {"text": "The card was used online.", "ref": "query:card_history", "claim": "online"},
            {"text": "Invented detail.", "claim": "Invented detail."},
        ]
    )
    assert result["fallback"] is True
    assert [row["text"] for row in result["kept"]] == ["The card was used online."]
    assert result["rejected"][0]["supported"] is False


def test_missing_jev_refuses_without_fallback():
    try:
        hop({}, allow_fallback=False)
    except RuntimeError as exc:
        assert "Jev" in str(exc)
    else:
        raise AssertionError("expected Jev to be required")
