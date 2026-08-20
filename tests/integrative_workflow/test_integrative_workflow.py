from __future__ import annotations

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "bin"))

from integration.evidence.io import load_bindings, read_tsv, sha256  # noqa: E402
from integration.evidence.provider import build_evidence  # noqa: E402
from integration.harmonization import build_harmonization  # noqa: E402
from integration.interpretation.model import build_regulatory_interpretation  # noqa: E402
from integration.interpretation.scoring import build_candidate_scores  # noqa: E402
from integration.interpretation.statistics import build_cross_assay_statistics  # noqa: E402
from integration.molecular import build_master_evidence  # noqa: E402
from integration.workflow.functional import build_functional_analysis  # noqa: E402
from integration.workflow.preflight import prepare_inputs  # noqa: E402
from integration.workflow.reporting import build_report  # noqa: E402
from integration.workflow.terminal import build_integrative_run_manifest  # noqa: E402
from integration.workflow.visualization import build_visualizations  # noqa: E402
from tests.integrative_workflow.prepare_fixture import build_fixture  # noqa: E402

POLICY = ROOT / "assets" / "integration" / "interpretation_policy.v1.json"
MARKS = ROOT / "assets" / "integration" / "mark_roles.v1.tsv"
HARMONIZATION = ROOT / "assets" / "integration" / "harmonization_policy.v1.json"
CONTEXT = ROOT / "tests" / "interpretation" / "fixture" / "prioritization_context.tsv"
ANNOTATION = ROOT / "tests" / "integrative_legacy_characterization" / "fixture" / "inputs" / "functional_annotation.tsv"
GOLDEN_FUNCTIONAL = ROOT / "tests" / "integrative_legacy_characterization" / "golden" / "functional" / "100-functional-analysis" / "functional_enrichment.tsv"


def native_components(root: Path):
    fixture = root / "fixture"
    rna_manifest, chip_manifest = build_fixture(fixture)
    prepared = root / "prepared"
    prepare_inputs(rna_manifest, rna_manifest.parent / "integration_artifacts", chip_manifest, chip_manifest.parent / "integration_artifacts", prepared)
    rna_evidence, chip_evidence = root / "rna_evidence", root / "chip_evidence"
    rna_declared = sorted((prepared / "rnaseq_artifacts").glob("*/*"))
    chip_declared = sorted((prepared / "chipseq_artifacts").glob("*/*"))
    rna_bindings = load_bindings(prepared / "rnaseq_bindings.json", rna_declared)
    chip_bindings = load_bindings(prepared / "chipseq_bindings.json", chip_declared)
    build_evidence(json.loads((prepared / "rnaseq_run_manifest.json").read_text()), rna_bindings, rna_evidence)
    build_evidence(json.loads((prepared / "chipseq_run_manifest.json").read_text()), chip_bindings, chip_evidence)
    harmonization, integration = root / "harmonization", root / "integration"
    classification, scoring, interpretation = root / "classification", root / "scoring", root / "interpretation"
    functional, visualization, report = root / "functional", root / "visualization", root / "report"
    build_harmonization(rna_evidence, chip_evidence, harmonization, json.loads(HARMONIZATION.read_text(encoding="utf-8")))
    build_master_evidence(rna_evidence, chip_evidence, harmonization, integration)
    build_regulatory_interpretation(integration, POLICY, MARKS, classification)
    build_candidate_scores(integration, classification, POLICY, CONTEXT, scoring)
    build_cross_assay_statistics(integration, classification, scoring, POLICY, MARKS, CONTEXT, interpretation)
    build_functional_analysis(interpretation, ANNOTATION, 4, functional)
    build_visualizations(interpretation, functional, visualization, 4)
    build_report(prepared, rna_evidence, chip_evidence, harmonization, integration, interpretation, functional, visualization, report, "Fixture report")
    return {"rna_manifest": prepared / "rnaseq_run_manifest.json", "chip_manifest": prepared / "chipseq_run_manifest.json", "prepared": prepared, "rna_evidence": rna_evidence, "chip_evidence": chip_evidence, "harmonization": harmonization, "integration": integration, "interpretation": interpretation, "functional": functional, "visualization": visualization, "report": report}


class IntegrativePreflightTest(unittest.TestCase):
    def test_portable_manifests_checksums_and_reference_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = build_fixture(root / "fixture")
            report = prepare_inputs(rna, rna.parent / "integration_artifacts", chip, chip.parent / "integration_artifacts", root / "prepared")
            self.assertEqual("compatible", report["reference_compatibility"])
            self.assertGreater(report["inputs"][0]["bound_artifacts"], 0)
            self.assertTrue((root / "prepared" / "rnaseq_bindings.json").is_file())
            bindings = load_bindings(
                root / "prepared" / "chipseq_bindings.json",
                list(reversed(sorted((root / "prepared" / "chipseq_artifacts").glob("*/*")))),
            )
            self.assertEqual({"chip.annotation", "chip.db"}, set(bindings))

    def test_incompatible_annotation_fails_early(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rna, chip = build_fixture(root / "fixture")
            document = json.loads(chip.read_text())
            document["reference"]["annotation_id"] = "other_annotation"
            chip.write_text(json.dumps(document), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "annotation_id incompatible"):
                prepare_inputs(rna, rna.parent / "integration_artifacts", chip, chip.parent / "integration_artifacts", root / "prepared")


class FunctionalReportingTest(unittest.TestCase):
    def test_legacy_functional_summary_and_formal_bh(self):
        with tempfile.TemporaryDirectory() as directory:
            products = native_components(Path(directory))
            self.assertEqual(GOLDEN_FUNCTIONAL.read_text(encoding="utf-8"), (products["functional"] / "functional_enrichment.tsv").read_text(encoding="utf-8"))
            _fields, tests = read_tsv(products["functional"] / "functional_tests.tsv")
            self.assertTrue(tests)
            self.assertTrue(all(0 <= float(row["padj"]) <= 1 for row in tests))
            self.assertTrue(all(sum(int(row[name]) for name in ("n11", "n10", "n01", "n00")) == 8 for row in tests))

    def test_missing_annotation_is_explicit_complete_empty(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            products = native_components(root / "base")
            empty = root / "empty.tsv"
            empty.write_text("gene_id\tterm\tdescription\n", encoding="utf-8")
            output = root / "functional-empty"
            manifest = build_functional_analysis(products["interpretation"], empty, 4, output)
            self.assertEqual("complete_empty", manifest["status"])
            self.assertFalse((output / "functional_enrichment.tsv").exists())

    def test_report_is_science_free_searchable_and_assets_exist(self):
        with tempfile.TemporaryDirectory() as directory:
            products = native_components(Path(directory))
            report = json.loads((products["report"] / "report_manifest.json").read_text())
            html_text = (products["report"] / "integrative_report.html").read_text()
            self.assertFalse(report["science_recalculated"])
            for section in ("Candidate prioritization", "Cross-assay statistics", "Functional analysis", "Methods and software provenance"):
                self.assertIn(section, html_text)
            self.assertIn("candidate-search", html_text)
            _fields, figures = read_tsv(products["visualization"] / "visualization_manifest.tsv")
            self.assertTrue(all((products["visualization"] / row["path"]).is_file() for row in figures))
            self.assertTrue(all(row["checksum"] == sha256(products["visualization"] / row["path"]) for row in figures))


class TerminalAndIsolationTest(unittest.TestCase):
    def test_terminal_manifest_traceability_and_json_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            products = native_components(root)
            output = root / "integrative_run_manifest.json"
            document = build_integrative_run_manifest(products["rna_manifest"], products["chip_manifest"], products["prepared"], products["rna_evidence"], products["chip_evidence"], products["harmonization"], products["integration"], products["interpretation"], products["functional"], products["visualization"], products["report"], {"id": "fixture.integrative", "workflow": "integrative", "run_id": "fixture", "run_name": "fixture", "helixforge_version": "test", "git_commit": "fixture", "nextflow_version": "25.10.7", "profile": "test", "parameters": {}, "source": {"type": "helixforge"}}, output)
            self.assertEqual("complete", document["status"])
            self.assertEqual(2, len(document["input_manifests"]))
            self.assertTrue(any(item["artifact_type"] == "candidate_ranking" for item in document["artifacts"]))
            self.assertTrue(all(item["checksum"]["value"] for item in document["artifacts"]))
            try:
                from validate_integration_manifest import jsonschema_errors
                errors = jsonschema_errors(document, ROOT / "schemas" / "integration")
                if errors and errors[0].startswith("JSON Schema validation requires"):
                    self.skipTest(errors[0])
                self.assertEqual([], errors)
            except ImportError:
                self.skipTest("jsonschema runtime unavailable")

    def test_active_native_workflow_has_no_legacy_dependency(self):
        active = "\n".join((ROOT / path).read_text(encoding="utf-8") for path in ("workflows/integrative.nf", "subworkflows/local/integrative/native_integration.nf"))
        self.assertNotIn("LEGACY_STEP", active)
        self.assertNotIn("pipelines/integrative/legacy", active)
        self.assertNotIn(".done", active)

    def test_all_wires_terminal_bundles_not_completion_tokens(self):
        active = (ROOT / "workflows" / "all.nf").read_text(encoding="utf-8")
        self.assertIn("ALL_RNASEQ.out.terminal_bundle", active)
        self.assertIn("ALL_CHIPSEQ.out.terminal_bundle", active)
        self.assertNotIn("completed.mix", active)


if __name__ == "__main__":
    unittest.main()
