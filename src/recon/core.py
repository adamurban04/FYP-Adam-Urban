from collections import Counter
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
import hashlib
import json


# transaction records and exact money values

def money_to_cents(text: str) -> int:
    # parse the original decimal text so binary floating point is never involved
    if not isinstance(text, str):
        raise TypeError("amount must be supplied as text")
    try:
        amount = Decimal(text)
    except InvalidOperation as error:
        raise ValueError("invalid amount") from error
    if not amount.is_finite():
        raise ValueError("amount must be finite")
    # use an exact fraction so large values cannot be rounded by decimal context
    numerator, denominator = amount.as_integer_ratio()
    cents, remainder = divmod(numerator * 100, denominator)
    if remainder:
        raise ValueError("amount has fractions of a cent")
    return cents


@dataclass(frozen=True)
class Transaction:
    # these first cases all use one organisation and EUR
    transaction_id: str
    reference: str
    amount_cents: int
    booking_date: date

    def to_dict(self) -> dict:
        # use a readable date in the audit file
        return {
            "transaction_id": self.transaction_id,
            "reference": self.reference,
            "amount_cents": self.amount_cents,
            "booking_date": self.booking_date.isoformat(),
        }


@dataclass(frozen=True)
class Decision:
    ledger_id: str
    status: str
    candidate_ids: tuple[str, ...]
    reason: str


# strict candidates and allocation checks

def find_exact_matches(
    ledger: Transaction, bank_records: list[Transaction]
) -> list[Transaction]:
    # a missing reference is not enough for this strict matching rule
    if not ledger.reference.strip():
        return []
    return [
        bank for bank in bank_records
        if bank.reference == ledger.reference
        and bank.amount_cents == ledger.amount_cents
        and bank.booking_date == ledger.booking_date
    ]


def reconcile(
    ledger_records: list[Transaction], bank_records: list[Transaction]
) -> list[Decision]:
    # duplicate source ids would make candidate tracking ambiguous
    for records in [ledger_records, bank_records]:
        ids = [record.transaction_id for record in records]
        if len(ids) != len(set(ids)):
            raise ValueError("transaction ids must be unique within each source")

    candidates = {
        ledger.transaction_id: find_exact_matches(ledger, bank_records)
        for ledger in ledger_records
    }

    # count all claims before accepting anything so ledger order cannot assign
    # a shared bank record to whichever ledger entry happens to appear first
    demand = Counter(
        bank.transaction_id
        for records in candidates.values()
        for bank in records
    )
    decisions = []
    for ledger in ledger_records:
        ids = tuple(sorted(bank.transaction_id for bank in candidates[ledger.transaction_id]))
        if len(ids) == 1 and demand[ids[0]] == 1:
            status, reason = "match", "one unique exact candidate"
        elif len(ids) > 1:
            status, reason = "review", "multiple exact candidates"
        elif ids:
            status, reason = "review", "bank record also fits another ledger entry"
        else:
            status, reason = "review", "no exact candidate"
        decisions.append(Decision(ledger.transaction_id, status, ids, reason))
    return decisions


# local audit events and integrity checks

EMPTY_HEAD = "0" * 64


def event_hash(event: dict) -> str:
    # hash the content in a stable order and leave out the hash field itself
    content = {key: value for key, value in event.items() if key != "hash"}
    encoded = json.dumps(content, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def read_events(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def verify_audit(path: Path, expected_head: str | None = None) -> bool:
    # a separately trusted head is needed to detect removal of the last events
    previous = EMPTY_HEAD
    try:
        for sequence, event in enumerate(read_events(path), start=1):
            if not isinstance(event, dict):
                return False
            if event.get("sequence") != sequence or event.get("previous_hash") != previous:
                return False
            if event.get("hash") != event_hash(event):
                return False
            previous = event["hash"]
    except (ValueError, TypeError, OSError):
        return False
    return expected_head is None or previous == expected_head


def append_event(path: Path, case_id: str, event_type: str, data: dict) -> str:
    # check the existing file before extending it rather than repairing it silently
    if not verify_audit(path):
        raise ValueError("existing audit chain is invalid")
    events = read_events(path)
    event = {
        "sequence": len(events) + 1,
        "case_id": case_id,
        "event_type": event_type,
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "data": data,
        "previous_hash": events[-1]["hash"] if events else EMPTY_HEAD,
    }
    event["hash"] = event_hash(event)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(event, sort_keys=True) + "\n")
    return event["hash"]
