import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "benchmark/chipseq/configs/real_broad_execution.json"
STATE = ROOT / "benchmark/chipseq/results/real_broad/benchmark_state.json"
PREFLIGHT = ROOT / "benchmark/chipseq/scripts/collect_real_broad_preflight.py"
METADATA = ROOT / "benchmark/chipseq/scripts/collect_real_broad_metadata.py"


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

    def test_checkpoint_starts_before_download(self):
        state = json.loads(STATE.read_text(encoding="utf-8"))
        self.assertEqual(state["current_phase"], "WAITING_FOR_EXTERNAL_JOB")
        self.assertEqual(state["download_status"], "NOT_STARTED")
        self.assertEqual(state["preflight_job_ids"], ["16273", "16279"])
        self.assertEqual(state["runtime_job_ids"], ["16274", "16278"])
        self.assertEqual(state["cleanup_job_ids"], ["16275", "16277"])
        self.assertEqual(state["last_verified_status"]["cleanup_attempts"]["16277"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["runtime_build_job_state"], "COMPLETED")
        self.assertEqual(state["last_verified_status"]["runtime_job_state"], "TIMEOUT")
        self.assertEqual(state["last_verified_status"]["runtime_source_status"], "UNSUITABLE_VERSION_DRIFT")
        self.assertFalse(state["last_verified_status"]["heavy_download_started"])
        self.assertFalse(state["last_verified_status"]["scientific_output_observed"])

    def test_preflight_requires_slurm_and_checks_frozen_tools(self):
        source = PREFLIGHT.read_text(encoding="utf-8")
        self.assertIn('"SLURM_JOB_ID" not in os.environ', source)
        for value in ("25.10.7", "2.5.4", "samtools 1.20", "macs3 3.0.4", "v0.12.1", "1.35", "v2.31.1"):
            self.assertIn(value, source)
        self.assertIn('"broad_idr_disabled"', source)
        self.assertIn('"--r-bin"', source)

    def test_metadata_validation_preserves_frozen_accessions(self):
        source = METADATA.read_text(encoding="utf-8")
        for accession in (
            "ENCFF000BXP", "ENCFF000BXN", "ENCFF000BWK",
            "ENCFF049HUP", "ENCFF366NNJ", "ENCFF356LFX",
        ):
            self.assertIn(accession, source)
        self.assertIn('"control_experiment"', source)
        self.assertIn('"h3k27me3_target"', source)


if __name__ == "__main__":
    unittest.main()
