import argparse
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

from recon.core import EMPTY_HEAD, Transaction, append_event, money_to_cents, reconcile, verify_audit


def load_transaction(record: dict) -> Transaction:
    # keep the input amounts as text until they are converted to whole cents
    return Transaction(
        transaction_id=record["id"],
        reference=record["reference"],
        amount_cents=money_to_cents(record["amount"]),
        booking_date=date.fromisoformat(record["date"]),
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the four starter reconciliation cases")
    parser.add_argument("--out", type=Path, default=Path("output/demo"))
    args = parser.parse_args()

    # keep a previous run intact rather than replacing its audit history
    if args.out.exists():
        parser.error("output folder already exists; choose another --out folder")
    args.out.mkdir(parents=True)
    cases_path = Path(__file__).parent / "data" / "cases.json"
    cases = json.loads(cases_path.read_text())
    audit_path = args.out / "audit.jsonl"
    head = EMPTY_HEAD
    results = []

    for case in cases:
        ledger = [load_transaction(record) for record in case["ledger"]]
        bank = [load_transaction(record) for record in case["bank"]]
        head = append_event(audit_path, case["id"], "records_loaded", {
            "ledger": [record.to_dict() for record in ledger],
            "bank": [record.to_dict() for record in bank],
        })

        # retain the comparisons as well as the final outcome
        comparisons = [{
            "ledger_id": left.transaction_id,
            "bank_id": right.transaction_id,
            "amount_difference_cents": right.amount_cents - left.amount_cents,
            "date_difference_days": (right.booking_date - left.booking_date).days,
            "same_reference": left.reference == right.reference,
        } for left in ledger for right in bank]
        head = append_event(audit_path, case["id"], "records_compared", {"comparisons": comparisons})
        decisions = [asdict(decision) for decision in reconcile(ledger, bank)]
        head = append_event(audit_path, case["id"], "decision_recorded", {"decisions": decisions})
        results.append({"case_id": case["id"], "decisions": decisions})
        print(f'{case["id"]}: {decisions[0]["status"]} ({decisions[0]["reason"]})')

    # the local head file is a demo reference, not a secure external checkpoint
    (args.out / "audit_head.txt").write_text(head + "\n")
    (args.out / "results.json").write_text(json.dumps(results, indent=2))
    print(f"audit chain valid: {verify_audit(audit_path, head)}")
    print(f"files: {args.out}")


if __name__ == "__main__":
    main()
