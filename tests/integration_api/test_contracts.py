from __future__ import annotations

import copy
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "bin"))

from integration_contract import (  # noqa: E402
    build_run_manifest,
    compatibility_errors,
    filesystem_errors,
    schema_contract_errors,
    semantic_errors,
)


def load_example(assay: str) -> dict:
    return json.loads((ROOT / "assets" / "examples" / f"{assay}_run_manifest.example.json").read_text(encoding="utf-8"))


class SchemaExamplesTest(unittest.TestCase):
    def test_examples_pass_structural_and_semantic_validation(self):
        for assay in ("rnaseq", "chipseq"):
            document = load_example(assay)
            self.assertEqual([], schema_contract_errors(document))
            self.assertEqual([], semantic_errors(document))

    def test_examples_pass_json_schema(self):
        try:
            from validate_integration_manifest import jsonschema_errors
            import jsonschema  # noqa: F401
        except ImportError:
            self.skipTest("jsonschema is installed by CI and the module environment")
        schema_root = ROOT / "schemas" / "integration"
        for assay in ("rnaseq", "chipseq"):
            self.assertEqual([], jsonschema_errors(load_example(assay), schema_root))

    def test_all_schema_documents_are_json_objects_with_identifiers(self):
        paths = sorted((ROOT / "schemas" / "integration").rglob("*.json"))
        self.assertEqual(7, len(paths))
        for path in paths:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertIsInstance(document, dict)
            self.assertTrue(document.get("$id"))


class RnaContractTest(unittest.TestCase):
    def test_multiple_contrasts_are_explicit(self):
        document = load_example("rnaseq")
        document["samples"].append({
            "sample_id": "egg_1", "dataset": "fixture", "condition": "egg", "stage": "egg",
            "batch": "B2", "biological_replicate": "1", "technical_runs": ["egg_run_1"],
        })
        document["conditions"].append("egg")
        document["stages"].append("egg")
        document["batches"].append("B2")
        document["contrasts"].append({
            "contrast_id": "adult_vs_egg", "factor": "condition", "numerator": "adult",
            "denominator": "egg", "label": None, "formula": "~ batch + condition",
            "covariates": ["batch"], "assay": ["rnaseq"], "metadata": {},
        })
        self.assertEqual([], semantic_errors(document))

    def test_invalid_reference_and_artifact_type_are_rejected(self):
        document = load_example("rnaseq")
        document["artifacts"][0]["reference_id"] = "other_reference"
        document["artifacts"][0]["artifact_type"] = "peak_set"
        errors = semantic_errors(document)
        self.assertTrue(any("unknown reference" in error for error in errors))
        self.assertTrue(any("assay/type mismatch" in error for error in errors))

    def test_malformed_contrast_is_rejected(self):
        document = load_example("rnaseq")
        document["contrasts"][0]["denominator"] = "adult"
        errors = semantic_errors(document)
        self.assertTrue(any("identical" in error for error in errors))


class ChipContractTest(unittest.TestCase):
    def test_mark_and_control_relationship_are_valid(self):
        self.assertEqual([], semantic_errors(load_example("chipseq")))

    def test_missing_mark_is_rejected(self):
        document = load_example("chipseq")
        document["samples"][1]["mark_or_factor"] = None
        document["artifacts"][0]["mark_or_factor"] = None
        errors = semantic_errors(document)
        self.assertTrue(any("requires mark_or_factor" in error for error in errors))

    def test_invalid_control_relationship_is_rejected(self):
        document = load_example("chipseq")
        document["samples"][1]["control_record_id"] = "missing_control"
        self.assertTrue(any("invalid control relationship" in error for error in semantic_errors(document)))

    def test_peak_types_and_multiple_db_contrasts_validate(self):
        document = load_example("chipseq")
        document["conditions"].append("cercaria")
        document["contrasts"] = [
            {"contrast_id": "adult_vs_cercaria", "factor": "condition", "numerator": "adult", "denominator": "cercaria", "label": None, "formula": "~ condition", "covariates": [], "assay": ["chipseq"], "metadata": {}},
            {"contrast_id": "cercaria_vs_adult", "factor": "condition", "numerator": "cercaria", "denominator": "adult", "label": None, "formula": "~ condition", "covariates": [], "assay": ["chipseq"], "metadata": {}},
        ]
        narrow_peak = copy.deepcopy(document["artifacts"][0])
        narrow_peak.update({"artifact_id": "fixture.h3k27ac.narrow", "artifact_type": "peak_set", "peak_type": "narrow"})
        broad_peak = copy.deepcopy(narrow_peak)
        broad_peak.update({"artifact_id": "fixture.h3k27ac.broad", "peak_type": "broad"})
        differential_binding = copy.deepcopy(document["artifacts"][0])
        differential_binding.update({
            "artifact_id": "fixture.h3k27ac.db", "artifact_type": "differential_binding",
            "contrast_id": "adult_vs_cercaria", "mark_or_factor": None,
            "marks_or_factors": ["H3K27ac"], "peak_type": None,
        })
        document["artifacts"].extend([narrow_peak, broad_peak, differential_binding])
        self.assertEqual([], semantic_errors(document))


class FilesystemAndCompatibilityTest(unittest.TestCase):
    def test_missing_artifact_and_checksum_are_separate_filesystem_errors(self):
        document = load_example("rnaseq")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manifest = root / "manifest.json"
            document["artifacts"][0]["location"] = {"kind": "manifest_relative", "path": "result.tsv", "base_path": None, "producer_manifest_id": None}
            document["artifacts"][0]["checksum"] = {"algorithm": "sha256", "value": "0" * 64}
            manifest.write_text(json.dumps(document), encoding="utf-8")
            self.assertTrue(any("missing" in error for error in filesystem_errors(document, manifest)))
            (root / "result.tsv").write_text("gene_id\tvalue\ng1\t1\n", encoding="utf-8")
            self.assertTrue(any("checksum mismatch" in error for error in filesystem_errors(document, manifest)))

    def test_duplicate_ids_and_missing_path_are_rejected(self):
        document = load_example("rnaseq")
        document["artifacts"].append(copy.deepcopy(document["artifacts"][0]))
        document["artifacts"][0]["location"].pop("path")
        errors = semantic_errors(document)
        self.assertIn("duplicate artifact_id", errors)
        self.assertTrue(any("has no path" in error for error in errors))

    def test_reference_and_organism_compatibility(self):
        rna, chip = load_example("rnaseq"), load_example("chipseq")
        self.assertEqual([], compatibility_errors(rna, chip))
        chip["reference"]["reference_id"] = "other"
        chip["reference"]["genome_id"] = "other"
        chip["reference"]["organism"] = "Mus musculus"
        errors = compatibility_errors(rna, chip)
        self.assertTrue(any("reference_id incompatible" in error for error in errors))
        self.assertTrue(any("organism incompatible" in error for error in errors))


class StageOneFixtureProjectionTest(unittest.TestCase):
    def test_stage_one_rna_context_builds_without_filename_inference(self):
        legacy_metadata = ROOT / "tests" / "integrative_legacy_characterization" / "fixture" / "inputs" / "rna_metadata.tsv"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            rows = legacy_metadata.read_text(encoding="utf-8").splitlines()
            metadata = root / "metadata.tsv"
            metadata.write_text(
                "dataset\tsample_id\trun_accession\tstage\tcondition\tbatch\n" +
                "\n".join("fixture\t" + row.split("\t")[0] + "\t" + row.split("\t")[0] + "_run\t" + "\t".join(row.split("\t")[1:]) for row in rows[1:]) + "\n",
                encoding="utf-8",
            )
            reference = root / "reference.json"
            reference.write_text(json.dumps({
                "schema_version": "1.0", "type": "reference_bundle", "id": "sm_fixture_v1",
                "organism": "Schistosoma mansoni", "status": "complete", "artifacts": [],
            }), encoding="utf-8")
            source = root / "source.json"
            source.write_text('{"schema_version":"1.0","type":"differential_expression","id":"fixture.de","status":"complete"}', encoding="utf-8")
            artifact = root / "de.tsv"
            artifact.write_text("gene_id\tcontrast\ngeneA\tadult_vs_cercariae\n", encoding="utf-8")
            contrast = root / "contrast.json"
            contrast.write_text(json.dumps({
                "design": {"variable": "condition", "formula": "~ batch + condition", "covariates": ["batch"]},
                "contrasts": [{"id": "adult_vs_cercariae", "factor": "condition", "numerator": "adult", "denominator": "cercariae"}],
            }), encoding="utf-8")
            spec = [{
                "artifact_id": "fixture.de.results", "artifact_type": "differential_expression", "assay": "rnaseq",
                "format": "tsv", "entity_level": "gene", "contrast_id": "adult_vs_cercariae", "sample_ids": [],
                "condition": None, "stage": None, "mark_or_factor": None, "peak_type": None, "role": "results",
                "producer_manifest_id": "fixture.de", "producer_process": "DE_AGGREGATE",
                "location": {"kind": "producer_relative", "path": "de.tsv", "base_path": None, "producer_manifest_id": "fixture.de"},
            }]
            document = build_run_manifest(
                assay="rnaseq", run={"id": "fixture.rna", "run_id": "r1", "run_name": "fixture", "helixforge_version": "test", "quantification_method": "salmon"},
                metadata=metadata, reference_manifest=reference, source_manifests=[source], artifacts=[artifact],
                artifact_specs=spec, contrast_spec=contrast,
            )
            self.assertEqual(["adult", "cercariae"], document["conditions"])
            self.assertEqual(4, len(document["samples"]))
            self.assertEqual("adult_vs_cercariae", document["contrasts"][0]["contrast_id"])


if __name__ == "__main__":
    unittest.main()
