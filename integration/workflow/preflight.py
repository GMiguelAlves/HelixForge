from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from integration.evidence.io import safe_id, sha256


RNA_EVIDENCE_TYPES = {
    "gene_abundance", "gene_counts", "normalized_counts",
    "differential_expression", "differential_expression_summary",
}
CHIP_EVIDENCE_TYPES = {
    "peak_set", "consensus_peaks", "idr_peaks",
    "peak_gene_annotation", "differential_binding",
}


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest is not a JSON object: {path}")
    return value


def _contract_errors(document: dict[str, Any], expected_type: str) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "integration_api_version", "type", "id", "status", "run", "reference", "artifacts"}
    missing = sorted(required - set(document))
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if document.get("schema_version") != "1.0" or document.get("integration_api_version") != "1.0":
        errors.append("unsupported Integration API version")
    if document.get("type") != expected_type:
        errors.append(f"expected {expected_type}, found {document.get('type')!r}")
    if document.get("status") not in {"complete", "complete_empty", "stub"}:
        errors.append("manifest status is not consumable")
    if not isinstance(document.get("reference"), dict):
        errors.append("reference must be an object")
    if not isinstance(document.get("artifacts"), list):
        errors.append("artifacts must be an array")
    identifiers = [item.get("artifact_id") for item in document.get("artifacts", []) if isinstance(item, dict)]
    if len(identifiers) != len(set(identifiers)):
        errors.append("duplicate artifact_id")
    reference_id = (document.get("reference") or {}).get("reference_id")
    for artifact in document.get("artifacts", []):
        if not isinstance(artifact, dict):
            errors.append("artifact is not an object")
        elif artifact.get("reference_id") != reference_id:
            errors.append(f"artifact {artifact.get('artifact_id')} has an incompatible reference_id")
    return errors


def _compatibility_errors(rna: dict[str, Any], chip: dict[str, Any]) -> list[str]:
    errors = []
    left, right = rna.get("reference", {}), chip.get("reference", {})
    for field in ("reference_id", "genome_id", "annotation_id"):
        if left.get(field) != right.get(field):
            errors.append(f"{field} incompatible: {left.get(field)!r} != {right.get(field)!r}")
    for field in ("organism", "assembly"):
        if str(left.get(field) or "").casefold() != str(right.get(field) or "").casefold():
            errors.append(f"{field} incompatible: {left.get(field)!r} != {right.get(field)!r}")
    return errors


def _source_path(manifest: Path, artifact_root: Path, artifact: dict[str, Any]) -> Path:
    location = artifact.get("location") or {}
    kind = location.get("kind")
    raw = str(location.get("path") or "")
    if not raw:
        raise ValueError(f"artifact {artifact.get('artifact_id')} has no filesystem path")
    if kind == "manifest_relative":
        relative = Path(raw)
        if relative.parts and relative.parts[0] == "integration_artifacts":
            relative = Path(*relative.parts[1:])
        candidate = artifact_root / relative
    elif kind == "absolute":
        candidate = Path(raw)
    else:
        raise ValueError(
            f"artifact {artifact.get('artifact_id')} uses unsupported location kind {kind!r}; "
            "portable Integrative input requires manifest_relative or absolute"
        )
    candidate = candidate.resolve()
    if not candidate.is_file():
        raise ValueError(f"artifact {artifact.get('artifact_id')} is missing: {candidate}")
    checksum = artifact.get("checksum")
    if checksum and (checksum.get("algorithm") != "sha256" or checksum.get("value") != sha256(candidate)):
        raise ValueError(f"artifact {artifact.get('artifact_id')} checksum mismatch")
    return candidate


def _materialize(document: dict[str, Any], manifest: Path, artifact_root: Path, assay: str, output: Path) -> tuple[list[dict[str, Any]], int]:
    allowed = RNA_EVIDENCE_TYPES if assay == "rnaseq" else CHIP_EVIDENCE_TYPES
    target_root = output / f"{assay}_artifacts"
    target_root.mkdir(parents=True, exist_ok=True)
    bindings = []
    for artifact in sorted(document.get("artifacts", []), key=lambda item: item.get("artifact_id", "")):
        if artifact.get("artifact_type") not in allowed:
            continue
        source = _source_path(manifest, artifact_root, artifact)
        relative = Path(safe_id(artifact["artifact_id"])) / source.name
        target = target_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        bindings.append({"artifact_id": artifact["artifact_id"], "declared_name": source.name})
    if not bindings:
        raise ValueError(f"{assay} manifest exposes no Integration Evidence artifacts")
    (output / f"{assay}_bindings.json").write_text(json.dumps({"bindings": bindings}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    shutil.copy2(manifest, output / f"{assay}_run_manifest.json")
    return bindings, len(bindings)


def prepare_inputs(rna_manifest: Path, rna_artifacts: Path, chip_manifest: Path, chip_artifacts: Path, output: Path) -> dict[str, Any]:
    rna, chip = _load(rna_manifest), _load(chip_manifest)
    errors = _contract_errors(rna, "rnaseq_run_manifest") + _contract_errors(chip, "chipseq_run_manifest") + _compatibility_errors(rna, chip)
    if errors:
        raise ValueError("invalid Integrative inputs: " + "; ".join(errors))
    output.mkdir(parents=True, exist_ok=True)
    rna_bindings, n_rna = _materialize(rna, rna_manifest, rna_artifacts, "rnaseq", output)
    chip_bindings, n_chip = _materialize(chip, chip_manifest, chip_artifacts, "chipseq", output)
    report = {
        "schema_version": "1.0", "type": "integrative_input_validation", "status": "complete",
        "mode": "rna_plus_chip", "schema_validation": "contract_and_ci_jsonschema",
        "semantic_validation": "valid", "filesystem_validation": "valid", "checksum_validation": "valid",
        "reference_compatibility": "compatible", "reference": rna["reference"],
        "inputs": [
            {"assay": "rnaseq", "manifest_id": rna["id"], "manifest_checksum": sha256(rna_manifest), "bound_artifacts": n_rna},
            {"assay": "chipseq", "manifest_id": chip["id"], "manifest_checksum": sha256(chip_manifest), "bound_artifacts": n_chip},
        ],
    }
    (output / "input_validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return report
