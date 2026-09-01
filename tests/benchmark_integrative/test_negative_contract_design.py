from __future__ import annotations

import csv
import hashlib
import unittest
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
INVENTORY = ROOT / "benchmark/integrative/datasets/negative_contract_cases.tsv"
REORDER = ROOT / "benchmark/integrative/protocol/operational_stage_reordering_20260901.md"
HARNESS_CORRECTION = ROOT / "benchmark/integrative/protocol/negative_contract_harness_correction_20260901.md"
EXPECTED_SHA256 = "ba87581f3f6d8ce5ab58a510f801ad361844e239b2cab3941ccd3692be961014"


class NegativeContractDesignTest(unittest.TestCase):
    def test_frozen_inventory_identity_and_dispositions(self):
        self.assertEqual(EXPECTED_SHA256, hashlib.sha256(INVENTORY.read_bytes()).hexdigest())
        with INVENTORY.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(14, len(rows))
        self.assertEqual(14, len({row["negative_test_id"] for row in rows}))
        self.assertEqual(Counter({"FAIL": 10, "PRESERVE": 3, "NORMALIZE": 1}), Counter(row["expected_disposition"] for row in rows))

    def test_operational_reordering_does_not_cancel_real_arm(self):
        text = REORDER.read_text(encoding="utf-8")
        self.assertIn("10D_STATUS = NOT_STARTED", text)
        self.assertIn("10D_SKIPPED_TEMPORARILY = YES", text)
        self.assertIn("10D_CANCELLED = NO", text)
        self.assertIn("No 10D or 10E criteria, fixtures, gates or scientific expectations were", text)

    def test_harness_correction_does_not_change_frozen_science(self):
        text = HARNESS_CORRECTION.read_text(encoding="utf-8")
        self.assertIn("CORE_CHANGED = NO", text)
        self.assertIn("FIXTURES_CHANGED = NO", text)
        self.assertIn("EXPECTED_BEHAVIORS_CHANGED = NO", text)
        self.assertIn("IC_GATES_CHANGED = NO", text)


if __name__ == "__main__":
    unittest.main()
