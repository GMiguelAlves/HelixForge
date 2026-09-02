from __future__ import annotations

import csv
import gzip
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
SELECTION = ROOT / "benchmark/integrative/datasets/real_sample_selection.tsv"
VALIDATOR_PATH = ROOT / "benchmark/integrative/scripts/real/validate_gse133183_metadata.py"
STATE_PATH = ROOT / "benchmark/integrative/results/real/benchmark_state.json"


def load_validator():
    spec = importlib.util.spec_from_file_location("real_metadata", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealBiologicalPreflightTests(unittest.TestCase):
    def test_selection_is_exact_and_balanced(self):
        with SELECTION.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual(len(rows), 16)
        self.assertEqual({row["geo_sample"] for row in rows}, {f"GSM{i}" for i in range(4817452, 4817468)})
        self.assertEqual(sum(row["assay"] == "RNA-seq" for row in rows), 4)
        self.assertEqual(sum(row["mark"] == "H3K27me3" for row in rows), 4)
        self.assertEqual(sum(row["mark"] == "H3K27ac" for row in rows), 4)
        self.assertEqual(sum(row["mark"] == "IgG" for row in rows), 4)
        for row in rows:
            if row["mark"] in {"H3K27me3", "H3K27ac"}:
                self.assertTrue(row["control_geo_sample"].startswith("GSM"))

    def test_reference_inventory_has_no_unresolved_checksum(self):
        path = ROOT / "benchmark/integrative/datasets/reference_sources.tsv"
        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle, delimiter="\t"))
        self.assertEqual({row["role"] for row in rows}, {"genome_fasta", "annotation_gtf", "transcriptome", "blacklist"})
        for row in rows:
            self.assertRegex(row["frozen_md5"], r"^[0-9a-f]{32}$")

    def test_persistent_state_records_frozen_orders(self):
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        self.assertEqual(state["scientific_stage_order"], ["10B", "10C", "10D", "10E", "10F"])
        self.assertEqual(state["operational_stage_order"], ["10B", "10C", "10E", "10D"])
        self.assertEqual(state["phase"], "REFERENCE_COMPLETE")
        self.assertEqual(state["status"], "COMPLETE")
        self.assertEqual(state["jobs"][0]["job_id"], "16456")
        self.assertEqual(state["jobs"][-1]["job_id"], "16505")
        self.assertEqual(state["jobs"][-1]["phase"], "REFERENCE_COMPLETE")

    def test_accession_preflight_is_complete(self):
        metadata = ROOT / "benchmark/integrative/results/real/metadata"
        validation = json.loads((metadata / "metadata_validation.json").read_text(encoding="utf-8"))
        storage = json.loads((metadata / "storage_plan.json").read_text(encoding="utf-8"))
        self.assertEqual(validation["status"], "METADATA_VALIDATED")
        self.assertEqual(len(validation["selected_gsms"]), 16)
        self.assertEqual(len(validation["selected_runs"]), 16)
        self.assertEqual(storage["selected_fastq_files"], 32)
        self.assertEqual(storage["status"], "SPACE_AVAILABLE")
        self.assertGreater(storage["paired_fastq_download_gib"], 200)

    def test_validator_rejects_execution_outside_slurm(self):
        with tempfile.TemporaryDirectory() as directory:
            result = subprocess.run(
                [sys.executable, str(VALIDATOR_PATH), "--selection", str(SELECTION),
                 "--ena-dir", directory, "--runinfo", str(SELECTION),
                 "--geo-soft", str(SELECTION), "--reference-sources", str(SELECTION),
                 "--scratch-root", directory, "--output-dir", str(Path(directory) / "out")],
                capture_output=True, text=True, env={key: value for key, value in os.environ.items() if key != "SLURM_JOB_ID"},
            )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must execute inside a Slurm job", result.stderr + result.stdout)

    def test_helper_parsers_preserve_paired_fastq_contract(self):
        module = load_validator()
        row = {
            "run_accession": "SRRTEST",
            "library_layout": "PAIRED",
            "fastq_ftp": "example/SRRTEST_1.fastq.gz;example/SRRTEST_2.fastq.gz",
            "fastq_md5": "a" * 32 + ";" + "b" * 32,
            "fastq_bytes": "10;20",
        }
        files = module.split_ena_files(row)
        self.assertEqual([item["mate"] for item in files], ["1", "2"])
        self.assertEqual(sum(item["bytes"] for item in files), 30)


if __name__ == "__main__":
    unittest.main()
