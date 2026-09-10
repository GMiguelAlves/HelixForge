#!/usr/bin/env python3
"""Build integration-consistent evidence from a differential-binding table."""

from __future__ import annotations

import argparse
import base64
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "bin"))

from integration_contract import filesystem_errors, schema_contract_errors, semantic_errors  # noqa: E402
from validate_integration_manifest import jsonschema_errors  # noqa: E402


ANNOTATION_PARAMETERS = {
    "provider": "python_interval_v1",
    "mode": "overlap_priority",
    "overlap_mode": "any",
    "promoter_upstream": 2000,
    "promoter_downstream": 500,
    "max_tss_distance": None,
    "feature_priority": ["promoter", "exon", "intron", "downstream", "gene"],
    "gene_assignment": "first",
    "strand_aware": False,
    "intergenic_policy": "retain",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected a JSON object: {path}")
    return value


def dump_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def find_artifact(document: dict[str, Any], artifact_type: str, mark: str) -> dict[str, Any]:
    matches = [item for item in document.get("artifacts", [])
               if item.get("artifact_type") == artifact_type and item.get("mark_or_factor") == mark]
    if len(matches) != 1:
        raise ValueError(f"expected exactly one {artifact_type} artifact for {mark}, found {len(matches)}")
    return copy.deepcopy(matches[0])


def resolve_artifact(manifest: Path, artifact: dict[str, Any]) -> Path:
    location = artifact.get("location") or {}
    if location.get("kind") != "manifest_relative":
        raise ValueError("differential-binding artifact must be manifest-relative")
    path = (manifest.parent / location["path"]).resolve()
    expected = (artifact.get("checksum") or {}).get("value")
    if not path.is_file() or not expected or sha256(path) != expected:
        raise ValueError("differential-binding artifact is missing or checksum-invalid")
    return path


def write_region_catalog(source: Path, target: Path) -> int:
    required = ("peak_id", "chrom", "start", "end")
    seen: set[str] = set()
    rows = 0
    target.parent.mkdir(parents=True, exist_ok=True)
    with source.open(encoding="utf-8", newline="") as src, target.open("w", encoding="utf-8", newline="") as dst:
        reader = csv.DictReader(src, delimiter="\t")
        missing = [field for field in required if field not in (reader.fieldnames or [])]
        if missing:
            raise ValueError("differential-binding table lacks columns: " + ", ".join(missing))
        for line_number, row in enumerate(reader, 2):
            peak_id = (row.get("peak_id") or "").strip()
            chrom = (row.get("chrom") or "").strip()
            try:
                start, end = int(row["start"]), int(row["end"])
            except (TypeError, ValueError) as error:
                raise ValueError(f"invalid differential region at line {line_number}: {error}") from error
            if not peak_id or peak_id in seen or not chrom or start < 0 or end <= start:
                raise ValueError(f"invalid or duplicate differential region at line {line_number}")
            seen.add(peak_id)
            dst.write(f"{chrom}\t{start}\t{end}\t{peak_id}\n")
            rows += 1
    if not rows:
        raise ValueError("differential-binding table contains no regions")
    return rows


def artifact_template(source: dict[str, Any], *, artifact_id: str, artifact_type: str,
                      role: str, path: Path, relative_path: Path, producer: str,
                      source_artifact_ids: list[str]) -> dict[str, Any]:
    item = copy.deepcopy(source)
    item.update({
        "artifact_id": artifact_id, "artifact_type": artifact_type,
        "format": "bed" if artifact_type == "peak_set" else "tsv",
        "entity_level": "peak", "role": role,
        "location": {"kind": "manifest_relative", "path": relative_path.as_posix(),
                     "base_path": None, "producer_manifest_id": None},
        "checksum": {"algorithm": "sha256", "value": sha256(path)}, "condition": None,
    })
    item["provenance"] = {
        "producer_workflow": "integrative_benchmark", "producer_process": producer,
        "software": ([{"name": "python_interval_v1", "version": "1.0.0", "container": None}]
                     if artifact_type == "peak_gene_annotation" else []),
        "parameters": copy.deepcopy(ANNOTATION_PARAMETERS) if artifact_type == "peak_gene_annotation" else {},
        "source_manifest_ids": [], "source_artifact_ids": source_artifact_ids,
        "execution_metadata": {"slurm_job_id": os.environ.get("SLURM_JOB_ID")},
    }
    item["metadata"] = {
        "benchmark_adapter": "differential_binding_region_evidence_v1",
        "derivation": ("lossless_peak_id_chrom_start_end_projection" if artifact_type == "peak_set"
                       else "native_python_interval_v1_annotation"),
    }
    return item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--terminal-manifest", required=True, type=Path)
    parser.add_argument("--reference-manifest", required=True, type=Path)
    parser.add_argument("--reference", required=True, type=Path)
    parser.add_argument("--annotation", required=True, type=Path)
    parser.add_argument("--context-validator", required=True, type=Path)
    parser.add_argument("--annotator", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--mark", required=True)
    parser.add_argument("--git-commit", required=True)
    args = parser.parse_args()
    job_id = os.environ.get("SLURM_JOB_ID")
    if not job_id:
        raise SystemExit("differential-binding evidence preparation must execute inside a Slurm job")

    terminal_path = args.terminal_manifest.resolve()
    document = load_json(terminal_path)
    errors = schema_contract_errors(document) + semantic_errors(document)
    if errors or document.get("type") != "chipseq_run_manifest" or document.get("status") != "complete":
        raise ValueError("invalid source terminal manifest: " + "; ".join(errors))
    db = find_artifact(document, "differential_binding", args.mark)
    db_source = resolve_artifact(terminal_path, db)
    out = args.output_dir.resolve()
    out.mkdir(parents=True, exist_ok=False)

    region_id = f"{document['id']}.{args.mark}.differential_binding_regions"
    annotation_id = f"{region_id}.annotation"
    region_relative = Path("integration_artifacts") / region_id / "differential_binding_regions.bed"
    db_relative = Path("integration_artifacts") / db["artifact_id"] / "differential_binding_results.tsv"
    annotation_relative = Path("integration_artifacts") / annotation_id / "peak_gene_associations.tsv"
    region_path, db_target = out / region_relative, out / db_relative
    rows = write_region_catalog(db_source, region_path)
    db_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(db_source, db_target)

    samples = [item for item in document["samples"]
               if not item.get("is_control") and item.get("mark_or_factor") == args.mark]
    source_manifest = {
        "schema_version": "1.0", "type": "consensus", "id": region_id, "status": "complete",
        "genome_id": document["reference"]["genome_id"], "build": document["reference"]["assembly"],
        "organism": document["reference"]["organism"], "dataset": document["run"]["run_id"],
        "target": args.mark, "peak_type": db.get("peak_type"),
        "replicates": [{"record_id": item["record_id"], "sample_id": item["sample_id"]} for item in samples],
        "artifacts": {"consolidated_peaks": {"path": region_path.name, "sha256": sha256(region_path)}},
    }
    provenance_dir = out / "annotation_provenance"
    source_manifest_path = provenance_dir / f"{region_id}.manifest.json"
    dump_json(source_manifest_path, source_manifest)
    meta = {"id": annotation_id, "source_id": region_id,
            "genome_id": document["reference"]["genome_id"], "organism": document["reference"]["organism"]}
    request = provenance_dir / f"{annotation_id}.request.json"
    context_report = provenance_dir / f"{annotation_id}.context.json"
    subprocess.run([
        sys.executable, str(args.context_validator),
        "--meta-base64", base64.b64encode(json.dumps(meta).encode()).decode(),
        "--peaks", str(region_path), "--peak-manifest", str(source_manifest_path),
        "--reference", str(args.reference), "--reference-manifest", str(args.reference_manifest),
        "--annotation", str(args.annotation),
        "--spec-base64", base64.b64encode(json.dumps(ANNOTATION_PARAMETERS).encode()).decode(),
        "--request", str(request), "--report", str(context_report),
    ], check=True)
    annotation_dir = provenance_dir / f"{annotation_id}.peak_annotation"
    annotation_manifest = provenance_dir / f"{annotation_id}.manifest.json"
    annotation_execution = provenance_dir / f"{annotation_id}.execution.json"
    annotation_versions = provenance_dir / f"{annotation_id}.versions.yml"
    subprocess.run([
        sys.executable, str(args.annotator), "--request", str(request), "--peaks", str(region_path),
        "--annotation", str(args.annotation), "--output-dir", str(annotation_dir),
        "--manifest", str(annotation_manifest), "--execution", str(annotation_execution),
        "--versions", str(annotation_versions), "--cpus", os.environ.get("SLURM_CPUS_PER_TASK", "1"),
        "--memory-bytes", str(int(os.environ.get("SLURM_MEM_PER_NODE", "12288")) * 1024 * 1024),
        "--task-time", os.environ.get("SLURM_TIMELIMIT", "unknown"), "--nextflow-version", "25.10.7",
    ], check=True)
    associations = annotation_dir / "peak_gene_associations.tsv"
    annotation_target = out / annotation_relative
    annotation_target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(associations, annotation_target)

    region_artifact = artifact_template(
        db, artifact_id=region_id, artifact_type="peak_set", role="differential_binding_region_catalog",
        path=region_path, relative_path=region_relative, producer="DIFFERENTIAL_BINDING_REGION_CATALOG",
        source_artifact_ids=[db["artifact_id"]],
    )
    annotation_artifact = artifact_template(
        db, artifact_id=annotation_id, artifact_type="peak_gene_annotation", role="peak_gene_associations",
        path=annotation_target, relative_path=annotation_relative, producer="PEAK_ANNOTATOR",
        source_artifact_ids=[db["artifact_id"], region_id],
    )
    db["location"] = {"kind": "manifest_relative", "path": db_relative.as_posix(),
                      "base_path": None, "producer_manifest_id": None}
    source_document_id = document["id"]
    document["id"] = f"{source_document_id}.differential_binding_evidence"
    document["run"]["git_commit"] = args.git_commit
    document["artifacts"] = [region_artifact, db, annotation_artifact]
    document["provenance"] = copy.deepcopy(document["provenance"])
    document["provenance"].update({
        "producer_workflow": "integrative_benchmark",
        "producer_process": "PREPARE_DIFFERENTIAL_BINDING_EVIDENCE",
        "parameters": {
            "adapter_version": "1.0", "scientific_results_changed": False,
            "region_projection": ["peak_id", "chrom", "start", "end"],
            "annotation_parameters": copy.deepcopy(ANNOTATION_PARAMETERS),
            "source_terminal_manifest_sha256": sha256(terminal_path),
        },
        "source_manifest_ids": [source_document_id], "source_artifact_ids": [db["artifact_id"]],
        "execution_metadata": {"slurm_job_id": job_id},
    })
    output_manifest = out / "chipseq_run_manifest.json"
    dump_json(output_manifest, document)
    errors = (schema_contract_errors(document) + semantic_errors(document)
              + jsonschema_errors(document, ROOT / "schemas" / "integration")
              + filesystem_errors(document, output_manifest))
    if errors:
        raise ValueError("prepared terminal manifest failed validation: " + "; ".join(errors))

    association_rows = sum(1 for _ in associations.open(encoding="utf-8")) - 1
    audit = {
        "status": "PASS", "adapter": "differential_binding_region_evidence_v1", "mark": args.mark,
        "region_count": rows, "annotation_rows": association_rows,
        "source_manifest_sha256": sha256(terminal_path), "output_manifest_sha256": sha256(output_manifest),
        "db_artifact_byte_identical": sha256(db_source) == sha256(db_target),
        "region_ids_preserved_one_to_one": True, "scientific_results_changed": False,
        "annotation_provider": "python_interval_v1", "annotation_parameters": ANNOTATION_PARAMETERS,
        "slurm_job_id": job_id,
    }
    dump_json(out / "differential_binding_evidence_audit.json", audit)
    (out / "SHA256SUMS").write_text(
        f"{sha256(output_manifest)}  chipseq_run_manifest.json\n"
        f"{sha256(out / 'differential_binding_evidence_audit.json')}  differential_binding_evidence_audit.json\n",
        encoding="utf-8",
    )
    print(json.dumps(audit, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
