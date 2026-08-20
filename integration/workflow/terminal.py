from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from integration.evidence.io import read_tsv, sha256


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _checksum_ref(path: Path, document: dict[str, Any]) -> dict[str, Any]:
    return {"id": document.get("id"), "type": document.get("type"), "checksum": {"algorithm": "sha256", "value": sha256(path)}}


def _component_artifacts(component: dict[str, Any], root: Path, prefix: str) -> list[dict[str, Any]]:
    artifacts = []
    for dataset in component.get("datasets", []):
        relative = dataset.get("path")
        if not relative:
            continue
        path = root / relative
        if not path.is_file():
            raise ValueError(f"terminal dataset is missing: {path}")
        checksum = sha256(path)
        expected = (dataset.get("checksum") or {}).get("value")
        if expected and checksum != expected:
            raise ValueError(f"terminal dataset checksum mismatch: {path}")
        identifier = dataset.get("dataset_id") or dataset.get("dataset_type") or dataset.get("evidence_type")
        artifacts.append({
            "artifact_id": identifier, "artifact_type": dataset.get("evidence_type") or dataset.get("dataset_type") or identifier,
            "format": dataset.get("format") or path.suffix.lstrip("."), "records": dataset.get("records"),
            "location": {"kind": "run_relative", "path": f"{prefix}/{relative}"},
            "checksum": {"algorithm": "sha256", "value": checksum}, "source_manifest_id": component.get("id"),
        })
    return artifacts


def _visualization_artifacts(component: dict[str, Any], root: Path, prefix: str) -> list[dict[str, Any]]:
    manifest = root / "visualization_manifest.tsv"
    if not manifest.is_file():
        return []
    _fields, rows = read_tsv(manifest)
    artifacts = []
    for row in rows:
        relative = row.get("path", "")
        path = root / relative
        if not relative or not path.is_file():
            raise ValueError(f"visualization artifact is missing: {path}")
        checksum = sha256(path)
        expected = row.get("checksum", "")
        if expected and checksum != expected:
            raise ValueError(f"visualization checksum mismatch: {path}")
        artifacts.append({
            "artifact_id": row.get("figure_id"), "artifact_type": "integrative_visualization",
            "format": row.get("format") or path.suffix.lstrip("."), "records": 1,
            "location": {"kind": "run_relative", "path": f"{prefix}/{relative}"},
            "checksum": {"algorithm": "sha256", "value": checksum},
            "source_manifest_id": component.get("id"),
        })
    return artifacts


def build_integrative_run_manifest(rna_manifest_path: Path, chip_manifest_path: Path, validation_dir: Path, rna_evidence_dir: Path, chip_evidence_dir: Path, harmonization_dir: Path, integration_dir: Path, interpretation_dir: Path, functional_dir: Path, visualization_dir: Path, report_dir: Path, run: dict[str, Any], output: Path) -> dict[str, Any]:
    rna, chip = _load(rna_manifest_path), _load(chip_manifest_path)
    components = [
        (rna_evidence_dir / "evidence_manifest.json", rna_evidence_dir, "evidence/rnaseq/rnaseq_evidence"),
        (chip_evidence_dir / "evidence_manifest.json", chip_evidence_dir, "evidence/chipseq/chipseq_evidence"),
        (harmonization_dir / "harmonization_manifest.json", harmonization_dir, "harmonization/harmonized_evidence"),
        (integration_dir / "integration_manifest.json", integration_dir, "master/integrated_evidence"),
        (interpretation_dir / "interpretation_manifest.json", interpretation_dir, "interpretation/final/interpretation"),
        (functional_dir / "functional_manifest.json", functional_dir, "functional/functional_analysis"),
        (visualization_dir / "visualization_manifest.json", visualization_dir, "visualization/integrative_visualization"),
        (report_dir / "report_manifest.json", report_dir, "report/integrative_report"),
    ]
    documents = [(path, root, prefix, _load(path)) for path, root, prefix in components]
    interpretation = next(document for _path, _root, _prefix, document in documents if document.get("type") == "molecular_interpretation")
    functional = next(document for _path, _root, _prefix, document in documents if document.get("type") == "functional_analysis")
    report = next(document for _path, _root, _prefix, document in documents if document.get("type") == "integrative_report")
    artifacts = []
    for _path, root, prefix, document in documents:
        artifacts.extend(_component_artifacts(document, root, prefix))
        if document.get("type") == "integrative_visualization":
            artifacts.extend(_visualization_artifacts(document, root, prefix))
    report_html = report_dir / "integrative_report.html"
    if not any(item["artifact_id"] == "report.html" for item in artifacts):
        artifacts.append({"artifact_id": "integrative.report.html", "artifact_type": "integrative_report", "format": "html", "records": 1, "location": {"kind": "run_relative", "path": "report/integrative_report/integrative_report.html"}, "checksum": {"algorithm": "sha256", "value": sha256(report_html)}, "source_manifest_id": report["id"]})
    source_manifests = [
        _checksum_ref(rna_manifest_path, rna), _checksum_ref(chip_manifest_path, chip),
        *[_checksum_ref(path, document) for path, _root, _prefix, document in documents],
    ]
    validation = _load(validation_dir / "input_validation.json")
    document = {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": "integrative_run_manifest",
        "id": str(run["id"]), "status": "complete", "run": run,
        "reference": interpretation.get("reference", {}),
        "input_manifests": [_checksum_ref(rna_manifest_path, rna), _checksum_ref(chip_manifest_path, chip)],
        "compatibility": {"status": validation["reference_compatibility"], "validation_checksum": {"algorithm": "sha256", "value": sha256(validation_dir / "input_validation.json")}},
        "models": {
            "evidence_model_version": documents[0][3].get("evidence_model_version"),
            "harmonization_model_version": documents[2][3].get("harmonization_model_version"),
            "integration_model_version": documents[3][3].get("integration_model_version"),
            "interpretation_model_version": interpretation.get("interpretation_model_version"),
            "classification_version": interpretation.get("classification_version"),
            "candidate_score_version": interpretation.get("candidate_score_version"),
            "functional_model_version": functional.get("functional_model_version"),
            "report_model_version": report.get("report_model_version"),
        },
        "policies": {"thresholds": interpretation.get("thresholds", {}), "candidate_score": interpretation.get("candidate_score", {}), "statistics_methods": interpretation.get("statistics_methods", {})},
        "artifacts": sorted(artifacts, key=lambda item: str(item.get("artifact_id"))),
        "component_manifests": source_manifests,
        "record_counts": {"terminal_artifacts": len(artifacts), "candidates": interpretation.get("record_counts", {}).get("scores", 0), "functional_terms": functional.get("record_counts", {}).get("terms", 0)},
        "provenance": {"producer_workflow": "integrative", "producer_process": "INTEGRATIVE_RUN_MANIFEST", "source_manifest_ids": [item.get("id") for item in source_manifests], "software": [{"name": "HelixForge", "version": run.get("helixforge_version")}], "parameters": run.get("parameters", {})},
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return document
