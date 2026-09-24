"""Local graph index. Same facts the installed queries would return.

TigerGraph is the submission store. This index lets the desk run before a
cluster is up, and it is what tests use. Card ids are only emitted when they
appear in the case pack or the closed-case file.
"""

from __future__ import annotations

import csv
import pickle
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

def _repo() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "HHGOA_IEEE 2").is_dir():
            return parent
    raise FileNotFoundError("HHGOA_IEEE 2 dataset directory")


ROOT = _repo()
DATA = ROOT / "HHGOA_IEEE 2"
CACHE = ROOT / ".cache" / "graph_index.pkl"

TXN = tuple  # id, ts, amt, product, channel, addr, email, risk, customer, card1


def _f(value: str) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except ValueError:
        return None


def _profile(row: dict) -> str:
    parts = [row.get("DeviceInfo") or "", row.get("id_30") or "", row.get("id_31") or "", row.get("id_33") or ""]
    parts = [p.strip() for p in parts if p and p.strip()]
    return " | ".join(parts)


@dataclass
class ClosedCase:
    case_id: str
    customer_id: str
    card_id: str
    outcome: str
    pattern: str
    txn_ids: list[str]
    connected: list[str]
    exposure: float
    actions: str
    notes: str
    device: str = ""


@dataclass
class GraphIndex:
    txns: dict[str, TXN]
    by_card: dict[tuple[str, str], list[str]]
    identity: dict[str, tuple[str, str, str]]  # profile, id_15, id_23
    device_cards: dict[str, set[tuple[str, str]]]
    card_id_of: dict[tuple[str, str], str]
    valid_card_ids: set[str]
    valid_customers: set[str]
    closed: list[ClosedCase]
    closed_by_card: dict[str, list[int]]
    pack: list[dict]
    built_at: str = ""

    def history(self, customer: str, card1: str) -> list[TXN]:
        ids = self.by_card.get((customer, card1), [])
        rows = [self.txns[i] for i in ids]
        rows.sort(key=lambda t: t[1])
        return rows

    def card_ids_on_device(self, profile: str, skip: tuple[str, str]) -> list[str]:
        found = []
        for key in self.device_cards.get(profile, ()):
            if key == skip:
                continue
            cid = self.card_id_of.get(key)
            if cid and cid not in found:
                found.append(cid)
        return found


def _load_pack_and_cases() -> tuple[list[dict], list[ClosedCase], set[str], set[str], dict[str, str]]:
    pack = list(csv.DictReader(open(DATA / "case_pack.csv", newline="")))
    closed: list[ClosedCase] = []
    valid_cards: set[str] = set()
    valid_customers: set[str] = set()
    txn_to_card: dict[str, str] = {}
    for row in pack:
        valid_cards.add(row["card_id"])
        valid_customers.add(row["customer_id"])
        txn_to_card[row["flagged_txn_id"]] = row["card_id"]
    with open(DATA / "closed_cases_history.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            connected = [c for c in (row["connected_card_ids"] or "").split("|") if c]
            txn_ids = [t for t in (row["txn_ids"] or "").split("|") if t]
            valid_cards.add(row["card_id"])
            valid_cards.update(connected)
            valid_customers.add(row["customer_id"])
            if row["first_fraud_txn_id"]:
                txn_to_card[row["first_fraud_txn_id"]] = row["card_id"]
            closed.append(
                ClosedCase(
                    case_id=row["case_id"],
                    customer_id=row["customer_id"],
                    card_id=row["card_id"],
                    outcome=row["outcome"],
                    pattern=row["pattern"],
                    txn_ids=txn_ids,
                    connected=connected,
                    exposure=float(row["exposure_usd"] or 0),
                    actions=row["actions_taken"],
                    notes=(row["analyst_notes"] or "")[:400],
                )
            )
    return pack, closed, valid_cards, valid_customers, txn_to_card


def build_index() -> GraphIndex:
    pack, closed, valid_cards, valid_customers, txn_to_card = _load_pack_and_cases()
    txns: dict[str, TXN] = {}
    by_card: dict[tuple[str, str], list[str]] = defaultdict(list)
    print("indexing transactions…", flush=True)
    with open(DATA / "transactions.csv", newline="") as handle:
        for n, row in enumerate(csv.DictReader(handle), 1):
            card1 = row["card1"] or ""
            if not card1:
                continue
            tid = row["TransactionID"]
            item = (
                tid,
                row["ts"],
                float(row["TransactionAmt"] or 0),
                row["ProductCD"],
                row["channel"],
                row["addr1"] or "",
                row["P_emaildomain"] or "",
                _f(row["risk_score"]),
                row["customer_id"],
                card1,
            )
            txns[tid] = item
            by_card[(row["customer_id"], card1)].append(tid)
            if n % 200000 == 0:
                print(f"  {n:,} rows", flush=True)
    print("indexing identity…", flush=True)
    identity: dict[str, tuple[str, str, str]] = {}
    device_cards: dict[str, set[tuple[str, str]]] = defaultdict(set)
    with open(DATA / "identity.csv", newline="") as handle:
        for row in csv.DictReader(handle):
            tid = row["TransactionID"]
            txn = txns.get(tid)
            if not txn:
                continue
            profile = _profile(row)
            identity[tid] = (profile, (row.get("id_15") or "").strip(), (row.get("id_23") or "").strip())
            if profile:
                device_cards[profile].add((txn[8], txn[9]))
    card_id_of: dict[tuple[str, str], str] = {}
    for tid, card_id in txn_to_card.items():
        txn = txns.get(tid)
        if txn:
            card_id_of[(txn[8], txn[9])] = card_id
    for case in pack:
        txn = txns.get(case["flagged_txn_id"])
        if txn:
            card_id_of[(txn[8], txn[9])] = case["card_id"]
    closed_by_card: dict[str, list[int]] = defaultdict(list)
    for i, case in enumerate(closed):
        closed_by_card[case.card_id].append(i)
        first = txns.get(case.txn_ids[0]) if case.txn_ids else None
        if first and first[0] in identity:
            case.device = identity[first[0]][0]
    index = GraphIndex(
        txns=txns,
        by_card=dict(by_card),
        identity=identity,
        device_cards=dict(device_cards),
        card_id_of=card_id_of,
        valid_card_ids=valid_cards,
        valid_customers=valid_customers,
        closed=closed,
        closed_by_card=dict(closed_by_card),
        pack=pack,
        built_at=datetime.utcnow().isoformat(timespec="seconds") + "Z",
    )
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    with open(CACHE, "wb") as handle:
        pickle.dump(index, handle, protocol=pickle.HIGHEST_PROTOCOL)
    print(f"index ready: {len(txns):,} transactions, cached at {CACHE}", flush=True)
    return index


class _IndexPickle(pickle.Unpickler):
    """Older caches were written when this module was named fraud_agent.index."""

    def find_class(self, module: str, name: str):
        if module.startswith("fraud_agent"):
            module = "graph.private.local_index"
        return super().find_class(module, name)


def load_index() -> GraphIndex:
    if CACHE.exists():
        try:
            with open(CACHE, "rb") as handle:
                return _IndexPickle(handle).load()
        except (AttributeError, ModuleNotFoundError, pickle.UnpicklingError):
            pass
    return build_index()


if __name__ == "__main__":
    build_index()
