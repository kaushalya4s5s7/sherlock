from __future__ import annotations

def commit(p: float, families: int, reply: str | None, pattern: str) -> tuple[str, str]:
    if reply in {"deny", "confirm"}:
        return "verification_resolved", "The simulated reply settled the case, so another lookup would not change the action."
    if (p >= 0.85 or p <= 0.15) and families >= 2:
        return "high_confidence", "Probability is outside 0.15–0.85 and at least two evidence families agree."
    if pattern == "undocumented":
        return "high_confidence", "The undocumented pattern is a hard stop: open, report, escalate, and write the shape in our own words."
    return "diminishing_returns", "Further lookups would not change the action list."
