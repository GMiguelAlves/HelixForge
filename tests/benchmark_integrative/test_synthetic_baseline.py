import hashlib
import csv
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
RESULTS = ROOT / "benchmark" / "integrative" / "results" / "synthetic"
REPORT = ROOT / "benchmark" / "integrative" / "reports" / "synthetic_integration_benchmark.md"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


class SyntheticIntegrativeBaselineTests(unittest.TestCase):
    def test_release_gates_and_readiness(self):
        summary = json.loads((RESULTS / "benchmark_summary.json").read_text(encoding="utf-8"))
        self.assertEqual(summary["release_gate_failures"], [])
        self.assertEqual(summary["expected_range_limitations"], [])
        self.assertEqual(summary["readiness"], "READY_FOR_REENTRY_EQUIVALENCE")

    def test_all_frozen_acceptance_criteria_pass(self):
        with (RESULTS / "acceptance_criteria.tsv").open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(rows), 12)
        self.assertTrue(all(row["status"] == "PASS" for row in rows))

    def test_committed_checksums(self):
        for line in (RESULTS / "SHA256SUMS").read_text(encoding="utf-8").splitlines():
            expected, filename = line.split("  ", 1)
            path = REPORT if filename == REPORT.name else RESULTS / filename
            self.assertTrue(path.is_file(), filename)
            self.assertEqual(sha256(path), expected, filename)

    def test_results_do_not_embed_machine_paths(self):
        forbidden = ("/scratch/", "/home/ra", "C:\\Users\\")
        for path in [REPORT, *RESULTS.glob("*.json")]:
            content = path.read_text(encoding="utf-8")
            self.assertFalse(any(token in content for token in forbidden), path.name)


if __name__ == "__main__":
    unittest.main()
