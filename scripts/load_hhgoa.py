"""Create the HHGOA graph on Savanna and load the local exam files.

The sample graph Transaction_Fraud is left alone. Rows are upserted in
batches, so running this again continues after the last finished batch.
"""

from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "HHGOA_IEEE 2"
PROGRESS = ROOT / ".cache" / "hhgoa_load.json"
GRAPH = "HHGOA"
BATCH = 2000

VERTICES = [
    'CREATE VERTEX Customer(PRIMARY_ID id STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
    'CREATE VERTEX BankCard(PRIMARY_ID id STRING, customer_id STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
    "CREATE VERTEX Transaction(PRIMARY_ID id STRING, amount DOUBLE, ts STRING, product STRING, "
    'channel STRING, addr STRING, email STRING, risk_score DOUBLE, customer_id STRING, card1 STRING) '
    'WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
    'CREATE VERTEX DeviceProfile(PRIMARY_ID id STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
    "CREATE VERTEX ClosedCase(PRIMARY_ID id STRING, customer_id STRING, card_id STRING, outcome STRING, "
    'pattern STRING, exposure DOUBLE, actions STRING, notes STRING) WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
    "CREATE VERTEX ExamCase(PRIMARY_ID id STRING, verdict STRING, exposure_usd DOUBLE, pattern STRING) "
    'WITH PRIMARY_ID_AS_ATTRIBUTE="true"',
]
EDGES = [
    "CREATE DIRECTED EDGE BY_CUSTOMER(FROM Transaction, TO Customer)",
    "CREATE DIRECTED EDGE TXN_ON_CARD(FROM Transaction, TO BankCard)",
    "CREATE DIRECTED EDGE OWNS(FROM Customer, TO BankCard)",
    "CREATE DIRECTED EDGE FROM_DEVICE(FROM Transaction, TO DeviceProfile)",
    "CREATE DIRECTED EDGE CASE_ON_CARD(FROM ClosedCase, TO BankCard)",
    "CREATE DIRECTED EDGE ABOUT(FROM ClosedCase, TO Transaction)",
    "CREATE DIRECTED EDGE CONNECTED_TO(FROM ClosedCase, TO BankCard)",
    "CREATE DIRECTED EDGE ON_CARD(FROM ExamCase, TO BankCard)",
]
DROPS = [
    "DROP GRAPH HHGOA",
    "DROP EDGE ON_CARD",
    "DROP EDGE CONNECTED_TO",
    "DROP EDGE ABOUT",
    "DROP EDGE CASE_ON_CARD",
    "DROP EDGE FROM_DEVICE",
    "DROP EDGE OWNS",
    "DROP EDGE TXN_ON_CARD",
    "DROP EDGE BY_CUSTOMER",
    "DROP VERTEX ExamCase",
    "DROP VERTEX ClosedCase",
    "DROP VERTEX DeviceProfile",
    "DROP VERTEX Transaction",
    "DROP VERTEX Customer",
    "DROP VERTEX BankCard",
]
GRAPH_STMT = (
    "CREATE GRAPH HHGOA(Customer, BankCard, Transaction, DeviceProfile, ClosedCase, ExamCase, "
    "BY_CUSTOMER, TXN_ON_CARD, OWNS, FROM_DEVICE, CASE_ON_CARD, ABOUT, CONNECTED_TO, ON_CARD)"
)


def env() -> dict[str, str]:
    found = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if not line.strip() or line.strip().startswith("#") or "=" not in line:
            continue
        name, value = line.split("=", 1)
        found[name.strip()] = value.strip()
    return found


class Savanna:
    def __init__(self, host: str, token: str):
        self.host = host.rstrip("/")
        self.token = token

    def _send(self, method: str, path: str, body: bytes | None, content_type: str) -> str:
        request = Request(
            self.host + path,
            data=body,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Accept": "application/json",
                "Content-Type": content_type,
                "User-Agent": "tiger-task/1.0",
            },
            method=method,
        )
        last_error = ""
        for _attempt in range(8):
            try:
                with urlopen(request, timeout=120) as response:
                    return response.read().decode()
            except HTTPError as exc:
                detail = exc.read(400).decode(errors="replace")
                last_error = detail
                if "Auto start is not enabled" in detail:
                    raise SystemExit(
                        "Savanna is stopped and auto-start is off. Start the workspace and turn auto-start on, then run this again."
                    ) from exc
                if exc.code in {502, 503, 504} or "Starting workspace" in detail:
                    time.sleep(10)
                    continue
                raise RuntimeError(f"{exc.code} {path}: {detail[:300]}") from exc
            except URLError as exc:
                raise RuntimeError(str(exc.reason)) from exc
        raise RuntimeError(f"{path}: {last_error[:300]}")

    def ping(self) -> None:
        self._send("GET", "/restpp/echo", None, "application/json")

    def gsql(self, statement: str, *, ignore_missing: bool = False) -> str:
        try:
            raw = self._send("POST", "/gsql/v1/statements", statement.encode(), "text/plain")
        except RuntimeError as exc:
            text = str(exc).lower()
            if ignore_missing and any(phrase in text for phrase in ("does not exist", "not found", "cannot find", "could not be found", "no such")):
                return text
            if any(phrase in text for phrase in ("already exists", "existing")):
                return text
            raise
        if "Semantic Check Fails" in raw or raw.startswith("Failed"):
            lowered = raw.lower()
            if ignore_missing and any(phrase in lowered for phrase in ("does not exist", "not found", "cannot find", "could not be found")):
                return raw
            if "already" in lowered or "existing" in lowered:
                return raw
            raise RuntimeError(raw[:300])
        return raw

    def upsert(self, payload: dict) -> None:
        raw = self._send(
            "POST",
            f"/restpp/graph/{GRAPH}",
            json.dumps(payload).encode(),
            "application/json",
        )
        if '"error":true' in raw.replace(" ", ""):
            raise RuntimeError(raw[:300])


def _num(value: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _profile(row: dict) -> str:
    parts = [row.get("DeviceInfo") or "", row.get("id_30") or "", row.get("id_31") or "", row.get("id_33") or ""]
    return " | ".join(part.strip() for part in parts if part and part.strip())


def card_map() -> dict[tuple[str, str], str]:
    """Match a transaction's customer and card1 to a known card id."""
    known: dict[str, str] = {}
    cards: dict[tuple[str, str], str] = {}
    with (DATA / "case_pack.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            known[row["flagged_txn_id"]] = row["card_id"]
    with (DATA / "closed_cases_history.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            if row["first_fraud_txn_id"]:
                known[row["first_fraud_txn_id"]] = row["card_id"]
    with (DATA / "transactions.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            card_id = known.get(row["TransactionID"])
            card1 = row["card1"] or ""
            if card_id and card1:
                cards[(row["customer_id"], card1)] = card_id
    return cards


def _progress() -> dict:
    if PROGRESS.exists():
        return json.loads(PROGRESS.read_text())
    return {"schema": False, "transactions": 0, "identity": False, "cases": False}


def _save(progress: dict) -> None:
    PROGRESS.parent.mkdir(parents=True, exist_ok=True)
    PROGRESS.write_text(json.dumps(progress))


def schema(client: Savanna, progress: dict) -> None:
    if progress["schema"]:
        return
    for statement in DROPS:
        result = client.gsql(statement, ignore_missing=True)
        print(statement, result[:60].replace("\n", " "), flush=True)
    for statement in (*VERTICES, *EDGES, GRAPH_STMT):
        result = client.gsql(statement)
        print(statement.split("(")[0], result[:80].replace("\n", " "), flush=True)
    progress["schema"] = True
    _save(progress)


def load_transactions(client: Savanna, cards: dict[tuple[str, str], str], progress: dict) -> None:
    skip = progress["transactions"]
    batch_v: dict = {"Transaction": {}, "Customer": {}, "BankCard": {}}
    batch_e: dict = {"Transaction": {}}
    seen = 0
    with (DATA / "transactions.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            seen += 1
            if seen <= skip:
                continue
            card1 = row["card1"] or ""
            if not card1:
                continue
            tid = row["TransactionID"]
            customer = row["customer_id"]
            batch_v["Transaction"][tid] = {
                "amount": {"value": _num(row["TransactionAmt"])},
                "ts": {"value": row["ts"]},
                "product": {"value": row["ProductCD"]},
                "channel": {"value": row["channel"]},
                "addr": {"value": row["addr1"] or ""},
                "email": {"value": row["P_emaildomain"] or ""},
                "risk_score": {"value": _num(row["risk_score"])},
                "customer_id": {"value": customer},
                "card1": {"value": card1},
            }
            batch_v["Customer"][customer] = {}
            edges = {"BY_CUSTOMER": {"Customer": {customer: {}}}}
            card_id = cards.get((customer, card1))
            if card_id:
                batch_v["BankCard"][card_id] = {"customer_id": {"value": customer}}
                edges["TXN_ON_CARD"] = {"BankCard": {card_id: {}}}
                batch_e.setdefault("Customer", {}).setdefault(customer, {}).setdefault("OWNS", {}).setdefault("BankCard", {})[card_id] = {}
            batch_e["Transaction"][tid] = edges
            if len(batch_v["Transaction"]) >= BATCH:
                client.upsert({"vertices": batch_v, "edges": batch_e})
                progress["transactions"] = seen
                _save(progress)
                print(f"transactions {seen:,}", flush=True)
                batch_v = {"Transaction": {}, "Customer": {}, "BankCard": {}}
                batch_e = {"Transaction": {}}
    if batch_v["Transaction"]:
        client.upsert({"vertices": batch_v, "edges": batch_e})
        progress["transactions"] = seen
        _save(progress)
        print(f"transactions {seen:,}", flush=True)


def load_identity(client: Savanna, progress: dict) -> None:
    if progress["identity"]:
        return
    vertices = {"DeviceProfile": {}}
    edges = {"Transaction": {}}
    with (DATA / "identity.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            profile = _profile(row)
            if not profile:
                continue
            tid = row["TransactionID"]
            vertices["DeviceProfile"][profile] = {}
            edges["Transaction"][tid] = {"FROM_DEVICE": {"DeviceProfile": {profile: {}}}}
            if len(edges["Transaction"]) >= BATCH:
                client.upsert({"vertices": vertices, "edges": edges})
                vertices = {"DeviceProfile": {}}
                edges = {"Transaction": {}}
    if edges["Transaction"]:
        client.upsert({"vertices": vertices, "edges": edges})
    progress["identity"] = True
    _save(progress)
    print("identity loaded", flush=True)


def load_cases(client: Savanna, progress: dict) -> None:
    if progress["cases"]:
        return
    vertices = {"ClosedCase": {}, "BankCard": {}, "Customer": {}}
    edges = {"ClosedCase": {}, "Customer": {}}
    with (DATA / "closed_cases_history.csv").open(newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = row["case_id"]
            card_id = row["card_id"]
            customer = row["customer_id"]
            vertices["ClosedCase"][case_id] = {
                "customer_id": {"value": customer},
                "card_id": {"value": card_id},
                "outcome": {"value": row["outcome"]},
                "pattern": {"value": row["pattern"]},
                "exposure": {"value": _num(row["exposure_usd"])},
                "actions": {"value": (row["actions_taken"] or "")[:200]},
                "notes": {"value": (row["analyst_notes"] or "")[:400]},
            }
            vertices["BankCard"][card_id] = {"customer_id": {"value": customer}}
            vertices["Customer"][customer] = {}
            case_edges = {
                "CASE_ON_CARD": {"BankCard": {card_id: {}}},
            }
            if row["first_fraud_txn_id"]:
                case_edges["ABOUT"] = {"Transaction": {row["first_fraud_txn_id"]: {}}}
            connected = {}
            for other in (row["connected_card_ids"] or "").split("|"):
                other = other.strip()
                if other:
                    vertices["BankCard"].setdefault(other, {})
                    connected[other] = {}
            if connected:
                case_edges["CONNECTED_TO"] = {"BankCard": connected}
            edges["ClosedCase"][case_id] = case_edges
            edges["Customer"].setdefault(customer, {}).setdefault("OWNS", {}).setdefault("BankCard", {})[card_id] = {}
            if len(vertices["ClosedCase"]) >= BATCH:
                client.upsert({"vertices": vertices, "edges": edges})
                vertices = {"ClosedCase": {}, "BankCard": {}, "Customer": {}}
                edges = {"ClosedCase": {}, "Customer": {}}
    if vertices["ClosedCase"]:
        client.upsert({"vertices": vertices, "edges": edges})
    progress["cases"] = True
    _save(progress)
    print("closed cases loaded", flush=True)


def main() -> None:
    found = env()
    client = Savanna(found["TG_HOST"], found["TG_TOKEN"])
    client.ping()
    progress = _progress()
    schema(client, progress)
    print("mapping cards…", flush=True)
    cards = card_map()
    print(f"{len(cards):,} known cards", flush=True)
    load_transactions(client, cards, progress)
    load_identity(client, progress)
    load_cases(client, progress)
    print("HHGOA load finished", flush=True)


if __name__ == "__main__":
    os.chdir(ROOT)
    main()
