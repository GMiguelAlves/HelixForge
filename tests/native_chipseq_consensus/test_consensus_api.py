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


CONTEXT = load("consensus_context", ROOT / "modules/local/consensus_context/resources/usr/bin/validate_consensus_context.py")
INTERVALS = load("consensus_intervals", ROOT / "modules/local/consensus_intervals/resources/usr/bin/run_consensus.py")
IDR = load("idr_provider", ROOT / "modules/local/idr_provider/resources/usr/bin/run_idr.py")
AGGREGATE = load("consensus_aggregate", ROOT / "modules/local/consensus_aggregate/resources/usr/bin/consensus_aggregate.py")
DB_PREFLIGHT = load("db_preflight", ROOT / "modules/local/db_preflight/resources/usr/bin/db_preflight.py")


def records(count=2, peak_type="narrow"):
    return [{
        "group_id": "fixture.group", "peak_id": f"p{index}", "peak_directory": f"p{index}.dir",
        "record_id": f"r{index}", "sample_id": f"s{index}", "dataset": "fixture",
        "experiment_id": "fixture.H3K27ac", "condition": "treated", "target": "H3K27ac",
        "genome_id": "fixture_v1", "peak_type": peak_type, "caller": "macs3",
        "caller_version": "3.0.4", "biological_replicate": str(index), "technical_replicate": "1",
    } for index in range(1, count + 1)]


class ContextContractTest(unittest.TestCase):
    def test_biological_replicates_are_explicit_and_unique(self):
        data = records()
        mode, policy = CONTEXT.validate_group(data, {"replicate_mode": "biological", "replicate_policy": "require_premerged"})
        self.assertEqual((mode, policy), ("biological", "require_premerged"))
        self.assertEqual([row["evidence_replicate_id"] for row in data], ["1", "2"])

    def test_cross_talk_and_unmerged_technical_replicates_fail(self):
        data = records()
        data[1]["genome_id"] = "other"
        with self.assertRaisesRegex(ValueError, "cross-talk"):
            CONTEXT.validate_group(data, {"replicate_mode": "biological", "replicate_policy": "require_premerged"})
        data = records()
        data[1]["biological_replicate"] = "1"
        data[1]["technical_replicate"] = "2"
        with self.assertRaisesRegex(ValueError, "not premerged"):
            CONTEXT.validate_group(data, {"replicate_mode": "biological", "replicate_policy": "require_premerged"})

    def test_technical_mode_requires_preservation(self):
        with self.assertRaisesRegex(ValueError, "requires replicate_policy=preserve"):
            CONTEXT.validate_group(records(), {"replicate_mode": "technical", "replicate_policy": "require_premerged"})


class IntervalContractTest(unittest.TestCase):
    def test_atomic_segments_respect_support_threshold(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, table, bed = root / "multi.tsv", root / "result.tsv", root / "result.bed"
            source.write_text("chr1\t0\t5\t1\t1\t1\t0\nchr1\t5\t10\t2\t1,2\t1\t1\n", encoding="utf-8")
            rows, distribution = INTERVALS.parse_multiinter(
                source, {"id": "g", "support_threshold": 2}, "replicate_support", table, bed
            )
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["support"], 2)
            self.assertEqual(distribution, {1: 1, 2: 1})


class IdrContractTest(unittest.TestCase):
    def request(self):
        return {
            "status": "valid", "strategy": "idr", "provider": "idr", "provider_version": "2.0.4.2",
            "replicate_mode": "biological", "replicate_policy": "require_premerged",
            "replicate_count": 2, "peak_type": "narrow", "id": "fixture.group",
            "parameters": {"idr_threshold": 0.05, "rank_metric": "signal_value"},
            "replicates": [
                {"evidence_replicate_id": str(index), "peak_id": f"p{index}",
                 "peak_directory": f"p{index}.dir", "peak_file": "peaks.narrowPeak"}
                for index in (1, 2)
            ],
        }

    def test_idr_requires_two_narrow_premerged_biological_replicates(self):
        request = self.request()
        request["replicates"] = []
        with self.assertRaisesRegex(ValueError, "exactly two"):
            IDR.validate_request(request, {})

    def test_rank_mapping_command_and_input_checks_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            directories = {}
            for index in (1, 2):
                peak_dir = root / f"p{index}.dir"
                peak_dir.mkdir()
                (peak_dir / "peaks.narrowPeak").write_text(
                    f"chr1\t{index}\t{index + 10}\tp{index}\t100\t.\t5\t10\t8\t4\n", encoding="utf-8"
                )
                directories[peak_dir.name] = str(peak_dir)
            request, peaks = IDR.validate_request(self.request(), directories)
            command = IDR.build_command(request, peaks, root / "out.tsv", root / "idr.log")
            self.assertEqual(command[command.index("--rank") + 1], "signal.value")
            self.assertEqual(command[command.index("--random-seed") + 1], "0")
            self.assertEqual(command[command.index("--idr-threshold") + 1], "0.05")

    def test_idr_output_is_normalized_for_downstream_apis(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, table, bed = root / "idr.tsv", root / "consolidated.tsv", root / "consolidated.bed"
            source.write_text(
                "chr1\t10\t20\tpeak\t540\t.\t5\t10\t8\t4\t1.5\t1.30103\t10\t20\t5\t4\t11\t21\t5\t4\n",
                encoding="utf-8",
            )
            self.assertEqual(IDR.parse_idr_output(source, "fixture.group", table, bed), 1)
            fields = table.read_text(encoding="utf-8").splitlines()[1].split("\t")
            self.assertEqual(fields[0], "fixture.group.idr.000001")
            self.assertAlmostEqual(float(fields[-1]), 0.05, places=6)
            self.assertEqual(bed.read_text(encoding="utf-8"), "chr1\t10\t20\tfixture.group.idr.000001\n")

    def test_completed_idr_manifest_advertises_real_peaks(self):
        document = {
            "type": "idr", "id": "g", "strategy": "idr", "status": "complete",
            "artifacts": {"consolidated_peaks": {"available": True, "path": "consolidated_peaks.tsv"}},
            "replicates": [{}, {}],
        }
        rows = AGGREGATE.summarize({"g": (document, "manifest.json")})
        self.assertTrue(rows[0]["consolidated_peaks_available"])

    def test_differential_binding_accepts_completed_idr_bed(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = root / "fixture.idr_result"
            result.mkdir()
            bed = result / "consolidated_peaks.bed"
            bed.write_text("chr1\t10\t20\tfixture.idr.000001\n", encoding="utf-8")
            document = {
                "schema_version": "1.0", "type": "idr", "id": "fixture", "strategy": "idr",
                "status": "complete", "artifacts": {"consolidated_bed": {
                    "available": True, "path": bed.name, "sha256": IDR.sha256(bed),
                }},
            }
            embedded = result / "manifest.json"
            external = root / "fixture.idr.manifest.json"
            embedded.write_text(json.dumps(document), encoding="utf-8")
            external.write_text(json.dumps(document), encoding="utf-8")
            accepted = DB_PREFLIGHT.consensus_inputs([str(result)], [str(external)])
            self.assertEqual(accepted[0][2], str(bed))

    def test_real_certification_uses_immutable_provider_image(self):
        workflow = (ROOT / ".github/workflows/idr-certification.yml").read_text(encoding="utf-8")
        runner = (ROOT / "tests/native_chipseq_consensus/run_real.sh").read_text(encoding="utf-8")
        digest = "sha256:d6fb2a7eb69bb236278562d08fcd0b62bfbe2e887d330111c6aea1e42cb26caa"
        self.assertIn(digest, workflow)
        self.assertIn(digest, runner)
        self.assertIn("docker pull", workflow)
        self.assertIn("validate_real.py", runner)


if __name__ == "__main__":
    unittest.main()
