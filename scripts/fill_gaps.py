"""Store policy vectors, device communities, and the exam-case edges."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "packages" / p) for p in ("graph", "community", "contracts")]
sys.path.insert(0, str(ROOT / "scripts"))

from community import build  # noqa: E402
from graph.private.local_index import load_index  # noqa: E402
from graph.private.vectors import NOTES, embed  # noqa: E402
from load_hhgoa import Savanna, env  # noqa: E402


def main() -> None:
    rows = build(load_index())
    print(f"communities {len(rows)}", flush=True)
    found = env()
    client = Savanna(found["TG_HOST"], found["TG_TOKEN"])
    client.ping()
    jobs = [
        """
USE GLOBAL
CREATE GLOBAL SCHEMA_CHANGE JOB add_community_attr {
  ALTER VERTEX BankCard ADD ATTRIBUTE (community_id STRING);
}
RUN GLOBAL SCHEMA_CHANGE JOB add_community_attr
""".strip(),
        """
USE GRAPH HHGOA
CREATE SCHEMA_CHANGE JOB add_policy_emb FOR GRAPH HHGOA {
  ALTER VERTEX PolicyNote ADD ATTRIBUTE (emb STRING);
}
RUN SCHEMA_CHANGE JOB add_policy_emb
""".strip(),
        """
USE GLOBAL
CREATE DIRECTED EDGE EXAM_TXN(FROM ExamCase, TO Transaction)
CREATE DIRECTED EDGE EXAM_DEVICE(FROM ExamCase, TO DeviceProfile)
CREATE DIRECTED EDGE EXAM_OTHER(FROM ExamCase, TO BankCard)
""".strip(),
        """
USE GLOBAL
CREATE GLOBAL SCHEMA_CHANGE JOB add_exam_edges {
  ADD EDGE EXAM_TXN TO GRAPH HHGOA;
  ADD EDGE EXAM_DEVICE TO GRAPH HHGOA;
  ADD EDGE EXAM_OTHER TO GRAPH HHGOA;
}
RUN GLOBAL SCHEMA_CHANGE JOB add_exam_edges
""".strip(),
    ]
    for job in jobs:
        try:
            print(client.gsql(job)[:220].replace("\n", " "), flush=True)
        except RuntimeError as exc:
            text = str(exc)
            if not any(word in text.lower() for word in ("already", "exists", "used by another", "conflict")):
                raise
            print(text[:220].replace("\n", " "), flush=True)
    notes = {
        note_id: {"body": {"value": body}, "emb": {"value": ",".join(str(v) for v in embed(body))}}
        for note_id, body in NOTES.items()
    }
    client.upsert({"vertices": {"PolicyNote": notes}})
    print(f"policy vectors {len(notes)}", flush=True)
    batch = {}
    written = 0
    for card_id, row in rows.items():
        batch[card_id] = {"community_id": {"value": row["community_id"]}}
        if len(batch) >= 2000:
            client.upsert({"vertices": {"BankCard": batch}})
            written += len(batch)
            print(f"community ids {written}", flush=True)
            batch = {}
    if batch:
        client.upsert({"vertices": {"BankCard": batch}})
        written += len(batch)
    print(f"community ids {written}", flush=True)
    text = (ROOT / "gsql" / "pack.gsql").read_text()
    statement = "USE GRAPH HHGOA\n" + text[text.index("CREATE OR REPLACE QUERY community_lookup") :].strip()
    statement += "\nINSTALL QUERY community_lookup"
    print(client.gsql(statement)[:200].replace("\n", " "), flush=True)
    print("gap fill finished", flush=True)


if __name__ == "__main__":
    main()
