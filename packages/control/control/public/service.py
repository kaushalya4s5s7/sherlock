"""Control gates. The fallback answers when Jev is not configured."""

def hop(state: dict) -> str:
    return "none"


def pattern_gate(state: dict) -> str:
    return "insufficient"


def sentences(items: list[dict]) -> list[dict]:
    return [item for item in items if item.get("ref")]
