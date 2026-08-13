from __future__ import annotations

import csv
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
METADATA = ROOT / "modules/local/rnaseq_metadata/validate_rnaseq_metadata.py"
REFERENCE = ROOT / "modules/local/reference_bundle/validate_reference_bundle.py"


class RnaSeqFoundationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.fastq = self.root / "fastq"
        self.fastq.mkdir()
        for name in ("sample_RUN1_R1.fastq", "sample_RUN1_R2.fastq"):
            (self.fastq / name).write_text("@read\nACGT\n+\nIIII\n", encoding="ascii")
        self.transcriptome = self.root / "transcriptome.fa"
        self.genome = self.root / "genome.fa"
        self.annotation = self.root / "annotation.gtf"
        self.transcriptome.write_text(">tx1\nACGTACGT\n", encoding="ascii")
        self.genome.write_text(">chr1\nACGTACGT\n", encoding="ascii")
        self.annotation.write_text(
            'chr1\ttest\ttranscript\t1\t8\t.\t+\t.\tgene_id "gene1"; transcript_id "tx1";\n',
            encoding="utf-8",
        )

    def tearDown(self):
        self.temp.cleanup()

    def write_context(self):
        metadata = self.root / "metadata.csv"
        with metadata.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(
                handle,
                fieldnames=["dataset", "sample_id", "file_prefix", "run_accession", "condition", "batch", "fastq_1", "fastq_2"],
            )
            writer.writeheader()
            writer.writerow({
                "dataset": "TEST", "sample_id": "sample", "file_prefix": "sample",
                "run_accession": "RUN1", "condition": "control", "batch": "B1",
                "fastq_1": self.fastq / "sample_RUN1_R1.fastq",
                "fastq_2": self.fastq / "sample_RUN1_R2.fastq",
            })
        settings = self.root / "settings.tsv"
        settings.write_text(
            "key\tvalue\n"
            f"METADATA_BASE_DIR\t{self.root}\n"
            "PIPELINE_PROJECTS\tTEST\n"
            f"SCRATCH_ROOT\t{self.root / 'scratch'}\n"
            "ORGANISM_NAME\tTest organism\n"
            "NATIVE_ANALYSIS_MODE\tquantification\n"
            "QUANT_METHOD\tsalmon\n"
            f"REF_GENOME_FA\t{self.genome}\n"
            f"REF_TRANSCRIPTS_FA\t{self.transcriptome}\n"
            f"REF_GTF\t{self.annotation}\n"
            "TRIM_QUALITY\t20\nTRIM_LENGTH\t20\n",
            encoding="utf-8",
        )
        return metadata, settings

    def test_metadata_builds_legacy_compatible_names_without_download(self):
        metadata, settings = self.write_context()
        result = subprocess.run([
            sys.executable, str(METADATA), "--metadata", str(metadata), "--settings", str(settings),
            "--normalized", str(self.root / "validated.csv"), "--plan-dir", str(self.root),
            "--reference-plan", str(self.root / "references.tsv"), "--report", str(self.root / "report.json"),
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        with (self.root / "TEST_qc_plan.csv").open(newline="", encoding="utf-8") as handle:
            row = next(csv.DictReader(handle))
        self.assertEqual(row["raw_r1"], str((self.fastq / "sample_RUN1_R1.fastq").resolve()))
        self.assertEqual(Path(row["trimmed_run_r1"]).parts[-3:], ("TEST", "trimmed_runs", "sample_RUN1_R1_trimmed.fastq.gz"))
        self.assertEqual(Path(row["merged_sample_r2"]).parts[-3:], ("TEST", "trimmed_merged", "sample_R2_trimmed.fastq.gz"))
        self.assertFalse(json.loads((self.root / "report.json").read_text())["download_performed"])

    def test_metadata_rejects_missing_fastq(self):
        metadata, settings = self.write_context()
        (self.fastq / "sample_RUN1_R2.fastq").unlink()
        result = subprocess.run([
            sys.executable, str(METADATA), "--metadata", str(metadata), "--settings", str(settings),
            "--normalized", str(self.root / "validated.csv"), "--plan-dir", str(self.root),
            "--reference-plan", str(self.root / "references.tsv"), "--report", str(self.root / "report.json"),
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("fastq_2 does not exist", result.stderr)

    def test_reference_bundle_records_content_checksums(self):
        manifest = self.root / "manifest.json"
        result = subprocess.run([
            sys.executable, str(REFERENCE), "--reference-id", "test-v1", "--organism", "Test organism",
            "--transcriptome", str(self.transcriptome), "--annotation", str(self.annotation),
            "--genome", str(self.genome), "--manifest", str(manifest), "--report", str(self.root / "reference-report.json"),
        ], text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        document = json.loads(manifest.read_text(encoding="utf-8"))
        artifacts = {item["role"]: item for item in document["artifacts"]}
        expected = hashlib.sha256(self.transcriptome.read_bytes()).hexdigest()
        self.assertEqual(artifacts["transcriptome"]["sha256"], expected)
        self.assertEqual(document["type"], "reference_bundle")

    def test_main_qc_graph_has_no_download_process(self):
        qc_source = (ROOT / "subworkflows/local/rnaseq/qc.nf").read_text(encoding="utf-8")
        workflow_source = (ROOT / "workflows/rnaseq.nf").read_text(encoding="utf-8")
        self.assertNotIn("RNASEQ_DOWNLOAD_STEP", qc_source)
        self.assertNotIn("RNASEQ_METADATA_STEP", qc_source)
        self.assertIn("RNASEQ_NATIVE_FOUNDATION", workflow_source)


if __name__ == "__main__":
    unittest.main()
