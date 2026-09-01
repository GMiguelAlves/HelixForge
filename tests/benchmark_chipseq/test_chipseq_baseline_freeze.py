import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
RESULTS = ROOT / "benchmark" / "chipseq" / "results"
TARGET = "0829c7c154dc634ffd4e13672b95ad4fbdc5957f"


class ChipseqBaselineFreezeTests(unittest.TestCase):
    def test_four_frozen_arms(self):
        with (RESULTS / "chipseq_benchmark_matrix.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual([row["benchmark_id"] for row in rows], ["synthetic_narrow", "synthetic_broad", "real_narrow", "real_broad"])
        self.assertTrue(all(row["overall_classification"] == "PASS_WITH_LIMITATIONS" for row in rows))
        self.assertTrue(all(row["scientific_target_commit"] == TARGET for row in rows))

    def test_summary_and_rn3_are_frozen(self):
        summary = json.loads((RESULTS / "chipseq_benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["overall_classification"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(summary["scientific_target_commit"], TARGET)
        rn3 = next(item for item in summary["deferred_follow_up"] if item["topic"] == "RN3_null_model_methodology")
        self.assertFalse(rn3["blocks_release"])
        self.assertEqual(rn3["status"], "DEFERRED_METHODS_INVESTIGATION")

    def test_acceptance_matrix_does_not_promote_rn3(self):
        with (RESULTS / "chipseq_acceptance_matrix.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        rn3 = next(row for row in rows if row["criterion_id"] == "RN3")
        self.assertEqual(rn3["status"], "NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS")


if __name__ == "__main__":
    unittest.main()
