from belief import believe


def _quiet():
    return {
        "testing": False,
        "structuring": False,
        "samsung": False,
        "new_device": False,
        "proxy": False,
        "shared_confirmed": False,
        "new_region": False,
        "trip": False,
        "home": False,
        "recurring": False,
        "prior_n": 0,
        "reply": None,
    }


def test_prior_from_memory_moves_p_and_is_labeled():
    base, _, _ = believe(_quiet(), 0.5)
    moved = dict(_quiet())
    moved["memory_rate"] = 0.9
    moved["memory_n"] = 5
    p, steps, _ = believe(moved, 0.5)
    assert p > base
    assert any(step["name"] == "prior from memory" for step in steps)


def test_one_neighbor_is_not_a_memory_prior():
    moved = dict(_quiet())
    moved["memory_rate"] = 0.9
    moved["memory_n"] = 1
    _, steps, _ = believe(moved, 0.5)
    assert all(step["name"] != "prior from memory" for step in steps)
