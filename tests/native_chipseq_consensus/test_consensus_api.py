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
IDR = load("idr_provider", ROOT / "modules/local/idr_provider/resources/usr/bin/prepare_idr_provider.py")
AGGREGATE = load("consensus_aggregate", ROOT / "modules/local/consensus_aggregate/resources/usr/bin/consensus_aggregate.py")


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
    def test_idr_requires_two_narrow_premerged_biological_replicates(self):
        request = {
            "status": "valid", "strategy": "idr", "provider": "idr_pending",
            "replicate_mode": "biological", "replicate_policy": "require_premerged",
            "replicate_count": 2, "peak_type": "narrow", "replicates": [],
        }
        with self.assertRaisesRegex(ValueError, "exactly two"):
            IDR.validate_request(request, {})

    def test_pending_idr_manifest_never_advertises_peaks(self):
        document = {
            "type": "idr", "id": "g", "strategy": "idr", "status": "not_implemented",
            "artifacts": {"consolidated_peaks": {"available": False}}, "replicates": [{}, {}],
        }
        rows = AGGREGATE.summarize({"g": (document, "manifest.json")})
        self.assertFalse(rows[0]["consolidated_peaks_available"])


if __name__ == "__main__":
    unittest.main()
