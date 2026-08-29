from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).parents[2] / "benchmark/chipseq/scripts/evaluate_synthetic_narrow.py"
SPEC = importlib.util.spec_from_file_location("evaluate_synthetic_narrow", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

COLLECTOR_SCRIPT = Path(__file__).parents[2] / "benchmark/chipseq/scripts/collect_synthetic_narrow_outputs.py"
COLLECTOR_SPEC = importlib.util.spec_from_file_location("collect_synthetic_narrow_outputs", COLLECTOR_SCRIPT)
assert COLLECTOR_SPEC and COLLECTOR_SPEC.loader
COLLECTOR = importlib.util.module_from_spec(COLLECTOR_SPEC)
sys.modules[COLLECTOR_SPEC.name] = COLLECTOR
COLLECTOR_SPEC.loader.exec_module(COLLECTOR)


class SyntheticNarrowEvaluatorTests(unittest.TestCase):
    def test_matching_maximizes_cardinality_before_overlap(self):
        truth = [
            MODULE.Truth(0, "T1", "chr1", 0, 400, 200, "STRONG", 0.9),
            MODULE.Truth(1, "T2", "chr1", 500, 900, 700, "WEAK", 0.3),
        ]
        calls = [
            MODULE.Peak(0, "chr1", 100, 800, "C1", 10.0, 450),
            MODULE.Peak(1, "chr1", 0, 200, "C2", 5.0, 100),
        ]
        edges = [(0, 0, 300, 250), (1, 0, 300, 250), (0, 1, 200, 100)]
        matched = MODULE.deterministic_matching(truth, calls, edges)
        self.assertEqual({(row[0], row[1]) for row in matched}, {(0, 1), (1, 0)})

    def test_average_precision_groups_tied_scores(self):
        ap, curve = MODULE.average_precision([1, 0, 1, 0], [2.0, 1.0, 1.0, 0.0])
        self.assertAlmostEqual(ap, (0.5 * 1.0) + (0.5 * (2 / 3)))
        self.assertEqual(curve[-1]["recall"], 1.0)

    def test_interval_union_metrics(self):
        left = [MODULE.Peak(0, "chr1", 0, 10, "a", 1.0, 5), MODULE.Peak(1, "chr1", 5, 15, "b", 1.0, 10)]
        right = [MODULE.Peak(0, "chr1", 10, 20, "c", 1.0, 15)]
        left_union = MODULE.interval_union(left)
        right_union = MODULE.interval_union(right)
        self.assertEqual(MODULE.union_length(left_union), 15)
        self.assertEqual(MODULE.union_intersection(left_union, right_union), 5)

    def test_final_idr_candidates_support_current_and_historical_layouts(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            expected = []
            for directory in ("experiment.idr_result", "consensus_result"):
                path = root / "experiment" / directory / "idr_output.narrowPeak"
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("chr1\t0\t10\n", encoding="utf-8")
                expected.append(path)
            unrelated = root / "idr_reports" / "idr_output.narrowPeak"
            unrelated.parent.mkdir(parents=True)
            unrelated.write_text("chr1\t0\t10\n", encoding="utf-8")

            observed = COLLECTOR.final_idr_candidates(root)

            self.assertEqual(set(observed), set(expected))


if __name__ == "__main__":
    unittest.main()
