import csv
import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
RESULTS = ROOT / "benchmark" / "integrative" / "results" / "reentry"
REPORT = ROOT / "benchmark" / "integrative" / "reports" / "reentry_equivalence_benchmark.md"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class ReentryBaselineTests(unittest.TestCase):
    def test_summary_is_ready(self):
        summary = json.loads((RESULTS / "benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["reentry_equivalence_benchmark"], "PASS")
        self.assertEqual(summary["readiness"], "READY_FOR_NEXT_INTEGRATIVE_STAGE")
        self.assertEqual(set(summary["ir_gates"].values()), {"PASS"})

    def test_all_frozen_ir_gates_pass(self):
        with (RESULTS / "acceptance_criteria.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual([row["criterion_id"] for row in rows], ["IR1", "IR2", "IR3", "IR4"])
        self.assertTrue(all(row["status"] == "PASS" for row in rows))

    def test_compact_checksums(self):
        for line in (RESULTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, name = line.split("  ", 1)
            path = REPORT if name == REPORT.name else RESULTS / name
            self.assertEqual(sha256(path), expected, name)

    def test_report_has_final_classification(self):
        text = REPORT.read_text(encoding="utf-8")
        self.assertIn("REENTRY_EQUIVALENCE_BENCHMARK = PASS", text)
        self.assertTrue(text.rstrip().endswith("READY_FOR_NEXT_INTEGRATIVE_STAGE"))


if __name__ == "__main__":
    unittest.main()
