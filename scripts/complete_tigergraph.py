"""Turn the three partial TigerGraph pieces into installed graph features.

Adds a native vector attribute on the policy notes, installs the vector
search query and the shared-device community walk, and loads the note vectors.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "packages" / "graph"))

from install_queries import _queries  # noqa: E402
from load_hhgoa import Savanna, env  # noqa: E402
from graph.private.vectors import NOTES, embed  # noqa: E402


def _ignore(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in ("already", "exists", "conflict", "used by another"))


def main() -> None:
    found = env()
    client = Savanna(found["TG_HOST"], found["TG_TOKEN"])
    client.ping()
    job = """
USE GRAPH HHGOA
CREATE SCHEMA_CHANGE JOB add_policy_vec FOR GRAPH HHGOA {
  ALTER VERTEX PolicyNote ADD VECTOR ATTRIBUTE vec(DIMENSION=32, METRIC="COSINE");
}
RUN SCHEMA_CHANGE JOB add_policy_vec
""".strip()
    try:
        print(client.gsql(job)[:240].replace("\n", " "), flush=True)
    except RuntimeError as exc:
        text = str(exc)
        if not _ignore(text):
            raise
        print(text[:240].replace("\n", " "), flush=True)
    notes = {}
    for note_id, body in NOTES.items():
        notes[note_id] = {
            "body": {"value": body},
            "vec": {"value": embed(body)},
        }
    client.upsert({"vertices": {"PolicyNote": notes}})
    print(f"policy vectors {len(notes)}", flush=True)
    wanted = {"card_community", "policy_vector_search"}
    for name, body in _queries():
        if name not in wanted:
            continue
        statement = f"USE GRAPH HHGOA\n{body}\nINSTALL QUERY {name}"
        print(f"install {name}", flush=True)
        result = client.gsql(statement)
        print(result[:220].replace("\n", " "), flush=True)
        if "Type Check Error" in result or "Semantic Check Fails" in result or "Saved as draft" in result:
            raise RuntimeError(result[:500])
    print("tigergraph features installed", flush=True)


if __name__ == "__main__":
    main()
