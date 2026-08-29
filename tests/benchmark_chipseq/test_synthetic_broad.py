from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


def load_module(name: str, relative_path: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


PREPARE = load_module("prepare_synthetic_broad_test", "benchmark/chipseq/scripts/prepare_synthetic_broad.py")
CONSENSUS = load_module("independent_broad_consensus_test", "benchmark/chipseq/scripts/independent_broad_consensus.py")


class SyntheticBroadContractTests(unittest.TestCase):
    def setUp(self):
        self.config = json.loads(
            (ROOT / "benchmark/chipseq/configs/broad_design.json").read_text(encoding="utf-8")
        )

    def test_frozen_factorial_design(self):
        specs = PREPARE.make_specs(self.config)
        observed = {}
        for row in specs:
            key = (row["width_class"], row["signal_class"])
            observed[key] = observed.get(key, 0) + 1
            lower, upper = self.config["truth"]["width_classes_bp"][row["width_class"].lower()]
            self.assertGreaterEqual(row["width"], lower)
            self.assertLessEqual(row["width"], upper)
        self.assertEqual(len(specs), 360)
        self.assertEqual(set(observed.values()), {40})
        self.assertEqual(len(observed), 9)

    def test_repeat_traversal_is_explicit_and_auditable(self):
        policy = self.config["truth"]["repeat_traversal"]
        self.assertTrue(policy["interior_allowed"])
        self.assertTrue(policy["require_both_boundaries_eligible"])
        self.assertTrue(policy["negative_regions_follow_same_rule"])
        self.assertEqual(
            policy["record_per_interval"],
            ["repeat_overlap_bp", "repeat_overlap_fraction"],
        )

    def test_boundary_eligibility_respects_frozen_buffer(self):
        expanded, starts = PREPARE.repeat_index([("chr1", 10000, 11000, "repeat")], 2000)
        self.assertTrue(PREPARE.boundary_eligible(8000, expanded["chr1"], starts["chr1"], 100000, 2000))
        self.assertFalse(PREPARE.boundary_eligible(8001, expanded["chr1"], starts["chr1"], 100000, 2000))
        self.assertFalse(PREPARE.boundary_eligible(12999, expanded["chr1"], starts["chr1"], 100000, 2000))
        self.assertTrue(PREPARE.boundary_eligible(13000, expanded["chr1"], starts["chr1"], 100000, 2000))

    def test_repeat_overlap_counts_interior_bases(self):
        self.assertEqual(PREPARE.repeat_overlap(7000, 15000, [(10000, 11000)]), 1000)
        self.assertEqual(PREPARE.repeat_overlap(10500, 11500, [(10000, 11000)]), 500)

    def test_independent_consensus_matches_support_two_atomic_segments(self):
        left = {"chr1": [(0, 10), (10, 20), (30, 40)]}
        right = {"chr1": [(5, 15), (35, 45)]}
        self.assertEqual(
            CONSENSUS.intersect_atomic(left, right),
            [("chr1", 5, 15), ("chr1", 35, 40)],
        )

    def test_independent_consensus_cli_writes_statistics(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            peaks = []
            for name, text in (("r1", "chr1\t0\t20\n"), ("r2", "chr1\t10\t30\n")):
                path = root / f"{name}.broadPeak"
                path.write_text(text, encoding="utf-8")
                peaks.append(path)
            output = root / "consensus.bed"
            statistics = root / "statistics.json"
            original = sys.argv
            try:
                sys.argv = [
                    "independent_broad_consensus.py",
                    "--peak", str(peaks[0]),
                    "--peak", str(peaks[1]),
                    "--output", str(output),
                    "--statistics", str(statistics),
                ]
                CONSENSUS.main()
            finally:
                sys.argv = original
            self.assertEqual(output.read_text(encoding="utf-8"), "chr1\t10\t20\tINDEPENDENT_SUPPORT2_000001\n")
            self.assertEqual(json.loads(statistics.read_text(encoding="utf-8"))["covered_bases"], 10)


if __name__ == "__main__":
    unittest.main()
