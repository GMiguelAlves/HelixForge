import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmark/integrative/results"
PROVENANCE = ROOT / "benchmark/integrative/provenance"
REAL_ACCEPTANCE = RESULTS / "real/evaluation/acceptance_results.tsv"


class IntegrativeBaselineFreezeTests(unittest.TestCase):
    def test_four_arms_are_frozen_without_promotion(self):
        with (RESULTS / "integrative_benchmark_matrix.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(
            [row["arm_id"] for row in rows],
            ["synthetic_ground_truth", "manifest_reentry", "negative_contracts", "real_biological"],
        )
        self.assertEqual(
            [row["overall_classification"] for row in rows],
            ["PASS", "PASS", "PASS", "PASS_WITH_LIMITATIONS"],
        )
        self.assertTrue(all(row["core_release_gates"] == "PASS" for row in rows))

    def test_summary_freezes_global_classification(self):
        summary = json.loads((RESULTS / "integrative_benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["phase"], "BASELINE_FROZEN")
        self.assertEqual(summary["overall_classification"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(summary["core_release_gate_failures"], [])
        self.assertEqual(summary["tag"], "integrative-benchmark-v1.0.0-rc.1")

    def test_ib4_and_ib5_remain_unchanged(self):
        with REAL_ACCEPTANCE.open(encoding="utf-8", newline="") as handle:
            criteria = {row["criterion"]: row for row in csv.DictReader(handle, delimiter="\t")}
        self.assertEqual(criteria["IB4"]["type"], "EXPECTED_RANGE")
        self.assertEqual(criteria["IB4"]["status"], "FAIL")
        self.assertEqual(criteria["IB5"]["type"], "EXPECTED_RANGE")
        self.assertEqual(criteria["IB5"]["status"], "NOT_EVALUABLE")

    def test_freeze_manifest_tracks_all_audit_archives(self):
        manifest = json.loads(
            (PROVENANCE / "integrative_benchmark_freeze_manifest.json").read_text(encoding="utf-8")
        )
        self.assertEqual(manifest["phase"], "BASELINE_FROZEN")
        self.assertEqual(manifest["overall_classification"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(set(manifest["audit_archives"]), {"synthetic", "reentry", "negative_contracts", "real_biological"})
        self.assertEqual(manifest["preserved_limitations"]["IB4"], "FAIL_EXPECTED_RANGE_NO_SIGNIFICANT_H3K27ME3_REGIONS")
        self.assertEqual(manifest["preserved_limitations"]["IB5"], "NOT_EVALUABLE_DIRECTIONAL_FISHER_TESTS_NOT_EMITTED")


if __name__ == "__main__":
    unittest.main()
