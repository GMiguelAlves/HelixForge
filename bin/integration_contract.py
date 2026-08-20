#!/usr/bin/env python3
"""Integration API v1 construction and validation helpers."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any


RNA_TYPES = {
    "gene_counts", "gene_abundance", "transcript_counts", "transcript_abundance", "normalized_counts",
    "differential_expression", "differential_expression_summary", "rnaseq_report",
}
CHIP_TYPES = {
    "aligned_bam", "peak_set", "peak_qc", "consensus_peaks", "idr_peaks",
    "differential_binding", "peak_gene_annotation", "signal_track", "chipseq_report",
}
MARK_REQUIRED_TYPES = {
    "peak_set", "peak_qc", "consensus_peaks", "idr_peaks",
    "differential_binding", "peak_gene_annotation",
}


def sha256_path(path: Path) -> str:
    digest = hashlib.sha256()
    if path.is_dir():
        for child in sorted(item for item in path.rglob("*") if item.is_file()):
            digest.update(child.relative_to(path).as_posix().encode("utf-8"))
            digest.update(b"\0")
            digest.update(bytes.fromhex(sha256_path(child)))
        return digest.hexdigest()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"JSON document must be an object: {path}")
    return value


def read_table(path: Path) -> list[dict[str, str]]:
    text = path.read_text(encoding="utf-8-sig")
    try:
        dialect = csv.Sniffer().sniff(text[:8192], delimiters=",\t")
    except csv.Error:
        dialect = csv.excel_tab if path.suffix.lower() == ".tsv" else csv.excel
    return [
        {str(key): str(value or "").strip() for key, value in row.items()}
        for row in csv.DictReader(text.splitlines(), dialect=dialect)
    ]


def _unique(values: list[str]) -> list[str]:
    return sorted({value for value in values if value})


def reference_from_bundle(document: dict[str, Any]) -> dict[str, Any]:
    reference_id = str(document.get("genome_id") or document.get("id") or "").strip()
    organism = str(document.get("organism") or "").strip()
    if not reference_id or not organism:
        raise ValueError("Reference Bundle must declare a non-empty id/genome_id and organism")
    resources: dict[str, Any] = {}
    aliases = {"reference": "fasta", "genome": "fasta", "annotation": "annotation", "transcriptome": "transcriptome", "blacklist": "blacklist", "chrom_sizes": "chrom_sizes"}
    raw = document.get("artifacts", {})
    if isinstance(raw, list):
        entries = [(str(item.get("role") or ""), item) for item in raw if isinstance(item, dict)]
    elif isinstance(raw, dict):
        entries = [(str(role), item) for role, item in raw.items() if isinstance(item, dict)]
    else:
        entries = []
    for role, item in entries:
        resource_role = aliases.get(role)
        if not resource_role or item.get("available") is False:
            continue
        relative = str(item.get("path") or item.get("name") or "").strip()
        if not relative:
            continue
        checksum = item.get("sha256")
        resources[resource_role] = {
            "location": {
                "kind": "producer_relative", "path": relative,
                "base_path": None, "producer_manifest_id": str(document.get("id")),
            },
            "checksum": {"algorithm": "sha256", "value": checksum} if checksum else None,
            "version": None,
        }
    annotation_checksum = None
    if "annotation" in resources and resources["annotation"].get("checksum"):
        annotation_checksum = resources["annotation"]["checksum"]["value"]
    return {
        "reference_id": reference_id,
        "display_name": str(document.get("id") or reference_id),
        "organism": organism,
        "species": organism,
        "assembly": document.get("build") or document.get("assembly") or document.get("genome_id"),
        "genome_id": str(document.get("genome_id") or reference_id),
        "annotation_id": f"annotation.{annotation_checksum[:12]}" if annotation_checksum else (f"{reference_id}.annotation" if "annotation" in resources else None),
        "resources": resources,
        "source": {"type": "external", "name": "Reference Bundle", "version": str(document.get("schema_version") or "1.0")},
        "metadata": {"source_manifest_id": str(document.get("id"))},
    }


def samples_from_metadata(assay: str, path: Path) -> list[dict[str, Any]]:
    rows = read_table(path)
    if not rows:
        raise ValueError("normalized metadata contains no records")
    if assay == "rnaseq":
        grouped: dict[tuple[str, str], list[dict[str, str]]] = {}
        for row in rows:
            key = (row.get("dataset", ""), row.get("sample_id", ""))
            if not all(key) or not row.get("condition"):
                raise ValueError("RNA metadata requires dataset, sample_id, and condition")
            grouped.setdefault(key, []).append(row)
        result = []
        for (dataset, sample_id), records in sorted(grouped.items()):
            def one(field: str) -> str | None:
                values = _unique([record.get(field, "") for record in records])
                if len(values) > 1:
                    raise ValueError(f"RNA sample {sample_id} has conflicting {field}: {values}")
                return values[0] if values else None
            result.append({
                "sample_id": sample_id, "dataset": dataset, "condition": one("condition"),
                "stage": one("stage") or one("life_stage"), "batch": one("batch"),
                "biological_replicate": one("biological_replicate") or one("replicate"),
                "technical_runs": _unique([record.get("run_accession", "") or record.get("record_id", "") for record in records]),
            })
        if any(not sample["technical_runs"] for sample in result):
            raise ValueError("RNA sample is missing run_accession/record_id")
        return result
    result = []
    for row in rows:
        required = ("record_id", "sample_id", "dataset", "condition", "biological_replicate", "technical_replicate")
        missing = [field for field in required if not row.get(field)]
        if missing:
            raise ValueError("ChIP metadata row is missing: " + ", ".join(missing))
        is_control = row.get("is_control", "").lower() in {"true", "1", "yes", "y"}
        result.append({
            "record_id": row["record_id"], "sample_id": row["sample_id"], "dataset": row["dataset"],
            "condition": row["condition"], "stage": row.get("stage") or row.get("life_stage") or None,
            "biological_replicate": row["biological_replicate"], "technical_replicate": row["technical_replicate"],
            "is_control": is_control, "control_record_id": row.get("control_record_id") or row.get("control_id") or None,
            "mark_or_factor": row.get("target") or row.get("mark_or_factor") or None,
            "antibody": row.get("antibody") or None,
        })
    return sorted(result, key=lambda item: item["record_id"])


def contrasts_from_spec(path: Path | None, assay: str) -> list[dict[str, Any]]:
    if path is None:
        return []
    document = load_json(path)
    design = document.get("design") or {}
    result = []
    for item in document.get("contrasts", []):
        result.append({
            "contrast_id": str(item.get("contrast_id") or item.get("id") or ""),
            "factor": str(item.get("factor") or design.get("variable") or ""),
            "numerator": str(item.get("numerator") or ""), "denominator": str(item.get("denominator") or ""),
            "label": item.get("label") or item.get("description"), "formula": design.get("formula"),
            "covariates": list(design.get("covariates") or []), "assay": [assay], "metadata": {},
        })
    return result


def artifact_from_spec(spec: dict[str, Any], actual: Path, reference_id: str) -> dict[str, Any]:
    producer_manifest_id = spec.get("producer_manifest_id")
    provenance = {
        "producer_workflow": spec.get("producer_workflow") or spec["assay"],
        "producer_process": spec.get("producer_process") or "unknown",
        "software": spec.get("software") or [], "parameters": spec.get("parameters") or {},
        "source_manifest_ids": [producer_manifest_id] if producer_manifest_id else [],
        "source_artifact_ids": list(spec.get("source_artifact_ids") or []), "execution_metadata": None,
    }
    return {
        "artifact_id": spec["artifact_id"], "artifact_type": spec["artifact_type"], "assay": spec["assay"],
        "format": spec["format"], "entity_level": spec["entity_level"], "reference_id": reference_id,
        "contrast_id": spec.get("contrast_id"), "sample_ids": list(spec.get("sample_ids") or []),
        "condition": spec.get("condition"), "stage": spec.get("stage"), "mark_or_factor": spec.get("mark_or_factor"),
        "marks_or_factors": list(spec.get("marks_or_factors") or []),
        "peak_type": spec.get("peak_type"), "role": spec.get("role"), "location": spec["location"],
        "checksum": {"algorithm": "sha256", "value": sha256_path(actual)},
        "source": spec.get("source") or {"type": "helixforge", "name": "HelixForge", "version": None},
        "provenance": provenance, "metadata": spec.get("metadata") or {},
    }


def build_run_manifest(*, assay: str, run: dict[str, Any], metadata: Path, reference_manifest: Path,
                       source_manifests: list[Path], artifacts: list[Path], artifact_specs: list[dict[str, Any]],
                       contrast_spec: Path | None, status: str = "complete") -> dict[str, Any]:
    if assay not in {"rnaseq", "chipseq"}:
        raise ValueError(f"unsupported assay: {assay}")
    if len(artifacts) != len(artifact_specs):
        raise ValueError("artifact paths and semantic descriptors have different lengths")
    reference = reference_from_bundle(load_json(reference_manifest))
    samples = samples_from_metadata(assay, metadata)
    contrasts = contrasts_from_spec(contrast_spec, assay)
    conditions = _unique([str(sample["condition"]) for sample in samples])
    if status == "stub":
        contrasts = [
            contrast for contrast in contrasts
            if contrast["numerator"] in conditions and contrast["denominator"] in conditions
        ]
    semantic_artifacts = [artifact_from_spec(spec, path, reference["reference_id"]) for spec, path in zip(artifact_specs, artifacts)]
    if status == "stub":
        valid_contrast_ids = {contrast["contrast_id"] for contrast in contrasts}
        semantic_artifacts = [
            artifact for artifact in semantic_artifacts
            if not artifact.get("contrast_id") or artifact["contrast_id"] in valid_contrast_ids
        ]
    source_documents = [load_json(path) for path in source_manifests]
    source_ids = _unique([str(document.get("id") or "") for document in source_documents] + [str(load_json(reference_manifest).get("id") or "")])
    run_source = run.get("source") or {"type": "helixforge", "name": "HelixForge", "version": run.get("helixforge_version")}
    run_doc = {
        "workflow": assay, "run_id": str(run["run_id"]), "run_name": str(run.get("run_name") or run["run_id"]),
        "created_at": run.get("created_at"), "helixforge_version": str(run["helixforge_version"]),
        "git_commit": str(run.get("git_commit") or "unknown"), "nextflow_version": str(run.get("nextflow_version") or "unknown"),
        "profile": str(run.get("profile") or ""), "source": run_source,
    }
    document: dict[str, Any] = {
        "schema_version": "1.0", "integration_api_version": "1.0", "type": f"{assay}_run_manifest",
        "id": str(run["id"]), "status": status, "run": run_doc, "reference": reference,
        "samples": samples, "conditions": conditions,
        "contrasts": contrasts, "artifacts": semantic_artifacts,
        "provenance": {
            "producer_workflow": assay, "producer_process": "RUN_MANIFEST",
            "software": [{"name": "HelixForge", "version": run_doc["helixforge_version"], "container": None}],
            "parameters": run.get("parameters") or {}, "source_manifest_ids": source_ids,
            "source_artifact_ids": [artifact["artifact_id"] for artifact in semantic_artifacts], "execution_metadata": None,
        },
    }
    if assay == "rnaseq":
        document["stages"] = _unique([str(sample.get("stage") or "") for sample in samples])
        document["batches"] = _unique([str(sample.get("batch") or "") for sample in samples])
        document["quantification_method"] = run.get("quantification_method")
    else:
        document["marks_or_factors"] = _unique([str(sample.get("mark_or_factor") or "") for sample in samples if not sample["is_control"]])
    errors = schema_contract_errors(document) + semantic_errors(document)
    if errors:
        raise ValueError("invalid terminal manifest: " + "; ".join(errors))
    return document


def schema_contract_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    required = {"schema_version", "integration_api_version", "type", "id", "status", "run", "reference", "samples", "conditions", "contrasts", "artifacts", "provenance"}
    missing = sorted(required - set(document))
    if missing:
        errors.append("missing required fields: " + ", ".join(missing))
    if document.get("schema_version") != "1.0" or document.get("integration_api_version") != "1.0":
        errors.append("unsupported schema/API version")
    if document.get("type") not in {"rnaseq_run_manifest", "chipseq_run_manifest"}:
        errors.append("unsupported manifest type")
    for field in ("samples", "conditions", "contrasts", "artifacts"):
        if field in document and not isinstance(document[field], list):
            errors.append(f"{field} must be an array")
    if not isinstance(document.get("reference"), dict):
        errors.append("reference must be an object")
    return errors


def semantic_errors(document: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    assay = "rnaseq" if document.get("type") == "rnaseq_run_manifest" else "chipseq"
    reference_id = str((document.get("reference") or {}).get("reference_id") or "")
    conditions = set(document.get("conditions") or [])
    artifacts = document.get("artifacts") or []
    artifact_ids = [item.get("artifact_id") for item in artifacts if isinstance(item, dict)]
    if len(artifact_ids) != len(set(artifact_ids)):
        errors.append("duplicate artifact_id")
    contrasts = document.get("contrasts") or []
    contrast_ids = [item.get("contrast_id") for item in contrasts if isinstance(item, dict)]
    if len(contrast_ids) != len(set(contrast_ids)):
        errors.append("duplicate contrast_id")
    for contrast in contrasts:
        if not all(str(contrast.get(field) or "").strip() for field in ("contrast_id", "factor", "numerator", "denominator")):
            errors.append("malformed contrast")
            continue
        if contrast["numerator"] == contrast["denominator"]:
            errors.append(f"contrast {contrast['contrast_id']} has identical numerator and denominator")
        if contrast["numerator"] not in conditions or contrast["denominator"] not in conditions:
            errors.append(f"contrast {contrast['contrast_id']} references an unknown condition")
    allowed = RNA_TYPES if assay == "rnaseq" else CHIP_TYPES
    for artifact in artifacts:
        identifier = artifact.get("artifact_id", "<unknown>")
        if artifact.get("assay") != assay or artifact.get("artifact_type") not in allowed:
            errors.append(f"artifact {identifier} has an assay/type mismatch")
        if artifact.get("reference_id") != reference_id:
            errors.append(f"artifact {identifier} references an unknown reference")
        if artifact.get("contrast_id") and artifact["contrast_id"] not in set(contrast_ids):
            errors.append(f"artifact {identifier} references an unknown contrast")
        if assay == "chipseq" and artifact.get("artifact_type") in MARK_REQUIRED_TYPES and not (artifact.get("mark_or_factor") or artifact.get("marks_or_factors")):
            errors.append(f"artifact {identifier} requires mark_or_factor")
        location = artifact.get("location") or {}
        if location.get("kind") == "uri" and not location.get("uri"):
            errors.append(f"artifact {identifier} has no URI")
        if location.get("kind") != "uri" and not location.get("path"):
            errors.append(f"artifact {identifier} has no path")
    samples = document.get("samples") or []
    sample_key = "sample_id" if assay == "rnaseq" else "record_id"
    sample_ids = [sample.get(sample_key) for sample in samples]
    if len(sample_ids) != len(set(sample_ids)):
        errors.append(f"duplicate {sample_key}")
    if assay == "chipseq":
        records = {sample.get("record_id"): sample for sample in samples}
        marks = set(document.get("marks_or_factors") or [])
        for sample in samples:
            if not sample.get("is_control"):
                if not sample.get("mark_or_factor"):
                    errors.append(f"ChIP record {sample.get('record_id')} requires mark_or_factor")
                elif sample["mark_or_factor"] not in marks:
                    errors.append(f"ChIP record {sample.get('record_id')} has an undeclared mark_or_factor")
                control = sample.get("control_record_id")
                if control and (control not in records or not records[control].get("is_control")):
                    errors.append(f"ChIP record {sample.get('record_id')} has an invalid control relationship")
    return errors


def filesystem_errors(document: dict[str, Any], manifest_path: Path, producer_bases: dict[str, Path] | None = None) -> list[str]:
    errors: list[str] = []
    producer_bases = producer_bases or {}
    for artifact in document.get("artifacts") or []:
        location = artifact.get("location") or {}
        kind = location.get("kind")
        if kind == "uri":
            continue
        raw = location.get("path")
        if not raw:
            continue
        if kind == "manifest_relative":
            path = manifest_path.parent / raw
        elif kind == "producer_relative":
            producer_id = location.get("producer_manifest_id")
            if producer_id not in producer_bases:
                errors.append(f"artifact {artifact.get('artifact_id')} has no base for producer manifest {producer_id}")
                continue
            path = producer_bases[producer_id] / raw
        else:
            path = Path(raw)
        if not path.exists():
            errors.append(f"artifact {artifact.get('artifact_id')} is missing: {path}")
            continue
        checksum = artifact.get("checksum")
        if checksum and checksum.get("algorithm") == "sha256" and sha256_path(path) != checksum.get("value"):
            errors.append(f"artifact {artifact.get('artifact_id')} checksum mismatch")
    return errors


def compatibility_errors(left: dict[str, Any], right: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    left_ref, right_ref = left.get("reference") or {}, right.get("reference") or {}
    for field in ("reference_id", "genome_id"):
        if left_ref.get(field) != right_ref.get(field):
            errors.append(f"{field} incompatible: {left_ref.get(field)!r} != {right_ref.get(field)!r}")
    if left_ref.get("assembly") and right_ref.get("assembly") and left_ref["assembly"] != right_ref["assembly"]:
        errors.append(f"assembly incompatible: {left_ref['assembly']!r} != {right_ref['assembly']!r}")
    if str(left_ref.get("organism", "")).casefold() != str(right_ref.get("organism", "")).casefold():
        errors.append(f"organism incompatible: {left_ref.get('organism')!r} != {right_ref.get('organism')!r}")
    return errors
