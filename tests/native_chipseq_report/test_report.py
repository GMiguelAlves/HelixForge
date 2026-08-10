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


CONTEXT = load("report_context", "modules/local/report_context/resources/usr/bin/validate_report_context.py")
AGGREGATE = load("report_aggregate", "modules/local/report_aggregate/resources/usr/bin/report_aggregate.py")
GENERATOR = load("report_generator", "modules/local/report_generator/resources/usr/bin/generate_chipseq_report.py")


class ReportContextTest(unittest.TestCase):
    def setUp(self):
        self.project = {"project_id": "p", "dataset": "d", "genome_id": "g", "build": "b"}

    def write(self, root, name, document):
        path = root / name; path.write_text(json.dumps(document), encoding="utf-8"); return path

    def test_optional_components_are_not_requested(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.write(root, "bam.json", {"schema_version": "1.0", "type": "bam_final", "id": "r1", "record_id": "r1", "sample_id": "s1", "dataset": "d", "status": "complete"})
            inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project": self.project, "required_components": ["bam"], "components": [{"component": "bam", "manifest": "ignored", "artifacts": []}]}
            result = CONTEXT.validate(inventory, [manifest])
            self.assertEqual(result["components"]["bam"]["status"], "available")
            self.assertEqual(result["components"]["tracks"]["status"], "not_requested")

    def test_required_missing_fails(self):
        inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project": self.project, "required_components": ["bam"], "components": []}
        with self.assertRaisesRegex(ValueError, "required components"):
            CONTEXT.validate(inventory, [])

    def test_idr_not_implemented_is_not_zero(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.write(root, "idr.json", {"schema_version": "1.0", "type": "idr", "id": "idr1", "strategy": "idr", "status": "not_implemented"})
            inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project": self.project, "required_components": [], "components": [{"component": "consensus_idr", "manifest": "ignored", "artifacts": []}]}
            result = CONTEXT.validate(inventory, [manifest])
            self.assertEqual(result["components"]["consensus_idr"]["status"], "not_implemented")

    def test_association_is_independent_of_manifest_order(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bam = self.write(root, "same.json", {"schema_version": "1.0", "type": "bam_final", "id": "r1", "record_id": "r1", "sample_id": "s1", "dataset": "d", "status": "complete"})
            peak = self.write(root, "other.json", {"schema_version": "1.0", "type": "peak_calling", "id": "p1", "record_id": "r1", "sample_id": "s1", "dataset": "d", "status": "complete"})
            inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project": self.project, "required_components": [], "components": [{"component": "peak", "manifest": "x"}, {"component": "bam", "manifest": "y"}]}
            result = CONTEXT.validate(inventory, [bam, peak])
            self.assertEqual(result["records"], [{"record_id": "r1", "sample_id": "s1"}])

    def test_build_conflict_fails(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = self.write(root, "ref.json", {"schema_version": "1.0", "type": "reference_bundle", "id": "ref", "build": "other", "status": "complete"})
            inventory = {"schema_version": "1.0", "type": "chipseq_report_input", "project": self.project, "required_components": [], "components": [{"component": "reference", "manifest": "x"}]}
            with self.assertRaisesRegex(ValueError, "build conflict"):
                CONTEXT.validate(inventory, [manifest])


class ReportPresentationTest(unittest.TestCase):
    def test_missing_and_idr_status_are_explicit_and_html_is_self_contained(self):
        data = {"project": {"project_id": "p", "dataset": "d", "genome_id": "g", "build": "b"}, "sections": {key: {"status": "not_requested", "data": None} for key, _label in GENERATOR.SECTION_ORDER}}
        data["sections"]["consensus_idr"] = {"status": "not_implemented", "data": {"idr_status": "not_implemented", "regions": None}}
        page = GENERATOR.generate_html(data, {"provider": "html_v1", "title": "A < B", "language": "en"})
        self.assertIn("Not executed", page)
        self.assertIn("not_implemented", page)
        self.assertIn("Not available", page)
        self.assertIn("A &lt; B", page)
        self.assertNotIn("src=\"http", page)

    def test_semantic_aggregate_uses_declared_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            subprocess.run([sys.executable, str(ROOT / "tests/native_chipseq_report/generate_fixture.py"), "--outdir", str(root)], check=True)
            inventory = json.loads((root / "report_input.json").read_text(encoding="utf-8"))
            manifests = [root / entry["manifest"] for entry in inventory["components"]]
            artifacts = [root / value for entry in inventory["components"] for value in entry.get("artifacts", [])]
            context = CONTEXT.validate(inventory, manifests)
            documents = [AGGREGATE.load_json(path) for path in manifests]
            loaded = AGGREGATE.load_semantic_artifacts(artifacts, AGGREGATE.declared_checksums(documents))
            data = AGGREGATE.aggregate(context, documents, loaded)
            self.assertEqual(data["sections"]["consensus_idr"]["data"]["idr_status"], "not_implemented")
            self.assertEqual(data["sections"]["tracks"]["data"]["records"][0]["normalization"], "CPM")
            self.assertEqual(data["sections"]["differential_binding"]["data"]["summaries"][0]["significant"], "12")


class SchemaTest(unittest.TestCase):
    def test_schema_and_example_roles_agree(self):
        schema = json.loads((ROOT / "schemas/chipseq-report-input-v1.schema.json").read_text(encoding="utf-8"))
        example = json.loads((ROOT / "assets/chipseq_report_input.example.json").read_text(encoding="utf-8"))
        roles = schema["$defs"]["component"]["enum"]
        self.assertEqual(example["type"], "chipseq_report_input")
        self.assertTrue(set(example["required_components"]).issubset(roles))
        self.assertTrue(all(entry["component"] in roles for entry in example["components"]))


if __name__ == "__main__":
    unittest.main()
