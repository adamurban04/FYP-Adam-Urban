import json
import tempfile
import unittest
from dataclasses import replace
from datetime import date
from pathlib import Path

from recon.core import Transaction, append_event, money_to_cents, reconcile, verify_audit


class MoneyTests(unittest.TestCase):
    def test_decimal_amounts_convert_exactly(self):
        # values that can be awkward in floating point should stay exact here
        self.assertEqual(money_to_cents("0.10") + money_to_cents("0.20"), 30)
        self.assertEqual(money_to_cents("2450.00"), 245000)
        self.assertEqual(
            money_to_cents("1234567890123456789012345678.99"),
            123456789012345678901234567899,
        )

    def test_subcent_amount_is_rejected(self):
        # do not silently round an input that the current money model cannot hold
        with self.assertRaises(ValueError):
            money_to_cents("1.001")

    def test_non_finite_amount_is_rejected(self):
        for value in ["NaN", "Infinity", "-Infinity"]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                money_to_cents(value)


class MatchingTests(unittest.TestCase):
    def setUp(self):
        # use one ordinary payment and vary only the part each test investigates
        self.ledger = Transaction("L001", "INV-1042", 245000, date(2026, 3, 12))
        self.bank = replace(self.ledger, transaction_id="B001")

    def test_unique_exact_match_is_matched(self):
        result = reconcile([self.ledger], [self.bank])[0]
        self.assertEqual(result.status, "match")
        self.assertEqual(result.candidate_ids, ("B001",))

    def test_competing_candidates_require_review(self):
        rival = replace(self.bank, transaction_id="B002")
        # neither candidate order should hide the ambiguity
        for records in [[self.bank, rival], [rival, self.bank]]:
            result = reconcile([self.ledger], records)[0]
            self.assertEqual(result.status, "review")
            self.assertEqual(result.candidate_ids, ("B001", "B002"))

    def test_amount_difference_requires_review(self):
        bank = replace(self.bank, amount_cents=self.bank.amount_cents + 1)
        self.assertEqual(reconcile([self.ledger], [bank])[0].status, "review")

    def test_missing_candidate_requires_review(self):
        self.assertEqual(reconcile([self.ledger], [])[0].status, "review")

    def test_bank_transaction_cannot_be_reused(self):
        second_ledger = replace(self.ledger, transaction_id="L002")
        # both claims need review rather than giving the first ledger priority
        for records in [[self.ledger, second_ledger], [second_ledger, self.ledger]]:
            results = reconcile(records, [self.bank])
            self.assertTrue(all(result.status == "review" for result in results))


class AuditTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "audit.jsonl"

    def test_audit_chain_verifies_after_append(self):
        append_event(self.path, "REC-1", "records_loaded", {"amount_cents": 185000})
        head = append_event(self.path, "REC-1", "decision_recorded", {"status": "review"})
        self.assertTrue(verify_audit(self.path, head))
        self.assertEqual(len(self.path.read_text().splitlines()), 2)

    def test_modified_audit_event_is_detected(self):
        head = append_event(self.path, "REC-1", "decision_recorded", {"status": "review"})
        event = json.loads(self.path.read_text())
        event["data"]["status"] = "match"
        self.path.write_text(json.dumps(event) + "\n")
        self.assertFalse(verify_audit(self.path, head))

    def test_removed_final_event_is_detected_with_trusted_head(self):
        append_event(self.path, "REC-1", "records_loaded", {})
        head = append_event(self.path, "REC-1", "decision_recorded", {"status": "review"})
        first_line = self.path.read_text().splitlines()[0]
        self.path.write_text(first_line + "\n")
        self.assertFalse(verify_audit(self.path, head))


if __name__ == "__main__":
    unittest.main()
