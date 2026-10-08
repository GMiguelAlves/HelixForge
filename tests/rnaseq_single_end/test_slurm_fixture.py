from __future__ import annotations

import csv
import gzip
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tests/slurm"))
import generate_rnaseq_fixture as fixture  # noqa: E402
import validate_rnaseq_single_end as validate  # noqa: E402


class SlurmFixtureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory(dir=ROOT)
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.genes, self.counts = fixture.read_counts(
            ROOT / "tests/fixtures/native_de/counts_matrix.tsv", increment=False
        )

    def test_single_end_technical_runs_are_distinct_and_sum_to_one_sample(self) -> None:
        fixture.write_fastqs(self.root / "inputs", self.genes, self.counts, "single", True)
        fixture.write_tables(self.root, self.genes, self.counts, "single", True)
        fastq_root = self.root / "inputs/SYNTHETIC/fastq_ftp"
        self.assertEqual(len(list(fastq_root.glob("*_R1.fastq.gz"))), 5)
        self.assertFalse(list(fastq_root.glob("*_R2.fastq.gz")))
        with (self.root / "metadata.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 5)
        self.assertEqual(
            {row["run_accession"] for row in rows if row["sample_id"] == "control_1"},
            {"RUN_control_1a", "RUN_control_1b"},
        )
        self.assertEqual({row["library_layout"] for row in rows}, {"single"})
        observed = 0
        for suffix in ("a", "b"):
            path = fastq_root / f"control_1_RUN_control_1{suffix}_R1.fastq.gz"
            with gzip.open(path, "rt", encoding="ascii") as handle:
                lines = sum(1 for _ in handle)
            self.assertEqual(lines % 4, 0)
            observed += lines // 4
        self.assertEqual(observed, sum(self.counts["control_1"].values()))

    def test_paired_fixture_default_is_unchanged(self) -> None:
        fixture.write_fastqs(self.root / "inputs", self.genes, self.counts)
        fixture.write_tables(self.root, self.genes, self.counts)
        fastq_root = self.root / "inputs/SYNTHETIC/fastq_ftp"
        self.assertEqual(len(list(fastq_root.glob("*_R1.fastq.gz"))), 4)
        self.assertEqual(len(list(fastq_root.glob("*_R2.fastq.gz"))), 4)
        with (self.root / "metadata.csv").open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 4)
        self.assertNotIn("library_layout", rows[0])

    def test_trace_process_matching_does_not_confuse_single_and_paired(self) -> None:
        rows = [{"name": "RNASEQ:QC:TRIM_GALORE_SINGLE (sample)", "status": "CACHED"}]
        validate.assert_process_count(rows, "TRIM_GALORE_SINGLE", 1)
        validate.assert_process_count(rows, "TRIM_GALORE", 0)
        self.assertEqual(
            validate.process_name("RNASEQ:RUN_MANIFEST (rnaseq:run-id.rnaseq)"),
            "RUN_MANIFEST",
        )


if __name__ == "__main__":
    unittest.main()
