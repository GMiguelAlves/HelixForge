import base64
import copy
import csv
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    return module


FIXTURE = load("regional_annotation_fixture", "tests/native_chipseq_peak_annotation/generate_regional_fixture.py")
CONTEXT = load("regional_annotation_context", "modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py")
REPORT_CONTEXT = load("regional_report_context", "modules/local/report_context/resources/usr/bin/validate_report_context.py")
REPORT = load("regional_report_aggregate", "modules/local/report_aggregate/resources/usr/bin/report_aggregate.py")
HTML = load("regional_report_html", "modules/local/report_generator/resources/usr/bin/generate_chipseq_report.py")


def rows(path):
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def run(relative, *args, check=True):
    return subprocess.run([sys.executable, str(ROOT / relative), *map(str, args)],
                          capture_output=True, text=True, check=check)


class RegionalAnnotationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        request = FIXTURE.generate(self.root)
        # Known fixture output, independent of the interval-consolidation implementation.
        self.peaks = self.root / "consolidated_peaks.bed"
        self.peaks.write_text("chrStub\t100\t500\tregion1\nchrStub\t501\t601\tregion2\n", encoding="utf-8")
        self.core = self.root / "core_supported.bed"
        self.core.write_text("chrStub\t299\t300\tcore1\n", encoding="utf-8")
        self.doc = {**request, "type": "consensus", "status": "complete", "artifacts": {
            "consolidated_bed": {"available": True, "path": self.peaks.name, "sha256": FIXTURE.digest(self.peaks)},
            "core_supported_bed": {"available": True, "path": self.core.name, "sha256": FIXTURE.digest(self.core)},
        }, "statistics": {"consolidated_peaks": 2, "candidate_bp": 500, "core_bp": 1, "spatially_supported_regions": 1},
           "semantics": {"consolidated_bed": "candidate_envelopes_not_confirmed_occupancy",
                         "positive_gap_filling_bp": 0, "reproducible_occupancy": "not_assessed"}}
        self.manifest = self.root / "catalog_manifest.json"
        self.meta = dict(id="fixture.catalog.annotation", source_id="fixture.catalog", genome_id="fixture_v1")
        self.request = self.root / "annotation_request.json"

    def context(self, peaks=None, check=True):
        FIXTURE.dump(self.manifest, self.doc)
        return run("modules/local/peak_annotation_context/resources/usr/bin/validate_peak_annotation_context.py",
            "--meta-base64", base64.b64encode(json.dumps(self.meta).encode()).decode(),
            "--peaks", peaks or self.peaks, "--peak-manifest", self.manifest,
            "--reference", self.root / "reference.fa", "--reference-manifest", self.root / "reference_manifest.json",
            "--annotation", self.root / "annotation.gtf", "--spec-base64", base64.b64encode(json.dumps(
                dict(promoter_upstream=0, promoter_downstream=0, gene_assignment="all")).encode()).decode(),
            "--request", self.request, "--report", self.root / "context.json", check=check)

    def annotate(self, peaks=None, check=True):
        self.output = self.root / "annotation"
        self.provider_manifest = self.root / "provider_manifest.json"
        return run("modules/local/peak_annotator/resources/usr/bin/run_peak_annotator.py",
            "--request", self.request, "--peaks", peaks or self.peaks, "--annotation", self.root / "annotation.gtf",
            "--output-dir", self.output, "--manifest", self.provider_manifest,
            "--execution", self.root / "execution.json", "--versions", self.root / "versions.yml",
            "--cpus", 1, "--memory-bytes", 1000, "--task-time", "1m", "--nextflow-version", "test", check=check)

    def test_tail_and_single_library_associations_survive_without_gap_filling(self):
        before = (FIXTURE.digest(self.peaks), FIXTURE.digest(self.core))
        self.context(); self.annotate()
        annotated = rows(self.output / "annotated_peaks.tsv")
        self.assertEqual([(int(r["start"]), int(r["end"])) for r in annotated], [(100, 500), (501, 601)])
        associations = rows(self.output / "peak_gene_associations.tsv")
        self.assertEqual({r["gene_id"] for r in associations}, {"left_tail", "right_tail", "single_library"})
        self.assertTrue(all(r["source_representation"] == "regional_candidate_catalog" and r["occupancy_status"] == "not_assessed" for r in associations))
        self.assertEqual(before, (FIXTURE.digest(self.peaks), FIXTURE.digest(self.core)))

    def test_context_rejects_core_as_catalog_input(self):
        result = self.context(peaks=self.core, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("peak artifact checksum", result.stderr)
        self.assertFalse(self.request.exists())

    def test_provider_rejects_substitution_after_context(self):
        self.context()
        result = self.annotate(peaks=self.core, check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("differs from the validated request", result.stderr)
        self.assertFalse(self.output.exists())

    def test_unsupported_gap_or_occupancy_claim_fails(self):
        for changes in ({"positive_gap_filling_bp": 1}, {"reproducible_occupancy": "confirmed"}, {"consolidated_bed": "core"}):
            doc = copy.deepcopy(self.doc); doc["semantics"].update(changes)
            with self.subTest(changes=changes), self.assertRaisesRegex(ValueError, "candidate envelopes"):
                CONTEXT.regional_representation(doc)

    def test_missing_core_declaration_fails(self):
        del self.doc["artifacts"]["core_supported_bed"]
        result = self.context(check=False)
        self.assertEqual(result.returncode, 2)
        self.assertIn("core_supported_bed", result.stderr)

    def test_nonregional_requests_keep_existing_semantics(self):
        self.assertIsNone(CONTEXT.regional_representation({"type": "consensus", "strategy": "replicate_support"}))
        self.assertIsNone(CONTEXT.regional_representation({"type": "peak_calling", "provider": "macs3"}))

    def test_annotation_aggregate_and_html_preserve_candidate_semantics(self):
        self.context(); self.annotate()
        stats, stats_manifest = self.root / "statistics.json", self.root / "statistics_manifest.json"
        run("modules/local/peak_annotation_statistics/resources/usr/bin/peak_annotation_statistics.py",
            "--annotation-dir", self.output, "--annotation-manifest", self.provider_manifest,
            "--output-json", stats, "--output-tsv", self.root / "statistics.tsv", "--reports", self.root / "statistics_reports",
            "--manifest", stats_manifest, "--execution", self.root / "statistics_execution.json",
            "--versions", self.root / "statistics_versions.yml", "--cpus", 1, "--memory-bytes", 1000, "--task-time", "1m")
        aggregate = self.root / "aggregate"
        run("modules/local/peak_annotation_aggregate/resources/usr/bin/peak_annotation_aggregate.py",
            "--annotation-dir", self.output, "--annotation-manifest", self.provider_manifest,
            "--statistics-json", stats, "--statistics-manifest", stats_manifest, "--output-dir", aggregate,
            "--manifest", self.root / "aggregate_manifest.json", "--execution", self.root / "aggregate_execution.json",
            "--versions", self.root / "aggregate_versions.yml", "--cpus", 1, "--memory-bytes", 1000, "--task-time", "1m")
        self.assertEqual({r["gene_id"] for r in rows(aggregate / "peak_gene_associations.tsv")}, {"left_tail", "right_tail", "single_library"})
        self.assertEqual(rows(aggregate / "statistics.tsv")[0]["unique_genes"], "3")
        doc = json.loads((aggregate / "manifest.json").read_text())
        source = json.loads(self.provider_manifest.read_text())
        self.assertEqual(doc["source_representations"][0]["support_core"]["sha256"], FIXTURE.digest(self.core))
        inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project":
            dict(project_id="fixture", dataset="fixture", genome_id="fixture_v1", build="fixture_v1"),
            "required_components": ["annotation", "consensus_idr"], "components": [
                {"component": "annotation", "manifest": "annotation"}, {"component": "annotation", "manifest": "aggregate"},
                {"component": "consensus_idr", "manifest": "consensus"}]}
        context = REPORT_CONTEXT.validate(inventory, [self.manifest, self.provider_manifest, aggregate / "manifest.json"])
        artifacts = REPORT.load_semantic_artifacts([aggregate / "statistics.tsv"], REPORT.declared_checksums([self.doc, source, doc]))
        data = REPORT.aggregate(context, [self.doc, source, doc], artifacts)
        evidence = data["sections"]["annotation"]["data"]["source_representations"]
        self.assertEqual(len(evidence), 1)  # Duplicate aggregate/provider declarations agree.
        self.assertEqual(evidence[0]["source_statistics"]["core_bp"], 1)
        page = HTML.generate_html(data, {"provider": "html_v1", "language": "en"})
        self.assertIn("Regional candidate associations", page)
        self.assertIn("without filling positive gaps", page)
        self.assertIn("not_assessed", page)
        self.assertIn("core_supported.bed", page)

    def test_empty_catalog_does_not_fall_back_to_core(self):
        self.peaks.write_text("", encoding="utf-8")
        self.doc["artifacts"]["consolidated_bed"]["sha256"] = FIXTURE.digest(self.peaks)
        self.context(); self.annotate()
        self.assertEqual(rows(self.output / "annotated_peaks.tsv"), [])
        self.assertEqual(rows(self.output / "peak_gene_associations.tsv"), [])
        self.assertEqual(json.loads(self.provider_manifest.read_text())["status"], "complete_empty")


if __name__ == "__main__":
    unittest.main()
