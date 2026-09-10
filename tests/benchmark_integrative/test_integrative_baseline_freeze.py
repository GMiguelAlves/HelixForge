import csv
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "benchmark/integrative/results"
PROVENANCE = ROOT / "benchmark/integrative/provenance"
REAL_ACCEPTANCE = RESULTS / "real/evaluation/acceptance_results.tsv"
FIGURES = ROOT / "benchmark/integrative/figures/baseline"
FINAL_REPORT = ROOT / "benchmark/integrative/reports/integrative_benchmark_final_report.md"
FIGURE_RENDERER = ROOT / "benchmark/integrative/scripts/render_benchmark_figures.py"


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
        self.assertEqual(summary["tag_status"], "PUBLISHED")
        self.assertEqual(summary["tag_target_commit"], "0394fc2ab620e723b1b627dac18508feb50f574b")

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
        self.assertEqual(manifest["tag_status"], "PUBLISHED")
        self.assertEqual(set(manifest["audit_archives"]), {"synthetic", "reentry", "negative_contracts", "real_biological"})
        self.assertEqual(manifest["preserved_limitations"]["IB4"], "FAIL_EXPECTED_RANGE_NO_SIGNIFICANT_H3K27ME3_REGIONS")
        self.assertEqual(manifest["preserved_limitations"]["IB5"], "NOT_EVALUABLE_DIRECTIONAL_FISHER_TESTS_NOT_EMITTED")

    def test_metric_figures_are_reproducible_and_referenced(self):
        names = {
            "acceptance_criteria_status.svg",
            "benchmark_arm_status.svg",
            "real_biological_metrics.svg",
            "runtime_overview.svg",
        }
        report = FINAL_REPORT.read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            generated = Path(directory)
            subprocess.run(
                [sys.executable, str(FIGURE_RENDERER), "--repo-root", str(ROOT), "--output-dir", str(generated)],
                check=True,
            )
            for name in names:
                self.assertEqual(
                    (generated / name).read_text(encoding="utf-8"),
                    (FIGURES / name).read_text(encoding="utf-8"),
                )
                self.assertIn(f"../figures/baseline/{name}", report)
            self.assertEqual(
                (generated / "SHA256SUMS").read_text(encoding="utf-8"),
                (FIGURES / "SHA256SUMS").read_text(encoding="utf-8"),
            )


if __name__ == "__main__":
    unittest.main()
