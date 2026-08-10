import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


CONTEXT = load("track_context", "modules/local/track_context/resources/usr/bin/validate_track_context.py")


class TrackParameterTest(unittest.TestCase):
    def test_legacy_defaults_are_explicit(self):
        spec = CONTEXT.validate_spec({})
        self.assertEqual((spec["track_format"], spec["normalization"], spec["bin_size"]), ("bigwig", "CPM", 10))
        self.assertEqual((spec["fragment_mode"], spec["extend_reads"], spec["additional_filters"]), ("reads", False, "none"))

    def test_rpgc_requires_effective_size(self):
        with self.assertRaisesRegex(ValueError, "effective_genome_size"):
            CONTEXT.validate_spec({"normalization": "RPGC"})
        spec = CONTEXT.validate_spec({"normalization": "RPGC", "effective_genome_size": 1000})
        self.assertEqual(spec["effective_genome_size"], 1000)

    def test_unsupported_or_hidden_behavior_fails(self):
        for value, pattern in [({"scale_factor": 2}, "scale_factor"), ({"extend_reads": True}, "extend_reads"), ({"additional_filters": "mapq"}, "additional filters"), ({"other": 1}, "unsupported")]:
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, pattern):
                CONTEXT.validate_spec(value)


class IdentityTest(unittest.TestCase):
    def test_manifest_declared_artifacts_are_selected_without_channel_order(self):
        index = CONTEXT.index_by_basename(["/tmp/b.filtered.bam", "/tmp/a.filtered.bam"], "BAM")
        self.assertEqual(CONTEXT.find_artifact(index, "a.filtered.bam", "BAM"), "/tmp/a.filtered.bam")
        with self.assertRaisesRegex(ValueError, "absent"):
            CONTEXT.find_artifact(index, "missing.bam", "BAM")

    def test_reference_contigs_are_preserved_exactly(self):
        with tempfile.TemporaryDirectory() as directory:
            fasta = Path(directory) / "reference.fa"
            fasta.write_text(">chr1\nACGT\n>1\nAC\n", encoding="utf-8")
            self.assertEqual(CONTEXT.reference_contigs(fasta), {"chr1": 4, "1": 2})


class AggregateTest(unittest.TestCase):
    def test_aggregate_joins_reordered_inputs_by_track_id(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            dirs = []
            provider_manifests = []
            statistics_files = []
            statistics_manifests = []
            for identifier in ("track_b", "track_a"):
                result = root / f"{identifier}.result"; result.mkdir()
                (result / "track.bw").write_bytes(identifier.encode())
                provider = {"schema_version": "1.0", "type": "track_generation", "id": identifier, "track_role": "individual", "record_id": identifier, "record_ids": [identifier], "sample_ids": [identifier], "dataset": "d", "condition": "c", "target": "t", "genome_id": "g", "build": "g", "parameters": {"normalization": "CPM", "bin_size": 10}, "artifacts": {"primary_track": {"path": "track.bw"}}, "status": "complete"}
                (result / "manifest.json").write_text(json.dumps(provider), encoding="utf-8")
                external = root / f"{identifier}.manifest.json"; external.write_text(json.dumps(provider), encoding="utf-8")
                stats = {"id": identifier, "source_reads": 1, "mapped_reads": 1, "bases_covered": 4, "number_of_bins": 1}
                stats_path = root / f"{identifier}.statistics.json"; stats_path.write_text(json.dumps(stats), encoding="utf-8")
                stats_manifest = root / f"{identifier}.statistics.manifest.json"; stats_manifest.write_text(json.dumps({"type": "track_statistics", "id": identifier}), encoding="utf-8")
                dirs.append(result); provider_manifests.append(external); statistics_files.append(stats_path); statistics_manifests.append(stats_manifest)
            output = root / "aggregate"
            command = [sys.executable, str(ROOT / "modules/local/track_aggregate/resources/usr/bin/track_aggregate.py")]
            for option, values in (("--track-dir", dirs), ("--track-manifest", reversed(provider_manifests)), ("--statistics-json", statistics_files), ("--statistics-manifest", reversed(statistics_manifests))):
                for value in values: command.extend([option, str(value)])
            command.extend(["--output-dir", str(output), "--manifest", str(root / "aggregate.json"), "--execution", str(root / "execution.json"), "--versions", str(root / "versions.yml"), "--cpus", "1", "--memory-bytes", "1000", "--task-time", "1m"])
            subprocess.run(command, check=True)
            rows = (output / "tracks.tsv").read_text(encoding="utf-8").splitlines()
            self.assertIn("track_a", rows[1]); self.assertIn("track_b", rows[2])


if __name__ == "__main__":
    unittest.main()
