import importlib.util
import json
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT = load("peak_qc_context", ROOT / "modules/local/peak_qc_context/resources/usr/bin/validate_peak_qc_context.py")
FRIP = load("frip", ROOT / "modules/local/frip/resources/usr/bin/run_frip.py")
STATISTICS = load("peak_statistics", ROOT / "modules/local/peak_statistics/resources/usr/bin/peak_statistics.py")
AGGREGATE = load("peak_qc_aggregate", ROOT / "modules/local/peak_qc_aggregate/resources/usr/bin/peak_qc_aggregate.py")


class ContextTest(unittest.TestCase):
    def fixture(self, root):
        paths = {name: root / name for name in ("sample.bam", "sample.bam.bai", "bam.json", "peaks.narrowPeak", "peak.json", "reference.fa")}
        paths["sample.bam"].write_bytes(b"bam")
        paths["sample.bam.bai"].write_bytes(b"bai")
        paths["reference.fa"].write_text(">chr1\n" + "A" * 100 + "\n", encoding="utf-8")
        paths["peaks.narrowPeak"].write_text("chr1\t10\t20\tp1\t100\t.\t5\t10\t8\t4\n", encoding="utf-8")
        paths["bam.json"].write_text(json.dumps({"id": "sample", "duplicate_policy": "remove"}), encoding="utf-8")
        paths["peak.json"].write_text(json.dumps({
            "id": "sample.H3K27ac.narrow.macs3", "record_id": "sample", "sample_id": "sample",
            "target": "H3K27ac", "peak_type": "narrow", "caller": "macs3",
        }), encoding="utf-8")
        meta = {
            "peak_id": "sample.H3K27ac.narrow.macs3", "record_id": "sample", "sample_id": "sample",
            "target": "H3K27ac", "peak_type": "narrow", "caller": "macs3", "caller_version": "3.0.4",
            "single_end": False, "biological_replicate": "1", "technical_replicate": "1",
        }
        return paths, meta

    def test_layout_resolves_fragments_and_explicit_filters(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, meta = self.fixture(Path(directory))
            request = CONTEXT.build_request(
                meta, paths["sample.bam"], paths["sample.bam.bai"], paths["bam.json"],
                paths["peaks.narrowPeak"], paths["peak.json"], paths["reference.fa"], None, {},
            )
            self.assertEqual(request["unit"], "fragments")
            self.assertEqual(request["filters"]["include_flags"], 2)
            self.assertEqual(request["filters"]["exclude_flags"], 2820)
            self.assertEqual(request["filters"]["bam_duplicate_policy"], "remove")

    def test_identity_mismatch_and_reference_overflow_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, meta = self.fixture(Path(directory))
            bad = json.loads(paths["peak.json"].read_text(encoding="utf-8"))
            bad["sample_id"] = "other"
            paths["peak.json"].write_text(json.dumps(bad), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "does not match"):
                CONTEXT.build_request(meta, paths["sample.bam"], paths["sample.bam.bai"], paths["bam.json"], paths["peaks.narrowPeak"], paths["peak.json"], paths["reference.fa"], None, {})
            paths, meta = self.fixture(Path(directory))
            paths["peaks.narrowPeak"].write_text("chr1\t90\t101\tp1\t100\t.\t5\t10\t8\t4\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "exceeds"):
                CONTEXT.build_request(meta, paths["sample.bam"], paths["sample.bam.bai"], paths["bam.json"], paths["peaks.narrowPeak"], paths["peak.json"], paths["reference.fa"], None, {})

    def test_single_end_fragments_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, meta = self.fixture(Path(directory))
            meta["single_end"] = True
            with self.assertRaisesRegex(ValueError, "cannot use fragment"):
                CONTEXT.build_request(meta, paths["sample.bam"], paths["sample.bam.bai"], paths["bam.json"], paths["peaks.narrowPeak"], paths["peak.json"], paths["reference.fa"], None, {"unit": "fragments"})

    def test_conflicting_flags_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            paths, meta = self.fixture(Path(directory))
            with self.assertRaisesRegex(ValueError, "both required and excluded"):
                CONTEXT.build_request(meta, paths["sample.bam"], paths["sample.bam.bai"], paths["bam.json"], paths["peaks.narrowPeak"], paths["peak.json"], paths["reference.fa"], None, {"include_flags": 4})


class FripConversionTest(unittest.TestCase):
    def test_bedpe_counts_template_once(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, target = root / "input.bedpe", root / "fragments.bed"
            source.write_text("chr1\t10\t20\tchr1\t40\t50\tread1\t60\t+\t-\n", encoding="utf-8")
            self.assertEqual(FRIP.bedpe_to_fragments(source, target), 1)
            self.assertEqual(target.read_text(encoding="utf-8"), "chr1\t10\t50\tread1\n")

    def test_duplicate_template_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            line = "chr1\t10\t20\tchr1\t40\t50\tread1\t60\t+\t-\n"
            source, target = root / "input.bedpe", root / "fragments.bed"
            source.write_text(line + line, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "more than once"):
                FRIP.bedpe_to_fragments(source, target)


class StatisticsTest(unittest.TestCase):
    def test_narrow_and_broad(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            narrow, broad = root / "p.narrowPeak", root / "p.broadPeak"
            narrow.write_text("chr1\t0\t10\tp1\t100\t.\t5\t10\t8\t4\n", encoding="utf-8")
            broad.write_text("chr1\t1\t21\tp2\t200\t.\t6\t11\t9\n", encoding="utf-8")
            self.assertEqual(STATISTICS.parse_peaks(narrow, "narrow")[0]["width"], 10)
            self.assertEqual(STATISTICS.parse_peaks(broad, "broad")[0]["width"], 20)

    def test_empty_peak_set_is_valid(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "empty.narrowPeak"
            path.write_text("", encoding="utf-8")
            self.assertEqual(STATISTICS.parse_peaks(path, "narrow"), [])


class AggregateTest(unittest.TestCase):
    def record(self, sample="s"):
        identity = {"id": "p", "record_id": "r", "sample_id": sample, "target": "t", "biological_replicate": "1", "technical_replicate": "1", "peak_type": "narrow", "caller": "macs3", "caller_version": "3.0.4"}
        frip = {**identity, "metrics": {"unit": "fragments", "frip": 0.5, "total_units": 10, "units_in_peaks": 5, "total_alignments_input": 20, "eligible_alignments": 20}}
        stats = {**identity, "metrics": {"peak_count": 1, "valid_peak_count": 1, "peak_width": {"min": 10, "max": 10, "mean": 10, "median": 10}, "peak_score": {"mean": 100, "median": 100}, "signal_value": {"mean": 5, "median": 5}}}
        return frip, stats

    def test_matching_manifests_combine(self):
        frip, stats = self.record()
        rows = AGGREGATE.combine({"p": (frip, "f")}, {"p": (stats, "s")})
        self.assertEqual(rows[0]["frip"], 0.5)

    def test_identity_mismatch_fails(self):
        frip, stats = self.record()
        stats["sample_id"] = "other"
        with self.assertRaisesRegex(ValueError, "disagree on sample_id"):
            AGGREGATE.combine({"p": (frip, "f")}, {"p": (stats, "s")})


if __name__ == "__main__":
    unittest.main()
