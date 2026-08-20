from __future__ import annotations

from pathlib import Path

from integration.evidence.io import read_tsv, sha256


def _dataset_errors(document: dict, root: Path) -> list[str]:
    errors = []
    for dataset in document.get("datasets", []):
        path = (root / dataset.get("path", "")).resolve()
        if not path.is_relative_to(root.resolve()) or not path.is_file():
            errors.append(f"missing or escaping dataset {dataset.get('path')}")
            continue
        rows = read_tsv(path)[1]
        if len(rows) != dataset.get("records"):
            errors.append(f"{path.name}: record count mismatch")
        if dataset.get("checksum", {}).get("value") != sha256(path):
            errors.append(f"{path.name}: checksum mismatch")
    return errors


def validate_harmonization(document: dict, root: Path) -> list[str]:
    errors = _dataset_errors(document, root)
    if document.get("type") != "cross_assay_harmonization":
        errors.append("invalid harmonization manifest type")
    entity_rows = read_tsv(root / "entity_map.tsv")[1] if (root / "entity_map.tsv").is_file() else []
    keys = [(row.get("source_assay"), row.get("source_entity_id")) for row in entity_rows]
    if len(keys) != len(set(keys)):
        errors.append("duplicate source assay/entity mapping")
    if any(not row.get("canonical_entity_id") for row in entity_rows):
        errors.append("canonical entity is missing")
    contrast_rows = read_tsv(root / "contrast_map.tsv")[1] if (root / "contrast_map.tsv").is_file() else []
    contrast_ids = [row.get("canonical_contrast_id") for row in contrast_rows]
    if len(contrast_ids) != len(set(contrast_ids)):
        errors.append("duplicate canonical contrast")
    if any(row.get("numerator") == row.get("denominator") for row in contrast_rows):
        errors.append("contrast numerator and denominator are identical")
    return errors


def validate_integration(document: dict, root: Path) -> list[str]:
    errors = _dataset_errors(document, root)
    if document.get("type") != "molecular_evidence_integration":
        errors.append("invalid integration manifest type")
    long_rows = read_tsv(root / "master_evidence_long.tsv")[1] if (root / "master_evidence_long.tsv").is_file() else []
    observation_ids = [row.get("observation_id") for row in long_rows]
    if len(observation_ids) != len(set(observation_ids)):
        errors.append("duplicate integrated observation")
    for index, row in enumerate(long_rows, 2):
        if not row.get("canonical_entity_id"):
            errors.append(f"master_evidence_long.tsv:{index}: canonical entity is missing")
        if row.get("source_contrast_id") and not row.get("canonical_contrast_id"):
            errors.append(f"master_evidence_long.tsv:{index}: contrast is not harmonized")
        if row.get("evidence_type") == "differential_binding" and not row.get("canonical_mark"):
            errors.append(f"master_evidence_long.tsv:{index}: differential binding mark is missing")
    return errors
