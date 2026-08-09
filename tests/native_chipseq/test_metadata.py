import csv
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = ROOT / "modules" / "local" / "chipseq_metadata" / "validate_chipseq_metadata.py"
SPEC = importlib.util.spec_from_file_location("chipseq_metadata_validator", VALIDATOR)
VALIDATION = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(VALIDATION)


FIELDS = [
    "sample_id", "run_accession", "fastq_1", "fastq_2", "layout",
    "condition", "biological_replicate", "technical_replicate", "target",
    "control_id", "is_control", "organism", "genome_id", "dataset", "lane",
]


class ChipseqMetadataTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fastq = self.root / "fastq"
        self.fastq.mkdir()
        self.reference = self.root / "genome.fa"
        self.reference.write_text(">chr1\nACGTACGT\n", encoding="utf-8")
        for name in ["input", "ip1", "ip2", "ip1_lane2"]:
            for mate in ["R1", "R2"]:
                (self.fastq / f"{name}_{mate}.fastq").write_text(
                    f"@{name}_{mate}\nACGT\n+\nFFFF\n", encoding="utf-8"
                )
        self.settings = {
            "FASTQ_DIR": str(self.fastq),
            "READ_LAYOUT": "metadata",
            "ALLOW_MISSING_CONTROLS": "false",
            "ORGANISM_NAME": "test organism",
        }

    def tearDown(self):
        self.temp.cleanup()

    def row(self, sample, condition, replicate, control, is_control, **changes):
        values = {
            "sample_id": sample,
            "run_accession": "",
            "fastq_1": f"{sample}_R1.fastq",
            "fastq_2": f"{sample}_R2.fastq",
            "layout": "paired",
            "condition": condition,
            "biological_replicate": str(replicate),
            "technical_replicate": "1",
            "target": "input" if is_control else "H3K27ac",
            "control_id": control,
            "is_control": str(is_control).lower(),
            "organism": "test organism",
            "genome_id": "test_v1",
            "dataset": "study1",
            "lane": "",
        }
        values.update(changes)
        return values

    def write_metadata(self, rows):
        path = self.root / "metadata.tsv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
        return path

    def valid_rows(self):
        return [
            self.row("input", "control", 1, "", True),
            self.row("ip1", "treated", 1, "input", False),
            self.row("ip2", "treated", 2, "input", False),
        ]

    def test_multiple_samples_controls_and_biological_replicates(self):
        rows = VALIDATION.load_rows(self.write_metadata(self.valid_rows()), self.settings)
        controls = VALIDATION.validate_relationships(rows, False)
        self.assertEqual(len(rows), 3)
        self.assertEqual(len(controls), 2)
        self.assertEqual({row["biological_replicate"] for row in rows if row["is_control"] == "false"}, {"1", "2"})

    def test_missing_control_fails(self):
        rows = self.valid_rows()
        rows[1]["control_id"] = "absent"
        normalized = VALIDATION.load_rows(self.write_metadata(rows), self.settings)
        with self.assertRaisesRegex(ValueError, "missing control absent"):
            VALIDATION.validate_relationships(normalized, False)

    def test_incompatible_control_reference_fails(self):
        rows = self.valid_rows()
        rows[0]["genome_id"] = "other_build"
        normalized = VALIDATION.load_rows(self.write_metadata(rows), self.settings)
        with self.assertRaisesRegex(ValueError, "disagree on genome_id"):
            VALIDATION.validate_relationships(normalized, False)

    def test_ambiguous_duplicate_sample_fails(self):
        rows = self.valid_rows()
        duplicate = dict(rows[1])
        duplicate["fastq_1"] = "ip1_lane2_R1.fastq"
        duplicate["fastq_2"] = "ip1_lane2_R2.fastq"
        rows.append(duplicate)
        with self.assertRaisesRegex(ValueError, "duplicate execution record id"):
            VALIDATION.load_rows(self.write_metadata(rows), self.settings)

    def test_compatible_technical_runs_are_distinct(self):
        rows = self.valid_rows()
        rows[1]["run_accession"] = "RUN_A"
        duplicate = dict(rows[1])
        duplicate.update({
            "run_accession": "RUN_B",
            "technical_replicate": "2",
            "fastq_1": "ip1_lane2_R1.fastq",
            "fastq_2": "ip1_lane2_R2.fastq",
        })
        rows.append(duplicate)
        normalized = VALIDATION.load_rows(self.write_metadata(rows), self.settings)
        VALIDATION.validate_relationships(normalized, False)
        self.assertEqual([row["record_id"] for row in normalized if row["sample_id"] == "ip1"], ["RUN_A", "RUN_B"])

    def test_missing_fastq_fails_early(self):
        rows = self.valid_rows()
        rows[2]["fastq_1"] = "does_not_exist.fastq"
        with self.assertRaisesRegex(ValueError, "fastq_1 does not exist"):
            VALIDATION.load_rows(self.write_metadata(rows), self.settings)


if __name__ == "__main__":
    unittest.main()

