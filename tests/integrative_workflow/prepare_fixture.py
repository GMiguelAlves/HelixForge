#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from integration.evidence.io import sha256  # noqa: E402

SOURCE = ROOT / "tests" / "integrative_legacy_characterization" / "fixture" / "inputs"


def provenance(assay: str, artifact_id: str) -> dict:
    return {"producer_workflow": assay, "producer_process": "FIXTURE", "software": [{"name": "fixture", "version": "1", "container": None}], "parameters": {}, "source_manifest_ids": [], "source_artifact_ids": [artifact_id], "execution_metadata": None}


def source() -> dict:
    return {"type": "helixforge", "name": "HelixForge fixture", "version": "1"}


def reference() -> dict:
    return {"reference_id": "fixture_ref", "display_name": "Stage 1 fixture", "organism": "Schistosoma mansoni", "species": "Schistosoma mansoni", "assembly": "fixture_v1", "genome_id": "fixture_genome", "annotation_id": "fixture_annotation", "resources": {}, "source": source(), "metadata": {}}


def location(assay_root: Path, artifact_id: str, input_name: str) -> tuple[Path, dict]:
    target = assay_root / "integration_artifacts" / artifact_id / input_name
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(SOURCE / input_name, target)
    return target, {"kind": "manifest_relative", "path": f"integration_artifacts/{artifact_id}/{input_name}", "base_path": None, "producer_manifest_id": None}


def artifact(assay: str, assay_root: Path, artifact_id: str, artifact_type: str, input_name: str, **values) -> dict:
    target, artifact_location = location(assay_root, artifact_id, input_name)
    return {"artifact_id": artifact_id, "artifact_type": artifact_type, "assay": assay, "format": "tsv", "entity_level": values.pop("entity_level", "gene"), "reference_id": "fixture_ref", "contrast_id": values.pop("contrast_id", None), "sample_ids": [], "condition": None, "stage": None, "mark_or_factor": values.pop("mark_or_factor", None), "marks_or_factors": values.pop("marks_or_factors", []), "peak_type": None, "role": values.pop("role", "integration_evidence"), "location": artifact_location, "checksum": {"algorithm": "sha256", "value": sha256(target)}, "source": source(), "provenance": provenance(assay, artifact_id), "metadata": values}


def run_document(assay: str) -> dict:
    return {"workflow": assay, "run_id": f"fixture-{assay}", "run_name": f"fixture-{assay}", "created_at": None, "helixforge_version": "0.1.0-test", "git_commit": "fixture", "nextflow_version": "25.10.7", "profile": "test", "source": source()}


def build_fixture(output: Path) -> tuple[Path, Path]:
    rna_root, chip_root = output / "rna", output / "chip"
    rna_root.mkdir(parents=True, exist_ok=True)
    chip_root.mkdir(parents=True, exist_ok=True)
    contrasts = [
        {"contrast_id": "cercariae_vs_adult", "factor": "condition", "numerator": "cercariae", "denominator": "adult", "label": None, "formula": "~ condition", "covariates": [], "assay": ["rnaseq", "chipseq"], "metadata": {}},
        {"contrast_id": "adult_vs_cercariae", "factor": "condition", "numerator": "adult", "denominator": "cercariae", "label": None, "formula": "~ condition", "covariates": [], "assay": ["rnaseq"], "metadata": {}},
    ]
    rna_samples = [
        {"sample_id": sample, "dataset": "fixture", "condition": condition, "stage": condition, "batch": None, "biological_replicate": index, "technical_runs": [sample]}
        for condition, samples in (("cercariae", ("C1", "C2")), ("adult", ("A1", "A2"))) for index, sample in enumerate(samples, 1)
    ]
    rna_artifacts = [
        artifact("rnaseq", rna_root, "rna.tpm", "gene_abundance", "tpm_matrix.tsv", role="abundance"),
        artifact("rnaseq", rna_root, "rna.de", "differential_expression_summary", "deg_results.tsv", role="combined_results"),
    ]
    rna = {"schema_version": "1.0", "integration_api_version": "1.0", "type": "rnaseq_run_manifest", "id": "fixture.rnaseq", "status": "complete", "run": run_document("rnaseq"), "reference": reference(), "samples": rna_samples, "conditions": ["adult", "cercariae"], "stages": ["adult", "cercariae"], "batches": [], "quantification_method": "salmon", "contrasts": contrasts, "artifacts": rna_artifacts, "provenance": provenance("rnaseq", "fixture.rnaseq")}

    chip_samples = [
        {"record_id": "chip1", "sample_id": "chip1", "dataset": "fixture", "condition": "cercariae", "stage": "cercariae", "biological_replicate": 1, "technical_replicate": 1, "is_control": False, "control_record_id": None, "mark_or_factor": "H3K27ac", "antibody": None}
    ]
    chip_artifacts = [
        artifact("chipseq", chip_root, "chip.annotation", "peak_gene_annotation", "annotated_peaks_fixture.tsv", entity_level="peak", marks_or_factors=["H3K27ac", "H3K27me3", "SmHP1"], role="peak_gene_associations"),
        artifact("chipseq", chip_root, "chip.db", "differential_binding", "differential_binding.tsv", entity_level="peak", contrast_id="cercariae_vs_adult", marks_or_factors=["H3K27ac", "H3K27me3"], role="results"),
    ]
    chip = {"schema_version": "1.0", "integration_api_version": "1.0", "type": "chipseq_run_manifest", "id": "fixture.chipseq", "status": "complete", "run": run_document("chipseq"), "reference": reference(), "samples": chip_samples, "conditions": ["adult", "cercariae"], "marks_or_factors": ["H3K27ac"], "contrasts": [contrasts[0]], "artifacts": chip_artifacts, "provenance": provenance("chipseq", "fixture.chipseq")}
    rna_path, chip_path = rna_root / "rnaseq_run_manifest.json", chip_root / "chipseq_run_manifest.json"
    rna_path.write_text(json.dumps(rna, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    chip_path.write_text(json.dumps(chip, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(SOURCE / "functional_annotation.tsv", output / "functional_annotation.tsv")
    return rna_path, chip_path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rna, chip = build_fixture(args.output)
    print(rna)
    print(chip)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
