import json
import gzip
import hashlib
import importlib.util
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "benchmark/chipseq/configs/real_broad_execution.json"
STATE = ROOT / "benchmark/chipseq/results/real_broad/benchmark_state.json"
METADATA = ROOT / "benchmark/chipseq/scripts/real_broad/collect_real_broad_metadata.py"
DOWNLOAD_VALIDATOR = ROOT / "benchmark/chipseq/scripts/real_broad/validate_real_broad_downloads.py"
FASTQ_AUDITOR = ROOT / "benchmark/chipseq/scripts/real_broad/audit_real_broad_fastq_lengths.py"
READ_LENGTH_AMENDMENT = ROOT / "benchmark/chipseq/protocol/real_broad_read_length_amendment_20260831.md"
REFERENCE_PREPARER = ROOT / "benchmark/chipseq/scripts/real_broad/prepare_real_broad_reference.py"
INPUT_PREPARER = ROOT / "benchmark/chipseq/scripts/real_broad/prepare_helixforge_real_broad_inputs.py"
HELIXFORGE_RUNNER = ROOT / "benchmark/chipseq/scripts/real_broad/run_real_broad_helixforge.sh"
INDEPENDENT_RUNNER = ROOT / "benchmark/chipseq/scripts/real_broad/run_independent_real_broad.sh"
EVALUATOR = ROOT / "benchmark/chipseq/scripts/real_broad/evaluate_real_broad.py"
FIGURE_RENDERER = ROOT / "benchmark/chipseq/scripts/real_broad/render_real_broad_figures.py"


def load_download_validator():
    spec = importlib.util.spec_from_file_location("real_broad_download_validator", DOWNLOAD_VALIDATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class RealBroadBenchmarkTests(unittest.TestCase):
    def test_frozen_execution_contract(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["scientific_target"], "0829c7c154dc634ffd4e13672b95ad4fbdc5957f")
        self.assertEqual(config["protocol_commit"], "bb8db940ee137fee67fe5f13530521326c96dfc0")
        self.assertEqual(config["dataset"]["replicate_files"], ["ENCFF000BXP", "ENCFF000BXN"])
        self.assertEqual(config["dataset"]["control_file"], "ENCFF000BWK")
        self.assertEqual(config["processing"]["run_mode"], "consensus")
        self.assertEqual(config["processing"]["minimum_replicate_support"], 2)
        self.assertTrue(config["processing"]["macs3"]["broad"])
        self.assertFalse(config["processing"]["idr"]["enabled"])
        self.assertFalse(config["external_references"]["encode_is_ground_truth"])
        self.assertEqual(config["evaluation"]["coverage_bin_bp"], 500)
        self.assertEqual(config["evaluation"]["replicate_rotation_seed"], 20261003)
        self.assertEqual(config["evaluation"]["encode_rotation_seed"], 20261004)
        self.assertEqual(config["evaluation"]["encode_rotation_sets"], 100)

    def test_checkpoint_starts_before_download(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        self.assertEqual(state["current_phase"], "COMPLETED")
        self.assertEqual(state["download_status"], "DOWNLOAD_CHECKSUM_VALIDATED")
        self.assertEqual(state["preflight_job_ids"], ["16273", "16279"])
        self.assertEqual(state["metadata_job_ids"], ["16280"])
        self.assertEqual(state["runtime_job_ids"], ["16274", "16278"])
        self.assertEqual(state["cleanup_job_ids"], ["16275", "16277", "16327"])
        self.assertEqual(state["last_verified_status"]["cleanup_attempts"]["16277"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["runtime_build_job_state"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["repeat_preflight_job_state"], "COMPLETED_PASS")
        self.assertEqual(state["last_verified_status"]["runtime_job_state"], "TIMEOUT")
        self.assertEqual(state["last_verified_status"]["runtime_source_status"], "UNSUITABLE_VERSION_DRIFT")
        self.assertTrue(state["last_verified_status"]["heavy_download_started"])
        self.assertTrue(state["last_verified_status"]["scientific_output_observed"])
        self.assertEqual(state["last_verified_status"]["independent_job_state"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["independent_consensus_domains"], 19711)
        self.assertEqual(state["last_verified_status"]["audit_attempts"]["16326"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["cleanup_job_state"], "COMPLETED")
        self.assertTrue(state["last_verified_status"]["scratch_benchmark_root_removed"])

    def test_metadata_validation_preserves_frozen_accessions(self):
        source = METADATA.read_text(encoding="utf-8")
        for accession in (
            "ENCFF000BXP", "ENCFF000BXN", "ENCFF000BWK",
            "ENCFF049HUP", "ENCFF366NNJ", "ENCFF356LFX",
        ):
            self.assertIn(accession, source)
        self.assertIn('"control_experiment"', source)
        self.assertIn('"h3k27me3_target"', source)

    def test_download_validation_checks_compressed_and_content_md5(self):
        source = DOWNLOAD_VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('digest(path, "md5")', source)
        self.assertIn("expected_content_md5", source)
        self.assertIn('"DOWNLOAD_CHECKSUM_VALIDATED"', source)
        self.assertIn('"real_broad_download_manifest"', source)

    def test_fastq_length_audit_keeps_identity_checks_strict(self):
        source = FASTQ_AUDITOR.read_text(encoding="utf-8")
        self.assertIn('"compressed_md5"', source)
        self.assertIn('"content_md5"', source)
        self.assertIn('"read_count"', source)
        self.assertIn('"metadata_length_uniform"', source)
        self.assertIn('"length_histogram"', source)

    def test_read_length_amendment_freezes_observed_distribution(self):
        source = DOWNLOAD_VALIDATOR.read_text(encoding="utf-8")
        self.assertIn('"ENCFF000BXN": {36: 11752939, 47: 11077650}', source)
        amendment = READ_LENGTH_AMENDMENT.read_text(encoding="utf-8")
        self.assertIn("PROTOCOL_IMPLEMENTATION_CONFLICT = RESOLVED_PRE_EXECUTION", amendment)
        self.assertIn("PIPELINE_OR_SCIENTIFIC_PARAMETERS_CHANGED = NO", amendment)

    def test_download_validator_counts_variable_read_lengths(self):
        validator = load_download_validator()
        content = b"@r1\n" + b"A" * 36 + b"\n+\n" + b"I" * 36 + b"\n"
        content += b"@r2\n" + b"C" * 47 + b"\n+\n" + b"I" * 47 + b"\n"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "test.fastq.gz"
            with gzip.open(path, "wb") as handle:
                handle.write(content)
            validator.EXPECTED_LENGTH_HISTOGRAMS["TEST"] = {36: 1, 47: 1}
            observed = validator.validate_fastq(path, "TEST", 2, hashlib.md5(content).hexdigest())
        self.assertEqual(observed["length_histogram"], {"36": 1, "47": 1})

    def test_reference_preparation_uses_broad_external_peaks(self):
        source = REFERENCE_PREPARER.read_text(encoding="utf-8")
        self.assertIn('"broad_reference_peaks"', source)
        self.assertIn('"chipseq_real_broad_reference"', source)
        self.assertIn('"REFERENCE_READY"', source)
        self.assertIn('"renaming": "prohibited"', source)

    def test_real_broad_runner_preserves_frozen_scientific_parameters(self):
        inputs = INPUT_PREPARER.read_text(encoding="utf-8")
        runner = HELIXFORGE_RUNNER.read_text(encoding="utf-8")
        for accession in ("ENCFF000BXP", "ENCFF000BXN", "ENCFF000BWK"):
            self.assertIn(accession, inputs)
        self.assertIn('"PEAK_TYPE": "broad"', inputs)
        for value in (
            "--chipseq_run_mode consensus", "--chipseq_peak_type broad",
            "--chipseq_consensus_method replicate_support", "--chipseq_min_replicates 2",
            "--chipseq_peak_duplicate_policy all", "--chipseq_min_mapq 30",
        ):
            self.assertIn(value, runner)
        self.assertNotIn("--chipseq_idr_threshold", runner)

    def test_independent_runner_preserves_broad_parameters(self):
        source = INDEPENDENT_RUNNER.read_text(encoding="utf-8")
        for value in (
            "--very-sensitive", "-q 30 -F 2308", "--keep-dup all -B -q 0.01 --broad",
            "bedtools multiinter", "ENCFF000BXP", "ENCFF000BXN", "ENCFF000BWK",
        ):
            self.assertIn(value, source)
        self.assertNotIn("idr ", source)
        self.assertIn("LC_ALL=C awk", source)

    def test_evaluator_implements_frozen_rb_contract(self):
        source = EVALUATOR.read_text(encoding="utf-8")
        for value in (
            '"RB1"', '"RB2"', '"RB3"', '"RB4"', '"RB5"',
            "chromosome-preserving rigid circular rotation", "(1 + exceedances)",
            "annotation_distribution", "external_fragmentation",
            "ENCFF049HUP", "ENCFF366NNJ", "coordinate_equal",
        ):
            self.assertIn(value, source)
        self.assertIn('"DESCRIPTIVE"', source)
        self.assertNotIn("post-hoc domain stitching", source)

    def test_final_reporting_is_reproducible_and_auditable(self):
        renderer = FIGURE_RENDERER.read_text(encoding="utf-8")
        for value in ("figure_2_coverage_concordance.svg", "figure_4_encode_overlap.svg", "figure_6_fragmentation_context.svg"):
            self.assertIn(value, renderer)


if __name__ == "__main__":
    unittest.main()
