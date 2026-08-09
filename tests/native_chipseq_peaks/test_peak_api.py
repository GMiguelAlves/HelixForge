import base64
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT = load("peak_context", ROOT / "modules/local/peak_calling_context/resources/usr/bin/validate_peak_context.py")
AGGREGATE = load("peak_aggregate", ROOT / "modules/local/peak_calling_aggregate/resources/usr/bin/aggregate_peaks.py")
RUNNER = load("macs3_runner", ROOT / "modules/local/macs3_callpeak/resources/usr/bin/run_macs3_callpeak.py")


class PeakContextTest(unittest.TestCase):
    def rows(self):
        base = {"dataset": "d", "genome_id": "g", "organism": "o", "layout": "paired", "technical_replicate": "1"}
        return [
            {**base, "record_id": "ctrl", "sample_id": "ctrl", "condition": "control", "biological_replicate": "1", "is_control": "true", "control_id": "", "target": "input", "peak_dir": "/tmp/peaks", "peak_caller": "macs3", "peak_type": "narrow", "macs_qvalue": "0.01", "macs_genome_size": "1000", "macs_extra_opts": ""},
            {**base, "record_id": "ip1", "sample_id": "ip1", "condition": "treated", "biological_replicate": "1", "is_control": "false", "control_id": "ctrl", "target": "H3K27ac", "peak_dir": "/tmp/peaks", "peak_caller": "macs3", "peak_type": "narrow", "macs_qvalue": "0.01", "macs_genome_size": "1000", "macs_extra_opts": ""},
        ]

    def test_valid_control_and_request(self):
        plan = CONTEXT.build_peak_plan(self.rows(), {"caller_version": "3.0.4", "duplicate_policy": "all"})
        self.assertEqual(plan[0]["control_record_id"], "ctrl")
        self.assertEqual(plan[0]["format"], "BAMPE")

    def test_missing_control_fails(self):
        rows = self.rows()
        rows[1]["control_id"] = "missing"
        with self.assertRaisesRegex(ValueError, "does not identify a control"):
            CONTEXT.build_peak_plan(rows, {})

    def test_incompatible_control_fails(self):
        rows = self.rows()
        rows[0]["genome_id"] = "other"
        with self.assertRaisesRegex(ValueError, "disagree on genome_id"):
            CONTEXT.build_peak_plan(rows, {})

    def test_ambiguous_control_fails(self):
        rows = self.rows()
        rows[0]["record_id"] = "ctrl.run1"
        duplicate = dict(rows[0], record_id="ctrl.run2")
        rows.append(duplicate)
        with self.assertRaisesRegex(ValueError, "ambiguous"):
            CONTEXT.build_peak_plan(rows, {})

    def test_invalid_caller_peak_type_and_genome_size(self):
        for spec, message in [
            ({"caller": "unknown"}, "unsupported peak caller"),
            ({"peak_type": "auto"}, "explicitly narrow or broad"),
            ({"effective_genome_size": "auto"}, "explicit positive number"),
        ]:
            with self.subTest(spec=spec), self.assertRaisesRegex(ValueError, message):
                CONTEXT.build_peak_plan(self.rows(), spec)

    def test_invalid_probabilities(self):
        for spec in ({"q_value": 0}, {"q_value": 1.1}, {"p_value": -0.1}):
            with self.subTest(spec=spec), self.assertRaisesRegex(ValueError, "must be > 0 and <= 1"):
                CONTEXT.build_peak_plan(self.rows(), spec)

    def test_managed_additional_argument_fails(self):
        with self.assertRaisesRegex(ValueError, "cannot override managed"):
            CONTEXT.build_peak_plan(self.rows(), {"additional_args": "--outdir other"})

    def test_duplicate_replicate_fails(self):
        rows = self.rows()
        rows.append(dict(rows[1], record_id="ip1.other"))
        with self.assertRaisesRegex(ValueError, "duplicate sample/replicate/target"):
            CONTEXT.build_peak_plan(rows, {})

    def test_output_collision_fails(self):
        rows = self.rows()
        rows.append(dict(
            rows[1], sample_id="ip2", biological_replicate="2", technical_replicate="1"
        ))
        with self.assertRaisesRegex(ValueError, "peak output collision"):
            CONTEXT.build_peak_plan(rows, {})


class PeakFormatTest(unittest.TestCase):
    def test_narrow_and_broad_formats(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            narrow = root / "peaks.narrowPeak"
            broad = root / "peaks.broadPeak"
            narrow.write_text("chr1\t0\t10\tp1\t100\t.\t5\t10\t8\t4\n", encoding="utf-8")
            broad.write_text("chr1\t1\t20\tp1\t100\t.\t4\t9\t7\n", encoding="utf-8")
            self.assertEqual(AGGREGATE.validate_peaks(narrow, "narrow")["total_peaks"], 1)
            self.assertEqual(AGGREGATE.validate_peaks(broad, "broad")["total_peaks"], 1)

    def test_invalid_columns_and_coordinates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.narrowPeak"
            path.write_text("chr1\t10\t5\tp1\t100\t.\t5\t10\t8\t4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid half-open coordinates"):
                AGGREGATE.validate_peaks(path, "narrow")
            path.write_text("chr1\t0\t5\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "requires 10 columns"):
                AGGREGATE.validate_peaks(path, "narrow")


class ProviderInputTest(unittest.TestCase):
    def invoke(self, treatment, control=""):
        request = base64.b64encode(json.dumps({"peak_id": "p1"}).encode()).decode()
        old = sys.argv
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            sys.argv = [
                "run_macs3_callpeak.py", "--request-base64", request,
                "--treatment", str(treatment), "--control", str(control),
                "--output-dir", str(root / "out"), "--provider-peak", str(root / "peaks"),
                "--reports", str(root / "reports"), "--manifest", str(root / "manifest.json"),
                "--execution", str(root / "execution.json"), "--cpus", "1",
                "--memory-bytes", "1024", "--task-time", "1m", "--environment", "host",
            ]
            try:
                RUNNER.main()
            finally:
                sys.argv = old

    def test_missing_treatment_bam_fails(self):
        with self.assertRaisesRegex(ValueError, "treatment BAM is missing or empty"):
            self.invoke(Path("does-not-exist.bam"))

    def test_missing_control_bam_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            treatment = Path(directory) / "treatment.bam"
            treatment.write_bytes(b"bam")
            with self.assertRaisesRegex(ValueError, "control BAM is missing or empty"):
                self.invoke(treatment, Path(directory) / "missing-control.bam")


if __name__ == "__main__":
    unittest.main()
