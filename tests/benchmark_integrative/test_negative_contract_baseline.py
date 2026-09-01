from __future__ import annotations

import csv
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmark/integrative/results/contracts"
REPORT = ROOT / "benchmark/integrative/reports/negative_contract_validation.md"


class NegativeContractBaselineTest(unittest.TestCase):
    def test_summary_and_all_frozen_gates_pass(self):
        summary = json.loads((RESULTS / "benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual("PASS", summary["status"])
        self.assertEqual("READY_FOR_REAL_BIOLOGICAL_INTEGRATION", summary["progression"])
        self.assertEqual(14, summary["fixtures"]["total"])
        self.assertEqual(0, summary["fixtures"]["failed"])
        with (RESULTS / "acceptance_criteria.tsv").open(encoding="utf-8", newline="") as handle:
            gates = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual([f"IC{number}" for number in range(1, 7)], [row["criterion_id"] for row in gates])
        self.assertTrue(all(row["status"] == "PASS" for row in gates))

    def test_results_checksums_and_stage_record_are_intact(self):
        for line in (RESULTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, relative = line.split(maxsplit=1)
            self.assertEqual(expected, hashlib.sha256((RESULTS / relative).read_bytes()).hexdigest(), relative)
        report = REPORT.read_text(encoding="utf-8")
        self.assertIn("The benchmark protocol numbering was not changed.", report)
        self.assertIn("10D_STATUS = NOT_STARTED", report)
        self.assertIn("NEGATIVE_CONTRACT_BENCHMARK = PASS", report)


if __name__ == "__main__":
    unittest.main()
