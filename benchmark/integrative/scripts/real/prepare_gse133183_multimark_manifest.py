#!/usr/bin/env python3
"""Compose validated H3K27ac and H3K27me3 terminal manifests for GSE133183.

This benchmark adapter does not transform scientific tables. It verifies and
copies the six Integration API artifacts byte-for-byte.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "bin"))

from integration_contract import (  # noqa: E402
    compatibility_errors,
    filesystem_errors,
    schema_contract_errors,
    semantic_errors,
    sha256_path,
)


EXPECTED_MARKS = ("H3K27ac", "H3K27me3")
INTEGRATION_TYPES = {"consensus_peaks", "differential_binding", "peak_gene_annotation"}
COMPOSITE_ID = "gse133183_k562.multimark.chipseq"
COMPOSITE_DATASET = "gse133183_multimark"


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"manifest must be a JSON object: {path}")
    return value


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def dump_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def validate_source(document: dict[str, Any], path: Path, expected_mark: str) -> None:
    errors = schema_contract_errors(document) + semantic_errors(document)
    if document.get("type") != "chipseq_run_manifest":
        errors.append("source is not a chipseq_run_manifest")
    if document.get("status") != "complete":
        errors.append("source manifest is not complete")
    if document.get("marks_or_factors") != [expected_mark]:
        errors.append(f"source must declare exactly {expected_mark}")
    portable = copy.deepcopy(document)
    portable["artifacts"] = select_artifacts(document, expected_mark)
    errors.extend(filesystem_errors(portable, path))
    if errors:
        raise ValueError(f"invalid {expected_mark} source manifest: " + "; ".join(errors))


def contrast_signature(contrast: dict[str, Any]) -> dict[str, Any]:
    return {
        field: copy.deepcopy(contrast.get(field))
        for field in ("contrast_id", "factor", "numerator", "denominator", "formula", "covariates", "assay")
    }


def merge_samples(documents: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    records: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for document in documents:
        for raw in document["samples"]:
            sample = copy.deepcopy(raw)
            sample["dataset"] = COMPOSITE_DATASET
            record_id = str(sample["record_id"])
            previous = records.get(record_id)
            if previous is not None:
                if previous != sample:
                    raise ValueError(f"shared ChIP record differs between manifests: {record_id}")
                duplicates.append(record_id)
                continue
            records[record_id] = sample
    return [records[key] for key in sorted(records)], sorted(set(duplicates))


def select_artifacts(document: dict[str, Any], expected_mark: str) -> list[dict[str, Any]]:
    selected = [copy.deepcopy(item) for item in document["artifacts"] if item.get("artifact_type") in INTEGRATION_TYPES]
    counts = {kind: 0 for kind in INTEGRATION_TYPES}
    for artifact in selected:
        kind = artifact["artifact_type"]
        counts[kind] += 1
        if artifact.get("mark_or_factor") != expected_mark:
            raise ValueError(f"{expected_mark} artifact has inconsistent mark: {artifact['artifact_id']}")
        if (artifact.get("location") or {}).get("kind") != "manifest_relative":
            raise ValueError(f"integration artifact is not portable: {artifact['artifact_id']}")
    if any(count != 1 for count in counts.values()):
        raise ValueError(f"{expected_mark} must expose exactly one artifact of each integration type: {counts}")
    return sorted(selected, key=lambda item: item["artifact_id"])


def compose_document(
    ac_document: dict[str, Any],
    me3_document: dict[str, Any],
    *,
    git_commit: str,
    job_id: str | None,
    source_checksums: dict[str, str],
) -> tuple[dict[str, Any], list[str]]:
    compatibility = compatibility_errors(ac_document, me3_document)
    if compatibility:
        raise ValueError("ChIP source manifests are incompatible: " + "; ".join(compatibility))
    if ac_document.get("conditions") != me3_document.get("conditions"):
        raise ValueError("ChIP source manifests declare different conditions")
    if len(ac_document.get("contrasts", [])) != 1 or len(me3_document.get("contrasts", [])) != 1:
        raise ValueError("each source manifest must declare exactly one contrast")
    if contrast_signature(ac_document["contrasts"][0]) != contrast_signature(me3_document["contrasts"][0]):
        raise ValueError("ChIP source manifests declare different contrast semantics")

    samples, duplicate_records = merge_samples([ac_document, me3_document])
    artifacts = select_artifacts(ac_document, "H3K27ac") + select_artifacts(me3_document, "H3K27me3")
    contrast = copy.deepcopy(ac_document["contrasts"][0])
    contrast["label"] = "GSE133183 K562 GSK343 versus DMSO"
    contrast["metadata"] = {
        "marks_or_factors": list(EXPECTED_MARKS),
        "source_contrast_labels": [ac_document["contrasts"][0].get("label"), me3_document["contrasts"][0].get("label")],
    }
    source_ids = [ac_document["id"], me3_document["id"]]
    software_version = str(ac_document["run"].get("helixforge_version") or "1.0.0-rc.1")
    document = {
        "schema_version": "1.0",
        "integration_api_version": "1.0",
        "type": "chipseq_run_manifest",
        "id": COMPOSITE_ID,
        "status": "complete",
        "run": {
            "workflow": "chipseq", "run_id": "gse133183-integrative-multimark-v1",
            "run_name": "GSE133183 K562 multi-mark integration input", "created_at": None,
            "helixforge_version": software_version, "git_commit": git_commit,
            "nextflow_version": str(ac_document["run"].get("nextflow_version") or "25.10.7"),
            "profile": "slurm-manifest-reentry",
            "source": {"type": "helixforge", "name": "HelixForge benchmark adapter", "version": "1.0"},
        },
        "reference": copy.deepcopy(ac_document["reference"]),
        "samples": samples,
        "conditions": copy.deepcopy(ac_document["conditions"]),
        "marks_or_factors": list(EXPECTED_MARKS),
        "contrasts": [contrast],
        "artifacts": sorted(artifacts, key=lambda item: item["artifact_id"]),
        "provenance": {
            "producer_workflow": "integrative_benchmark",
            "producer_process": "PREPARE_GSE133183_MULTIMARK_MANIFEST",
            "software": [{"name": "python", "version": sys.version.split()[0], "container": None}],
            "parameters": {
                "adapter_version": "1.0", "dataset_normalization": COMPOSITE_DATASET,
                "scientific_artifacts_changed": False,
                "source_manifest_checksums": source_checksums,
                "deduplicated_control_record_ids": duplicate_records,
            },
            "source_manifest_ids": source_ids,
            "source_artifact_ids": [item["artifact_id"] for item in artifacts],
            "execution_metadata": {"slurm_job_id": job_id} if job_id else None,
        },
    }
    errors = schema_contract_errors(document) + semantic_errors(document)
    if errors:
        raise ValueError("invalid composite manifest: " + "; ".join(errors))
    return document, duplicate_records


def materialize_artifacts(document: dict[str, Any], sources: dict[str, Path], output_dir: Path) -> None:
    for artifact in document["artifacts"]:
        mark = artifact["mark_or_factor"]
        source_manifest = sources[mark]
        relative = Path(artifact["location"]["path"])
        source = source_manifest.parent / relative
        target = output_dir / relative
        expected = artifact["checksum"]["value"]
        if not source.is_file() or sha256_path(source) != expected:
            raise ValueError(f"source artifact missing or checksum-invalid: {artifact['artifact_id']}")
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        if sha256_path(target) != expected:
            raise ValueError(f"materialized artifact checksum mismatch: {artifact['artifact_id']}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--h3k27ac-manifest", required=True, type=Path)
    parser.add_argument("--h3k27me3-manifest", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id:
        raise SystemExit("GSE133183 multi-mark preparation must execute inside a Slurm job")

    source_paths = {"H3K27ac": args.h3k27ac_manifest.resolve(), "H3K27me3": args.h3k27me3_manifest.resolve()}
    documents = {mark: load_json(path) for mark, path in source_paths.items()}
    for mark in EXPECTED_MARKS:
        validate_source(documents[mark], source_paths[mark], mark)
    source_checksums = {mark: sha256(path) for mark, path in source_paths.items()}
    document, duplicate_records = compose_document(
        documents["H3K27ac"], documents["H3K27me3"], git_commit=args.git_commit,
        job_id=job_id, source_checksums=source_checksums,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    materialize_artifacts(document, source_paths, args.output_dir)
    manifest_path = args.output_dir / "chipseq_run_manifest.json"
    dump_json(manifest_path, document)
    errors = filesystem_errors(document, manifest_path)
    if errors:
        raise ValueError("invalid composite filesystem: " + "; ".join(errors))

    audit = {
        "status": "PASS", "adapter": "GSE133183 multi-mark terminal-manifest composition",
        "manifest_id": COMPOSITE_ID, "manifest_sha256": sha256(manifest_path),
        "source_manifest_checksums": source_checksums, "marks_or_factors": list(EXPECTED_MARKS),
        "input_sample_records": sum(len(item["samples"]) for item in documents.values()),
        "output_sample_records": len(document["samples"]),
        "deduplicated_control_record_ids": duplicate_records,
        "artifact_count": len(document["artifacts"]), "scientific_artifacts_changed": False,
        "slurm_job_id": job_id,
    }
    dump_json(args.output_dir / "multimark_adapter_audit.json", audit)
    checksums = [
        f"{sha256(manifest_path)}  chipseq_run_manifest.json",
        f"{sha256(args.output_dir / 'multimark_adapter_audit.json')}  multimark_adapter_audit.json",
    ]
    (args.output_dir / "SHA256SUMS").write_text("\n".join(checksums) + "\n", encoding="utf-8")
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
