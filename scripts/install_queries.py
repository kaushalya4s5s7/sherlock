"""Install the measurement queries and the policy notes on HHGOA.

The local index stays the test path. This script is what turns the
submission path on: after it finishes, the desk calls these query names.
"""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from load_hhgoa import DATA, Savanna, env  # noqa: E402

NOTES = {
    "policy_default": (
        "These are the patterns the bank's analysts recognize. They are not the only patterns in the data. "
        "Noticing activity that fits none of them, and describing it, is part of the investigation."
    ),
    "policy_shared_device": (
        "The known patterns are not the only ones in the data. "
        "A device profile shared across many cards is worth a look, and some cases are solved only by asking what happened on other cards."
    ),
    "rule_r1": "One weak signal and a fraud chance under 70 percent means ask the customer or send a code before any block.",
    "rule_r6": "A shared device is a case, a report, and a watch on the other cards only when those other cards are tied to fraud.",
    "rule_r7": "A customer dispute that matches a regular charge is a warning and an open case. It is not a block.",
    "rule_r8": "When the case is still unsure and the money at risk is over $500, send it to an analyst.",
    "pattern_card_testing": "Three or more online charges under $5 inside an hour, then a larger purchase, is card testing.",
    "pattern_undocumented": "A shape the five named patterns do not cover stays undocumented. Describe it. Do not rename it.",
}


def _queries() -> list[tuple[str, str]]:
    text = (ROOT / "gsql" / "pack.gsql").read_text()
    chunks = []
    current: list[str] = []
    name = ""
    for line in text.splitlines():
        if line.startswith("CREATE OR REPLACE QUERY "):
            if current and name:
                chunks.append((name, "\n".join(current)))
            name = line.split("(", 1)[0].split()[-1]
            current = [line]
        elif current:
            current.append(line)
    if current and name:
        chunks.append((name, "\n".join(current)))
    return chunks


def _upsert(client: Savanna, vertices: dict) -> None:
    client.upsert({"vertices": vertices})


def load_flags(client: Savanna) -> None:
    batch: dict = {}
    seen = 0
    with (DATA / "identity.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            batch[row["TransactionID"]] = {
                "id_15": {"value": row.get("id_15") or ""},
                "id_23": {"value": row.get("id_23") or ""},
            }
            if len(batch) >= 2000:
                _upsert(client, {"IdentityFlag": batch})
                seen += len(batch)
                print(f"identity flags {seen:,}", flush=True)
                batch = {}
    if batch:
        _upsert(client, {"IdentityFlag": batch})
        seen += len(batch)
    print(f"identity flags {seen:,}", flush=True)


def main() -> None:
    found = env()
    client = Savanna(found["TG_HOST"], found["TG_TOKEN"])
    client.ping()
    if "--queries-only" not in sys.argv:
        for statement in (
            'CREATE VERTEX IdentityFlag(PRIMARY_ID id STRING, id_15 STRING, id_23 STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
            'CREATE VERTEX PolicyNote(PRIMARY_ID id STRING, body STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
        ):
            try:
                print(client.gsql(statement)[:120].replace("\n", " "), flush=True)
            except RuntimeError as exc:
                text = str(exc)
                if "used by another object" not in text and "already" not in text.lower():
                    raise
                print(text[:120].replace("\n", " "), flush=True)
        job = """
USE GRAPH HHGOA
CREATE SCHEMA_CHANGE JOB add_exam_notes FOR GRAPH HHGOA {
  ADD VERTEX IdentityFlag(PRIMARY_ID id STRING, id_15 STRING, id_23 STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true";
  ADD VERTEX PolicyNote(PRIMARY_ID id STRING, body STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true";
}
RUN SCHEMA_CHANGE JOB add_exam_notes
""".strip()
        try:
            print(client.gsql(job)[:200].replace("\n", " "), flush=True)
        except RuntimeError as exc:
            text = str(exc)
            if "already" not in text.lower() and "exists" not in text.lower():
                raise
            print(text[:200].replace("\n", " "), flush=True)
        load_flags(client)
        notes = {
            note_id: {"body": {"value": body}}
            for note_id, body in NOTES.items()
        }
        _upsert(client, {"PolicyNote": notes})
        print(f"policy notes {len(notes)}", flush=True)
    for name, body in _queries():
        statement = f"USE GRAPH HHGOA\n{body}\nINSTALL QUERY {name}"
        print(f"install {name}", flush=True)
        result = client.gsql(statement)
        print(result[:180].replace("\n", " "), flush=True)
        if "Type Check Error" in result or "Semantic Check Fails" in result or "Saved as draft" in result:
            raise RuntimeError(result[:400])
    marker = ROOT / ".cache" / "queries_installed"
    marker.parent.mkdir(parents=True, exist_ok=True)
    marker.write_text(json.dumps({"graph": "HHGOA", "queries": [name for name, _ in _queries()]}))
    print("queries installed", flush=True)


if __name__ == "__main__":
    main()
