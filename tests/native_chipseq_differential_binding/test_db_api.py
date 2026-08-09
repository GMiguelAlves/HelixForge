import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module


PREFLIGHT = load("db_preflight", ROOT / "modules/local/db_preflight/resources/usr/bin/db_preflight.py")
COUNT = load("peak_featurecounts", ROOT / "modules/local/featurecounts_peak/resources/usr/bin/peak_featurecounts.py")
FIXTURE = load("db_fixture", ROOT / "tests/native_chipseq_differential_binding/generate_fixture.py")


class PreflightTest(unittest.TestCase):
    def load_fixture(self, root):
        FIXTURE.generate(root)
        spec_path = root / "db_spec.json"
        spec = PREFLIGHT.validate_spec(PREFLIGHT.load_json(spec_path, "spec")); spec["_path"] = str(spec_path)
        consensus = PREFLIGHT.consensus_inputs(
            [str(root / "fixture.control.consensus_result"), str(root / "fixture.treated.consensus_result")],
            [str(root / "fixture.control.manifest.json"), str(root / "fixture.treated.manifest.json")],
        )
        records = [f"{condition}_rep{replicate}" for condition in ("control", "treated") for replicate in (1, 2)]
        bams = PREFLIGHT.final_bam_inputs(
            [str(root / f"{record}.filtered.bam") for record in records],
            [str(root / f"{record}.filtered.bam.bai") for record in records],
            [str(root / f"{record}.bam.manifest.json") for record in records],
        )
        plan = PREFLIGHT.read_plan(root / "peak_plan.tsv")
        return spec, consensus, bams, plan

    def test_valid_plan_builds_two_explicit_contrasts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spec, consensus, bams, plan = self.load_fixture(root)
            rows = PREFLIGHT.build_analyses(consensus, bams, plan, spec, root / "out")
            self.assertEqual(rows[0]["samples"], 4); self.assertEqual(rows[0]["contrasts"], 2)

    def test_invalid_design_and_contrast_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); FIXTURE.generate(root)
            spec = json.loads((root / "db_spec.json").read_text())
            spec["design"]["formula"] = "~ condition * batch"
            with self.assertRaisesRegex(ValueError, "design"):
                PREFLIGHT.validate_spec(spec)
            spec = json.loads((root / "db_spec.json").read_text()); spec["contrasts"][0]["denominator"] = "treated"
            with self.assertRaisesRegex(ValueError, "equals"):
                PREFLIGHT.validate_spec(spec)

    def test_insufficient_replicates_and_missing_bam_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spec, consensus, bams, plan = self.load_fixture(root)
            spec["parameters"]["min_replicates"] = 3
            with self.assertRaisesRegex(ValueError, "fewer than 3"):
                PREFLIGHT.build_analyses(consensus, bams, plan, spec, root / "out1")
            spec["parameters"]["min_replicates"] = 2; bams.pop("treated_rep2")
            with self.assertRaisesRegex(ValueError, "no matching plan/final BAM"):
                PREFLIGHT.build_analyses(consensus, bams, plan, spec, root / "out2")

    def test_duplicate_sample_and_rank_deficient_batch_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); spec, consensus, bams, plan = self.load_fixture(root)
            plan["treated_rep2"]["sample_id"] = plan["treated_rep1"]["sample_id"]
            consensus[1][0]["replicates"][1]["sample_id"] = plan["treated_rep1"]["sample_id"]
            bams["treated_rep2"]["document"]["sample_id"] = plan["treated_rep1"]["sample_id"]
            with self.assertRaisesRegex(ValueError, "duplicate sample_id"):
                PREFLIGHT.build_analyses(consensus, bams, plan, spec, root / "out")
        samples = [{"condition": "control", "batch": "A"}, {"condition": "control", "batch": "A"},
                   {"condition": "treated", "batch": "B"}, {"condition": "treated", "batch": "B"}]
        with self.assertRaisesRegex(ValueError, "rank deficient"):
            PREFLIGHT.validate_design(samples, {"variable": "condition", "covariates": ["batch"]})


class CountingContractTest(unittest.TestCase):
    def test_bed_to_saf_preserves_half_open_coordinates(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); bed, saf = root / "peaks.bed", root / "peaks.saf"
            bed.write_text("chr1\t0\t10\tp1\n", encoding="utf-8")
            self.assertEqual(COUNT.bed_to_saf(bed, saf), [("p1", "chr1", 0, 10)])
            self.assertIn("p1\tchr1\t1\t10", saf.read_text())

    def test_provider_rejects_mixed_layout(self):
        spec = {"counting": {"provider": "featurecounts", "unit": "fragments", "strandedness": 0,
                "min_mapq": 0, "overlap_policy": "any", "allow_multi_overlap": False,
                "allow_multimapping": False, "fractional": False}}
        samples = [{"layout": "paired", "bam": "a.bam"}, {"layout": "single", "bam": "b.bam"}]
        with self.assertRaisesRegex(ValueError, "one explicit"):
            COUNT.provider_command(spec, "p.saf", "out", samples, 1)


if __name__ == "__main__": unittest.main()
