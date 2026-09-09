from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "benchmark/integrative/scripts/real/prepare_gse133183_multimark_manifest.py"


def load_adapter():
    spec = importlib.util.spec_from_file_location("real_multimark", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_document(mark: str) -> dict:
    dataset = f"gse133183_{mark.lower()}"
    reference = {
        "reference_id": "GRCh38.p14_GENCODE_50", "display_name": "GRCh38 reference",
        "organism": "Homo_sapiens", "species": "Homo_sapiens",
        "assembly": "GRCh38.p14_GENCODE_50", "genome_id": "GRCh38.p14_GENCODE_50",
        "annotation_id": "annotation.test", "resources": {},
        "source": {"type": "external", "name": "test", "version": "1"}, "metadata": {},
    }
    provenance = {
        "producer_workflow": "chipseq", "producer_process": "TEST", "software": [],
        "parameters": {}, "source_manifest_ids": [f"{mark}.source"], "source_artifact_ids": [],
        "execution_metadata": None,
    }
    artifacts = []
    for kind, filename in (
        ("consensus_peaks", "peaks.bed"),
        ("differential_binding", "db.tsv"),
        ("peak_gene_annotation", "annotation.tsv"),
    ):
        artifacts.append({
            "artifact_id": f"{mark}.{kind}", "artifact_type": kind, "assay": "chipseq",
            "format": "tsv", "entity_level": "peak", "reference_id": reference["reference_id"],
            "contrast_id": "GSK343_vs_DMSO" if kind == "differential_binding" else None,
            "sample_ids": [], "condition": None, "stage": None, "mark_or_factor": mark,
            "marks_or_factors": [], "peak_type": "narrow" if mark == "H3K27ac" else "broad",
            "role": kind,
            "location": {"kind": "manifest_relative", "path": f"integration_artifacts/{mark}/{filename}", "base_path": None, "producer_manifest_id": None},
            "checksum": {"algorithm": "sha256", "value": "a" * 64},
            "source": {"type": "helixforge", "name": "test", "version": "1"},
            "provenance": copy.deepcopy(provenance), "metadata": {},
        })
    samples = [
        {"record_id": f"{mark}.IP", "sample_id": f"{mark}.IP", "dataset": dataset,
         "condition": "GSK343", "stage": None, "biological_replicate": "1", "technical_replicate": "1",
         "is_control": False, "control_record_id": "SHARED.IGG", "mark_or_factor": mark, "antibody": mark},
        {"record_id": "SHARED.IGG", "sample_id": "SHARED.IGG", "dataset": dataset,
         "condition": "GSK343", "stage": None, "biological_replicate": "1", "technical_replicate": "1",
         "is_control": True, "control_record_id": None, "mark_or_factor": "IgG", "antibody": None},
    ]
    contrast = {
        "contrast_id": "GSK343_vs_DMSO", "factor": "condition", "numerator": "GSK343",
        "denominator": "DMSO", "label": f"{mark}: GSK343 versus DMSO", "formula": "~ condition",
        "covariates": [], "assay": ["chipseq"], "metadata": {},
    }
    return {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": "chipseq_run_manifest",
        "id": f"{mark}.run", "status": "complete",
        "run": {"workflow": "chipseq", "run_id": f"{mark}.run", "run_name": mark, "created_at": None,
                "helixforge_version": "1.0.0-rc.1", "git_commit": "test", "nextflow_version": "25.10.7",
                "profile": "test", "source": {"type": "helixforge", "name": "test", "version": "1"}},
        "reference": reference, "samples": samples, "conditions": ["DMSO", "GSK343"],
        "marks_or_factors": [mark], "contrasts": [contrast], "artifacts": artifacts,
        "provenance": provenance,
    }


class RealMultimarkManifestTests(unittest.TestCase):
    def test_composition_deduplicates_shared_control_and_preserves_artifacts(self):
        adapter = load_adapter()
        document, duplicates = adapter.compose_document(
            source_document("H3K27ac"), source_document("H3K27me3"),
            git_commit="abc123", job_id="42",
            source_checksums={"H3K27ac": "1" * 64, "H3K27me3": "2" * 64},
        )
        self.assertEqual(document["marks_or_factors"], ["H3K27ac", "H3K27me3"])
        self.assertEqual(len(document["samples"]), 3)
        self.assertEqual(duplicates, ["SHARED.IGG"])
        self.assertEqual(len(document["artifacts"]), 6)
        self.assertEqual({item["artifact_type"] for item in document["artifacts"]}, adapter.INTEGRATION_TYPES)
        self.assertIs(document["provenance"]["parameters"]["scientific_artifacts_changed"], False)
        self.assertEqual({item["dataset"] for item in document["samples"]}, {adapter.COMPOSITE_DATASET})

    def test_composition_rejects_conflicting_shared_control(self):
        adapter = load_adapter()
        ac = source_document("H3K27ac")
        me3 = source_document("H3K27me3")
        me3["samples"][1]["condition"] = "DMSO"
        with self.assertRaisesRegex(ValueError, "shared ChIP record differs"):
            adapter.compose_document(
                ac, me3, git_commit="abc123", job_id="42",
                source_checksums={"H3K27ac": "1" * 64, "H3K27me3": "2" * 64},
            )

    def test_script_requires_slurm_and_records_no_scientific_change(self):
        text = SCRIPT.read_text(encoding="utf-8")
        self.assertIn("must execute inside a Slurm job", text)
        self.assertIn("scientific_artifacts_changed", text)


if __name__ == "__main__":
    unittest.main()
