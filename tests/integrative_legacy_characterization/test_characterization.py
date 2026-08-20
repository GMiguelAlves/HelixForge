#!/usr/bin/env python3

from __future__ import annotations

import csv
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tests.integrative_legacy_characterization.baseline_support import (
    BASE_DIR,
    FIXTURE_DIR,
    GOLDEN_DIR,
    iter_expected_outputs,
    normalized_text,
    sha256,
)
from tests.integrative_legacy_characterization.run_baseline import run


def read_tsv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


class IntegrativeLegacyCharacterizationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(dir=BASE_DIR)
        cls.actual = Path(cls.temp.name) / "actual"
        run(cls.actual, clean=False)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_all_golden_outputs_match(self):
        for group, relative in iter_expected_outputs():
            with self.subTest(group=group, output=relative):
                actual = self.actual / relative
                golden = GOLDEN_DIR / group / relative
                self.assertTrue(actual.is_file(), actual)
                self.assertTrue(golden.is_file(), golden)
                self.assertEqual(normalized_text(actual, self.actual), golden.read_text(encoding="utf-8"))

    def test_fixture_exercises_every_integrative_class(self):
        rows = read_tsv(self.actual / "070-integrated-tables" / "integrated_gene_table.tsv")
        observed = {row["gene_id"]: row["integrative_class"] for row in rows}
        expected = json.loads((FIXTURE_DIR / "expected_behavior.json").read_text(encoding="utf-8"))["classes"]
        self.assertEqual(observed, expected)
        self.assertEqual(
            set(observed.values()),
            {
                "DEG_with_differential_peak",
                "DEG_with_promoter_peak",
                "DEG_with_gene_body_peak",
                "DEG_with_distal_peak",
                "DEG_only",
                "ChIP_only",
                "unchanged",
            },
        )

    def test_manifest_checksums_match_tracked_baseline(self):
        manifest = json.loads((BASE_DIR / "baseline_manifest.json").read_text(encoding="utf-8"))
        observed_inputs = {
            str(path.relative_to(FIXTURE_DIR)).replace("\\", "/"): sha256(path)
            for path in sorted(FIXTURE_DIR.rglob("*"))
            if path.is_file()
        }
        observed_golden = {
            str(path.relative_to(GOLDEN_DIR)).replace("\\", "/"): sha256(path)
            for path in sorted(GOLDEN_DIR.rglob("*"))
            if path.is_file()
        }
        self.assertEqual(observed_inputs, manifest["input_checksums"])
        self.assertEqual(observed_golden, manifest["golden_checksums"])

    def test_candidate_score_is_an_ordered_heuristic(self):
        rows = read_tsv(self.actual / "080-candidate-scoring" / "candidate_gene_scores.tsv")
        scores = [float(row["candidate_score"]) for row in rows]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual([row["gene_id"] for row in rows], ["geneA", "geneB", "geneF", "geneC", "geneD", "geneE", "geneG", "geneH"])
        self.assertTrue(all(row["score_components"].startswith("deg_significance;") for row in rows))


if __name__ == "__main__":
    unittest.main()
