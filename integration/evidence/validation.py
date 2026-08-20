from __future__ import annotations

import json
from pathlib import Path

from .io import read_tsv, sha256


REQUIRED = {
    "expression": {"evidence_id", "source_entity_id", "sample_id", "measurement", "unit", "source_artifact_id"},
    "differential_expression": {"evidence_id", "source_entity_id", "contrast_id", "log2_fold_change", "source_artifact_id"},
    "peak": {"evidence_id", "peak_id", "mark_or_factor", "chromosome", "start", "end", "peak_type", "source_artifact_id"},
    "peak_gene": {"evidence_id", "peak_id", "source_entity_id", "relationship", "source_artifact_id"},
    "consensus": {"evidence_id", "peak_id", "mark_or_factor", "chromosome", "start", "end", "source_artifact_id"},
    "differential_binding": {"evidence_id", "peak_id", "contrast_id", "log2_fold_change", "source_artifact_id"},
}


def schema_errors(document: dict) -> list[str]:
    errors = []
    for field in ("schema_version", "evidence_model_version", "type", "id", "assay", "run_id", "reference_id", "datasets", "artifact_catalog"):
        if field not in document:
            errors.append(f"missing manifest field {field}")
    if document.get("type") != "evidence_manifest":
        errors.append("type must be evidence_manifest")
    if document.get("assay") not in {"rnaseq", "chipseq"}:
        errors.append("assay must be rnaseq or chipseq")
    return errors


def validate_evidence_manifest(document: dict, root: Path) -> list[str]:
    errors = schema_errors(document)
    catalog = {item.get("artifact_id") for item in document.get("artifact_catalog", [])}
    contrasts = {item.get("contrast_id") for item in document.get("contrasts", [])}
    seen_ids: set[str] = set()
    seen_observations: set[tuple[str, ...]] = set()
    known_peaks: set[str] = set()
    pending_links: list[tuple[str, str]] = []
    for dataset in document.get("datasets", []):
        kind = dataset.get("evidence_type")
        path = root / dataset.get("path", "")
        if kind not in REQUIRED:
            errors.append(f"unknown evidence_type {kind}")
            continue
        if not path.is_file():
            errors.append(f"missing dataset {path.name}")
            continue
        fields, rows = read_tsv(path)
        missing = REQUIRED[kind] - set(fields)
        if missing:
            errors.append(f"{path.name}: missing columns {sorted(missing)}")
        if len(rows) != dataset.get("records"):
            errors.append(f"{path.name}: record count mismatch")
        expected = dataset.get("checksum", {}).get("value")
        if expected and sha256(path) != expected:
            errors.append(f"{path.name}: checksum mismatch")
        for number, row in enumerate(rows, 2):
            evidence_id = row.get("evidence_id", "")
            if not evidence_id or evidence_id in seen_ids:
                errors.append(f"{path.name}:{number}: missing or duplicate evidence_id")
            seen_ids.add(evidence_id)
            if row.get("source_artifact_id") not in catalog:
                errors.append(f"{path.name}:{number}: unknown source_artifact_id")
            if kind in {"expression", "differential_expression", "peak_gene", "differential_binding"} and not row.get("source_entity_id"):
                if kind != "differential_binding" or not row.get("peak_id"):
                    errors.append(f"{path.name}:{number}: missing source entity")
            if kind in {"differential_expression", "differential_binding"} and row.get("contrast_id") not in contrasts:
                errors.append(f"{path.name}:{number}: unknown contrast_id")
            key = ()
            if kind == "expression":
                key = (kind, row.get("source_entity_id", ""), row.get("sample_id", ""), row.get("unit", ""), row.get("source_artifact_id", ""))
            elif kind == "differential_expression":
                key = (kind, row.get("source_entity_id", ""), row.get("contrast_id", ""), row.get("source_artifact_id", ""))
            elif kind == "differential_binding":
                key = (kind, row.get("peak_id", ""), row.get("contrast_id", ""), row.get("source_artifact_id", ""))
            if key:
                if key in seen_observations:
                    errors.append(f"{path.name}:{number}: duplicate scientific observation")
                seen_observations.add(key)
            for key in ("pvalue", "padj"):
                if row.get(key):
                    value = float(row[key])
                    if value < 0 or value > 1:
                        errors.append(f"{path.name}:{number}: {key} outside [0,1]")
            if kind in {"peak", "consensus"}:
                try:
                    if int(row.get("start", "")) < 0 or int(row.get("start", "")) >= int(row.get("end", "")):
                        errors.append(f"{path.name}:{number}: invalid coordinates")
                except ValueError:
                    errors.append(f"{path.name}:{number}: non-integer coordinates")
                if not row.get("mark_or_factor"):
                    errors.append(f"{path.name}:{number}: missing mark_or_factor")
                known_peaks.add(row.get("peak_id", ""))
            if kind == "peak_gene":
                pending_links.append((path.name, row.get("peak_id", "")))
            if kind == "differential_binding" and not row.get("mark_or_factor"):
                errors.append(f"{path.name}:{number}: missing mark_or_factor")
    for filename, peak_id in pending_links:
        if known_peaks and peak_id not in known_peaks:
            errors.append(f"{filename}: peak-gene references unknown peak {peak_id}")
    return errors


def validate_file(path: Path) -> list[str]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return validate_evidence_manifest(document, path.parent)
