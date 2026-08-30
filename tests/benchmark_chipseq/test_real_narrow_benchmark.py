import importlib.util
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CONFIG = ROOT / "benchmark/chipseq/configs/real_narrow_execution.json"
CONTIG_AMENDMENT = ROOT / "benchmark/chipseq/protocol/real_narrow_contig_amendment_20260830.md"
NULL_AMENDMENT = ROOT / "benchmark/chipseq/protocol/real_narrow_null_amendment_20260830.md"
SNAPSHOT = ROOT / "benchmark/chipseq/results/real_narrow/metadata/encode_metadata_snapshot.json"
SCRIPT = ROOT / "benchmark/chipseq/scripts/collect_real_narrow_metadata.py"
HELIXFORGE_RUNNER = ROOT / "benchmark/chipseq/scripts/run_real_narrow_helixforge.sh"
INDEPENDENT_RUNNER = ROOT / "benchmark/chipseq/scripts/run_independent_real_narrow.sh"
EVALUATOR = ROOT / "benchmark/chipseq/scripts/evaluate_real_narrow.py"
NULL_VALIDATOR = ROOT / "benchmark/chipseq/scripts/validate_real_narrow_null_generator.py"
NULL_SLURM = ROOT / "benchmark/chipseq/scripts/slurm_validate_real_narrow_nulls.sh"
NULL_FREEZER = ROOT / "benchmark/chipseq/scripts/freeze_real_narrow_nulls.py"
EXACT_GC_PREFLIGHT = ROOT / "benchmark/chipseq/scripts/preflight_real_narrow_exact_gc_capacity.py"
EXACT_GC_SLURM = ROOT / "benchmark/chipseq/scripts/slurm_preflight_real_narrow_exact_gc.sh"
FINAL_METRICS = ROOT / "benchmark/chipseq/results/real_narrow/evaluation/final_metrics.json"


def load_script():
    spec = importlib.util.spec_from_file_location("real_narrow_metadata", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class RealNarrowBenchmarkTests(unittest.TestCase):
    def test_frozen_execution_contract(self):
        config = json.loads(CONFIG.read_text(encoding="utf-8"))
        self.assertEqual(config["scientific_target"], "0829c7c154dc634ffd4e13672b95ad4fbdc5957f")
        self.assertEqual(config["dataset"]["replicate_files"], ["ENCFF000BWM", "ENCFF000BWR"])
        self.assertEqual(config["dataset"]["control_file"], "ENCFF000BWK")
        self.assertEqual(config["processing"]["run_mode"], "idr")
        self.assertEqual(config["processing"]["macs3"]["format"], "BAM")
        self.assertEqual(config["evaluation"]["motif"]["matrix_id"], "MA0139.1")
        self.assertEqual(config["evaluation"]["encode_overlap_null"]["sets"], 100)
        null = config["evaluation"]["encode_overlap_null"]
        self.assertEqual(null["seed"], 20261002)
        self.assertEqual(null["candidate_sets"], 2000)
        self.assertIn("exact GC-base-count", null["method"])
        self.assertTrue(null["final_amendment"])
        self.assertIn("0.005", null["gc_match"])
        self.assertEqual(null["diversity_gates"]["minimum_observed_expected_unique_ratio"], 0.8)
        self.assertEqual(null["invalidated_result"]["status"], "INVALID_FOR_INFERENCE")
        policy = config["external_references"]["contig_policy"]
        self.assertIn("intersection", policy["comparison_universe"])
        self.assertIn("without renaming", policy["absent_external_records"])
        self.assertTrue(CONTIG_AMENDMENT.is_file())
        self.assertTrue(NULL_AMENDMENT.is_file())

    def test_metadata_snapshot_is_validated(self):
        snapshot = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
        self.assertEqual(snapshot["status"], "METADATA_VALIDATED")
        self.assertTrue(all(snapshot["checks"].values()))
        self.assertEqual({item["accession"] for item in snapshot["files"]}, {
            "ENCFF000BWM", "ENCFF000BWR", "ENCFF000BWK",
            "ENCFF519CXF", "ENCFF433VSV", "ENCFF356LFX",
        })

    def test_audit_rows_preserve_levels(self):
        module = load_script()
        observed = module.audit_rows({"audit": {"WARNING": [{"category": "legacy", "detail": "x", "path": "/x"}]}})
        self.assertEqual(observed, [{"level": "WARNING", "category": "legacy", "detail": "x", "path": "/x"}])

    def test_real_narrow_runners_preserve_frozen_parameters(self):
        helixforge = HELIXFORGE_RUNNER.read_text(encoding="utf-8")
        independent = INDEPENDENT_RUNNER.read_text(encoding="utf-8")
        for value in ("--chipseq_peak_format BAM", "--chipseq_min_mapq 30", "2913022398"):
            self.assertIn(value, helixforge)
        for value in ("-f BAM", "-q 30 -F 2308", "2913022398", "--rank signal.value"):
            self.assertIn(value, independent)

    def test_real_narrow_evaluator_preserves_frozen_seeds(self):
        evaluator = EVALUATOR.read_text(encoding="utf-8")
        self.assertIn('CONTROL_SEED = 20261001', evaluator)
        self.assertIn('NULL_SEED = 20261002', evaluator)
        self.assertIn('NULL_SETS = 100', evaluator)
        self.assertIn('GC_TOLERANCE = 0.005', evaluator)
        self.assertIn('POOL_MULTIPLIER = 20', evaluator)
        self.assertIn('MAX_POOL_ATTEMPT_MULTIPLIER = 10000', evaluator)
        self.assertIn('RN3_INFERENCE_LOCKED = True', evaluator)
        self.assertIn('"pass": bool(motif_test.pvalue < 0.05)', evaluator)
        self.assertIn('null_relocation_capacity.tsv', evaluator)
        self.assertIn('read_peaks(external_path, require_summit=False)', evaluator)
        self.assertIn('max(0, min(a[i][1], b[j][1]) - max(a[i][0], b[j][0]))', evaluator)

    def test_null_generator_validation_is_separate_from_rn3(self):
        validator = NULL_VALIDATOR.read_text(encoding="utf-8")
        slurm = NULL_SLURM.read_text(encoding="utf-8")
        self.assertIn('phase": "NULL_GENERATOR_VALIDATION"', validator)
        self.assertIn('"rn3": {"calculated": False}', validator)
        self.assertNotIn('observed_overlap', validator)
        self.assertNotIn('empirical_p', validator)
        self.assertIn('MIN_UNIQUE_EXPECTATION_RATIO = 0.80', validator)
        self.assertIn('GLOBAL_MAX_REUSE_ALPHA = 0.01', validator)
        self.assertIn('V2_SAMPLER_RETIRED = True', validator)
        self.assertIn('choices=("run_a", "run_b")', validator)
        self.assertIn('null_validation/$run_label', slurm)
        freezer = NULL_FREEZER.read_text(encoding="utf-8")
        self.assertIn('"phase": "VALIDATED_NULL_FREEZE"', freezer)
        self.assertIn('"rn3": {"calculated": False}', freezer)
        self.assertIn('deterministic null-generator outputs are not byte-identical', freezer)

    def test_exact_gc_capacity_preflight_cannot_run_inference(self):
        preflight = EXACT_GC_PREFLIGHT.read_text(encoding="utf-8")
        slurm = EXACT_GC_SLURM.read_text(encoding="utf-8")
        self.assertIn('phase": "EXACT_GC_CAPACITY_PREFLIGHT"', preflight)
        self.assertIn('"rn3_calculated": False', preflight)
        self.assertIn('"null_sets_generated": False', preflight)
        self.assertNotIn('observed_overlap', preflight)
        self.assertNotIn('empirical_p', preflight)
        self.assertIn('M >= k', preflight)
        self.assertIn('null_v3_capacity', slurm)

    def test_final_classification_preserves_rn3_disposition(self):
        metrics = json.loads(FINAL_METRICS.read_text(encoding="utf-8"))
        self.assertEqual(metrics["classification"], "PASS_WITH_LIMITATIONS")
        self.assertEqual(metrics["criteria"]["RN3"], "NOT_EVALUABLE_UNDER_FROZEN_CONTROL_REQUIREMENTS")
        self.assertFalse(metrics["rn3"]["null_sets_generated"])
        self.assertFalse(metrics["rn3"]["rn3_calculated"])
        self.assertEqual(metrics["rn3"]["invalidated_nominal_p_status"], "INVALID_FOR_INFERENCE")


if __name__ == "__main__":
    unittest.main()
