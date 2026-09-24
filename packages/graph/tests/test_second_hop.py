from graph import GraphIndex, second_hop


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
    return {"case_id": "HHG-001", "flagged_txn_id": "T1", "card_id": "C1-K1"}


def test_component_without_a_device_is_an_empty_claim():
    result = second_hop("component_cards", _case(), _index())
    assert result["entity_ids"] == []
    assert result["ref"] == "query:component_cards"
    assert "No device profile" in result["claim"]


def test_community_without_an_id_is_an_empty_claim():
    result = second_hop("community_lookup", _case(), _index())
    assert result["entity_ids"] == []
    assert "No community id" in result["claim"]


def test_policy_passage_is_a_document():
    result = second_hop("policy_passage", _case(), _index())
    assert result["source"] == "document"
    assert result["entity_ids"] == []
    assert result["claim"]
