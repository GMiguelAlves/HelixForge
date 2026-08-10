import base64
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
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONTEXT = load("peak_annotation_context", "modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py")
ANNOTATOR = load("peak_annotator", "modules/local/peak_annotator/resources/usr/bin/run_peak_annotator.py")


class ParameterContractTest(unittest.TestCase):
    def test_compatibility_defaults_are_explicit(self):
        spec = CONTEXT.validate_spec({})
        self.assertEqual(spec["promoter_upstream"], 2000)
        self.assertEqual(spec["promoter_downstream"], 500)
        self.assertEqual(spec["feature_priority"][0], "promoter")
        self.assertEqual(spec["gene_assignment"], "first")

    def test_unsupported_scientific_rules_fail(self):
        with self.assertRaisesRegex(ValueError, "nearest-TSS"):
            CONTEXT.validate_spec({"max_tss_distance": 1000})
        with self.assertRaisesRegex(ValueError, "feature_priority"):
            CONTEXT.validate_spec({"feature_priority": ["gene"]})
        with self.assertRaisesRegex(ValueError, "strand_aware"):
            CONTEXT.validate_spec({"strand_aware": True})


class CoordinateContractTest(unittest.TestCase):
    def test_invalid_peak_coordinates_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            peaks = Path(directory) / "bad.bed"
            peaks.write_text("chr1\t10\t5\tbad\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid half-open"):
                CONTEXT.parse_peak_contigs(peaks)

    def test_seqnames_are_not_rewritten(self):
        with tempfile.TemporaryDirectory() as directory:
            reference = Path(directory) / "reference.fa"
            reference.write_text(">chr1\nACGT\n>1\nACGT\n", encoding="utf-8")
            self.assertEqual(CONTEXT.parse_fasta_contigs(reference), {"chr1", "1"})


class ProviderContractTest(unittest.TestCase):
    def test_priority_and_multi_gene_policy_are_deterministic(self):
        with tempfile.TemporaryDirectory() as directory:
            annotation = Path(directory) / "annotation.gtf"
            annotation.write_text(
                'chr1\tx\tgene\t11\t30\t.\t+\t.\tgene_id "geneB";\n'
                'chr1\tx\tgene\t11\t30\t.\t+\t.\tgene_id "geneA";\n', encoding="utf-8"
            )
            features = ANNOTATOR.read_annotation(annotation, 5, 2)
            promoter_hits = ANNOTATOR.overlapping(features["promoter"], "chr1", 8, 12)
            self.assertEqual([row[3] for row in promoter_hits], ["geneA", "geneB"])


class FullContextTest(unittest.TestCase):
    def test_build_mismatch_fails_early(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            subprocess.run([sys.executable, str(ROOT / "tests/native_chipseq_peak_annotation/generate_fixture.py"), "--outdir", str(fixture)], check=True)
            reference_manifest = fixture / "reference_manifest.json"
            document = json.loads(reference_manifest.read_text(encoding="utf-8"))
            document["genome_id"] = document["build"] = "other_v1"
            reference_manifest.write_text(json.dumps(document), encoding="utf-8")
            meta = {"id": "fixture.peaks.annotation", "source_id": "fixture.peaks", "genome_id": "fixture_v1"}
            command = [
                sys.executable, str(ROOT / "modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py"),
                "--meta-base64", base64.b64encode(json.dumps(meta).encode()).decode(),
                "--peaks", str(fixture / "fixture.peaks.bed"), "--peak-manifest", str(fixture / "peak_manifest.json"),
                "--reference", str(fixture / "reference.fa"), "--reference-manifest", str(reference_manifest),
                "--annotation", str(fixture / "annotation.gtf"),
                "--spec-base64", base64.b64encode(b"{}").decode(),
                "--request", str(fixture / "request.json"), "--report", str(fixture / "report.json"),
            ]
            result = subprocess.run(command, capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 2)
            self.assertIn("genome/build mismatch", result.stderr)


class LightweightChainTest(unittest.TestCase):
    def test_semantic_outputs_and_statistics(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            subprocess.run([sys.executable, str(ROOT / "tests/native_chipseq_peak_annotation/generate_fixture.py"), "--outdir", str(fixture)], check=True)
            meta = {"id": "fixture.peaks.annotation", "source_id": "fixture.peaks", "genome_id": "fixture_v1", "organism": "fixture"}
            parameters = {"promoter_upstream": 5, "promoter_downstream": 2}
            request = fixture / "request.json"
            context = [
                sys.executable, str(ROOT / "modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py"),
                "--meta-base64", base64.b64encode(json.dumps(meta).encode()).decode(),
                "--peaks", str(fixture / "fixture.peaks.bed"), "--peak-manifest", str(fixture / "peak_manifest.json"),
                "--reference", str(fixture / "reference.fa"), "--reference-manifest", str(fixture / "reference_manifest.json"),
                "--annotation", str(fixture / "annotation.gtf"),
                "--spec-base64", base64.b64encode(json.dumps(parameters).encode()).decode(),
                "--request", str(request), "--report", str(fixture / "context.json"),
            ]
            subprocess.run(context, check=True)
            output = fixture / "annotation_result"
            provider_manifest = fixture / "annotation_manifest.json"
            subprocess.run([
                sys.executable, str(ROOT / "modules/local/peak_annotator/resources/usr/bin/run_peak_annotator.py"),
                "--request", str(request), "--peaks", str(fixture / "fixture.peaks.bed"),
                "--annotation", str(fixture / "annotation.gtf"), "--output-dir", str(output),
                "--manifest", str(provider_manifest), "--execution", str(fixture / "provider_execution.json"),
                "--versions", str(fixture / "provider_versions.yml"), "--cpus", "1", "--memory-bytes", "1000",
                "--task-time", "1m", "--nextflow-version", "test",
            ], check=True)
            rows = (output / "annotated_peaks.tsv").read_text(encoding="utf-8").splitlines()
            self.assertIn("peak_promoter\tchrStub\t8\t12\tpromoter", rows[1])
            self.assertIn("peak_intron\tchrStub\t16\t19\tintron", rows[2])
            self.assertIn("peak_intergenic\tchrStub\t50\t55\tintergenic", rows[3])
            statistics_json = fixture / "statistics.json"
            statistics_manifest = fixture / "statistics_manifest.json"
            subprocess.run([
                sys.executable, str(ROOT / "modules/local/peak_annotation_statistics/resources/usr/bin/peak_annotation_statistics.py"),
                "--annotation-dir", str(output), "--annotation-manifest", str(provider_manifest),
                "--output-json", str(statistics_json), "--output-tsv", str(fixture / "statistics.tsv"),
                "--reports", str(fixture / "statistics_reports"), "--manifest", str(statistics_manifest),
                "--execution", str(fixture / "statistics_execution.json"), "--versions", str(fixture / "statistics_versions.yml"),
                "--cpus", "1", "--memory-bytes", "1000", "--task-time", "1m",
            ], check=True)
            metrics = json.loads(statistics_json.read_text(encoding="utf-8"))
            self.assertEqual((metrics["total_peaks"], metrics["annotated_peaks"], metrics["unassociated_peaks"]), (3, 2, 1))
            aggregate = fixture / "aggregate"
            subprocess.run([
                sys.executable, str(ROOT / "modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py"),
                "--annotation-dir", str(output), "--annotation-manifest", str(provider_manifest),
                "--statistics-json", str(statistics_json), "--statistics-manifest", str(statistics_manifest),
                "--output-dir", str(aggregate), "--manifest", str(fixture / "aggregate_manifest.json"),
                "--execution", str(fixture / "aggregate_execution.json"), "--versions", str(fixture / "aggregate_versions.yml"),
                "--cpus", "1", "--memory-bytes", "1000", "--task-time", "1m",
            ], check=True)
            manifest = json.loads((aggregate / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["type"], "peak_annotation_aggregate")
            self.assertEqual(manifest["records"], 1)


if __name__ == "__main__":
    unittest.main()
