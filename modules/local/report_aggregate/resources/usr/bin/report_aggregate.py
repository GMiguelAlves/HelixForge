#!/usr/bin/env python3
import argparse
import csv
import hashlib
import json
import sys
import time
from collections import defaultdict
from pathlib import Path


TYPE_SECTION = {
    "metadata": "project", "chipseq_metadata": "project",
    "reference": "reference", "reference_bundle": "reference",
    "alignment": "alignment", "bam_aligned": "alignment",
    "bam_final": "bam_processing", "peak_calling": "peak_calling",
    "peak_qc": "peak_qc", "peak_qc_summary": "peak_qc",
    "consensus_idr": "consensus_idr", "consensus_idr_summary": "consensus_idr", "idr": "consensus_idr",
    "differential_binding": "differential_binding",
    "peak_annotation": "annotation", "peak_annotation_aggregate": "annotation",
    "track_generation": "tracks", "track_aggregate": "tracks",
    "provenance": "provenance", "execution": "provenance", "versions": "provenance",
}


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path):
    with Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path, value):
    Path(path).write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def declared_checksums(documents):
    result = defaultdict(list)
    for document in documents:
        source_id = document.get("id") or document.get("type")
        for item in iter_dicts(document):
            digest = item.get("sha256")
            if isinstance(digest, str) and len(digest) == 64:
                result[digest].append({"source_id": source_id, "role": item.get("path")})
    return result


def load_semantic_artifacts(paths, declarations):
    loaded = []
    for path in paths:
        digest = sha256(path)
        if digest not in declarations:
            raise ValueError(f"artifact is not checksum-declared by an input manifest: {path}")
        record = {"sha256": digest, "declarations": declarations[digest], "content": None, "format": "opaque"}
        try:
            record["content"] = load_json(path)
            record["format"] = "json"
        except (json.JSONDecodeError, UnicodeDecodeError):
            try:
                with Path(path).open(encoding="utf-8", newline="") as handle:
                    record["content"] = list(csv.DictReader(handle, delimiter="\t"))
                record["format"] = "tsv"
            except (UnicodeDecodeError, csv.Error):
                pass
        loaded.append(record)
    return loaded


def status_for(context, component):
    return context["components"][component]["status"]


def section(status, data=None):
    return {"status": status, "data": data if status != "not_requested" else None}


def select_docs(documents, *types):
    allowed = set(types)
    return [document for document in documents if document.get("type") in allowed]


def top_fields(document, fields):
    return {field: document.get(field) for field in fields}


def artifact_content(artifacts, expected_type=None, role_fragment=None):
    matches = []
    for artifact in artifacts:
        content = artifact["content"]
        roles = [str(value.get("role") or "") for value in artifact["declarations"]]
        type_match = isinstance(content, dict) and content.get("type") == expected_type if expected_type else True
        role_match = any(role_fragment in role for role in roles) if role_fragment else True
        if type_match and role_match:
            matches.append(content)
    return matches


def aggregate(context, documents, artifacts):
    project = context["project"]
    metadata_docs = select_docs(documents, "metadata", "chipseq_metadata")
    reference_docs = select_docs(documents, "reference", "reference_bundle")
    alignment_docs = select_docs(documents, "alignment", "bam_aligned")
    bam_docs = select_docs(documents, "bam_final")
    peak_docs = select_docs(documents, "peak_calling")
    qc_docs = select_docs(documents, "peak_qc", "peak_qc_summary")
    consensus_docs = select_docs(documents, "consensus_idr", "consensus_idr_summary", "idr")
    db_docs = select_docs(documents, "differential_binding")
    annotation_docs = select_docs(documents, "peak_annotation", "peak_annotation_aggregate")
    track_docs = select_docs(documents, "track_generation", "track_aggregate")

    sample_records = {}
    for document in documents:
        for item in iter_dicts(document):
            record_id = item.get("record_id")
            if not record_id:
                continue
            row = sample_records.setdefault(str(record_id), {"record_id": str(record_id)})
            for field in ("sample_id", "dataset", "condition", "target", "biological_replicate", "technical_replicate", "is_control", "control_id", "control_record_id"):
                if item.get(field) is not None:
                    row[field] = item[field]

    bam_records = []
    for document in bam_docs:
        row = top_fields(document, ("id", "record_id", "sample_id", "dataset", "duplicate_policy", "blacklist_policy"))
        row["selection"] = document.get("selection")
        row["metrics"] = document.get("metrics")
        bam_records.append(row)

    peak_records = []
    for document in peak_docs:
        row = top_fields(document, ("id", "record_id", "sample_id", "dataset", "condition", "target", "biological_replicate", "technical_replicate", "control_id", "control_record_id", "caller", "caller_version", "peak_type", "status"))
        row["parameters"] = document.get("parameters")
        row["metrics"] = document.get("metrics")
        peak_records.append(row)

    qc_rows = []
    for document in qc_docs:
        if isinstance(document.get("rows"), list):
            qc_rows.extend(document["rows"])
    for document in artifact_content(artifacts, expected_type="peak_qc_summary"):
        qc_rows.extend(document.get("rows", []))

    consensus_rows = []
    for document in consensus_docs:
        if isinstance(document.get("rows"), list):
            consensus_rows.extend(document["rows"])
    for document in artifact_content(artifacts, expected_type="consensus_idr_summary"):
        consensus_rows.extend(document.get("rows", []))
    idr_docs = [document for document in consensus_docs if document.get("type") == "idr"]
    idr_status = "not_requested" if not idr_docs else (
        "not_implemented" if any(document.get("status") == "not_implemented" for document in idr_docs)
        else context["components"]["consensus_idr"]["status"]
    )

    db_summaries = []
    for artifact in artifacts:
        for declaration in artifact["declarations"]:
            if "differential_binding_summary" in str(declaration.get("role") or "") and isinstance(artifact["content"], list):
                db_summaries.extend(artifact["content"])
    annotation_statistics = []
    track_rows = []
    for artifact in artifacts:
        for declaration in artifact["declarations"]:
            role = str(declaration.get("role") or "")
            if "statistics" in role and isinstance(artifact["content"], list):
                annotation_statistics.extend(artifact["content"])
            if "tracks.tsv" in role and isinstance(artifact["content"], list):
                track_rows.extend(artifact["content"])

    provenance_sources = []
    for document in documents:
        provenance_sources.append({
            "type": document.get("type"), "id": document.get("id"), "status": document.get("status"),
            "provider": document.get("provider"), "parameters": document.get("parameters"),
            "versions": document.get("versions"), "execution": document.get("execution"),
            "command": document.get("command"),
        })

    sections = {
        "project": section("available", {"project": project, "samples": [sample_records[key] for key in sorted(sample_records)], "metadata_manifests": len(metadata_docs)}),
        "reference": section(status_for(context, "reference"), {"manifests": reference_docs}),
        "sequencing_qc": section(status_for(context, "metadata"), {"metadata": metadata_docs}),
        "alignment": section(status_for(context, "alignment"), {"records": alignment_docs}),
        "bam_processing": section(status_for(context, "bam"), {"records": bam_records}),
        "peak_calling": section(status_for(context, "peak"), {"records": peak_records}),
        "peak_qc": section(status_for(context, "peak_qc"), {"records": qc_rows}),
        "consensus_idr": section(status_for(context, "consensus_idr"), {"records": consensus_rows, "idr_status": idr_status, "manifests": consensus_docs}),
        "differential_binding": section(status_for(context, "differential_binding"), {"manifests": db_docs, "summaries": db_summaries}),
        "annotation": section(status_for(context, "annotation"), {"manifests": annotation_docs, "statistics": annotation_statistics}),
        "tracks": section(status_for(context, "tracks"), {"manifests": track_docs, "records": track_rows}),
        "provenance": section("available", {"versions": context.get("versions", {}), "sources": provenance_sources}),
    }
    return {
        "schema_version": "1.0", "type": "chipseq_report_data", "id": context["id"],
        "project": project, "sections": sections, "source_manifest_count": len(documents),
        "source_artifact_count": len(artifacts), "status": context["status"],
    }


def write_tsv(path, fields, rows):
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--context", required=True)
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--artifact", action="append", default=[])
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--execution", required=True)
    parser.add_argument("--versions", required=True)
    parser.add_argument("--cpus", type=int, required=True)
    parser.add_argument("--memory-bytes", type=int, required=True)
    parser.add_argument("--task-time", required=True)
    args = parser.parse_args()
    started = int(time.time())
    context = load_json(args.context)
    documents = [load_json(path) for path in args.manifest]
    artifacts = load_semantic_artifacts(args.artifact, declared_checksums(documents))
    data = aggregate(context, documents, artifacts)
    output = Path(args.output_dir); output.mkdir(parents=True, exist_ok=True)
    write_json(output / "report_data.json", data)
    component_rows = [{"component": name, "status": value["status"]} for name, value in data["sections"].items()]
    write_tsv(output / "components.tsv", ("component", "status"), component_rows)
    records = data["sections"]["project"]["data"]["samples"]
    record_fields = ("record_id", "sample_id", "dataset", "condition", "target", "biological_replicate", "technical_replicate", "is_control", "control_id")
    write_tsv(output / "records.tsv", record_fields, records)
    provenance = data["sections"]["provenance"]["data"]
    write_json(output / "provenance.json", provenance)
    with (output / "versions.yml").open("w", encoding="utf-8") as handle:
        handle.write('"REPORT_AGGREGATE":\n')
        handle.write(f'    python: "{sys.version.split()[0]}"\n')
        for name, version in sorted(context.get("versions", {}).items()):
            handle.write(f'    {name}: "{version}"\n')
    ended = int(time.time())
    execution = {"schema_version": "1.0", "id": context["id"], "process": "REPORT_AGGREGATE", "cpus": args.cpus, "memory_bytes": args.memory_bytes, "time": args.task_time, "started_epoch": started, "ended_epoch": ended, "elapsed_seconds": ended - started}
    write_json(args.execution, execution)
    manifest = {
        "schema_version": "1.0", "type": "chipseq_report_aggregate", "id": context["id"],
        "project": context["project"], "components": component_rows,
        "artifacts": {
            "report_data": {"path": "report_data.json", "sha256": sha256(output / "report_data.json")},
            "components": {"path": "components.tsv", "sha256": sha256(output / "components.tsv")},
            "records": {"path": "records.tsv", "sha256": sha256(output / "records.tsv")},
            "provenance": {"path": "provenance.json", "sha256": sha256(output / "provenance.json")},
            "versions": {"path": "versions.yml", "sha256": sha256(output / "versions.yml")},
        }, "status": data["status"],
    }
    write_json(output / "manifest.json", manifest)
    Path(args.versions).write_text((output / "versions.yml").read_text(encoding="utf-8"), encoding="utf-8")
    print(f"Aggregated {len(documents)} manifests and {len(artifacts)} declared artifacts")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(2)
