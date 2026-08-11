#!/usr/bin/env python3
import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path


COMPONENTS = (
    "metadata", "reference", "alignment", "bam", "peak", "peak_qc",
    "consensus_idr", "differential_binding", "annotation", "tracks", "provenance",
)

TYPE_COMPONENT = {
    "metadata": "metadata", "chipseq_metadata": "metadata",
    "reference": "reference", "reference_bundle": "reference",
    "alignment": "alignment", "bam_aligned": "alignment",
    "bam_final": "bam",
    "peak_calling": "peak",
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
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"manifest is not a JSON object: {path}")
    return value


def text(value):
    return None if value is None or str(value).strip() == "" else str(value).strip()


def normalize_status(document):
    raw = text(document.get("status")) or "incomplete"
    lowered = raw.lower()
    nested = []
    for key in ("rows", "groups", "results"):
        if isinstance(document.get(key), list):
            nested.extend(text(row.get("status")) for row in document[key] if isinstance(row, dict))
    nested = [value.lower() for value in nested if value]
    values = [lowered] + nested
    if any(value in {"failed", "error"} for value in values):
        return "failed"
    if any(value == "not_implemented" for value in values):
        return "not_implemented"
    if all(value in {"complete", "complete_empty", "available", "success"} for value in values):
        return "available"
    return "incomplete"


def iter_dicts(value):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from iter_dicts(child)
    elif isinstance(value, list):
        for child in value:
            yield from iter_dicts(child)


def compatible(label, expected, documents):
    observed = {text(item.get(label)) for document in documents for item in iter_dicts(document)}
    observed.discard(None)
    if observed and observed != {expected}:
        raise ValueError(f"{label} conflict: expected {expected!r}, observed {sorted(observed)!r}")


def collect_versions(documents):
    values = defaultdict(set)
    for document in documents:
        versions = document.get("versions")
        if isinstance(versions, dict):
            for name, version in versions.items():
                if isinstance(version, (str, int, float)):
                    values[str(name)].add(str(version))
        for key in ("caller", "provider"):
            name = text(document.get(key))
            version = text(document.get(f"{key}_version"))
            if name and version:
                values[name].add(version)
    conflicts = {name: sorted(found) for name, found in values.items() if len(found) > 1}
    if conflicts:
        raise ValueError(f"version conflicts: {conflicts}")
    return {name: next(iter(found)) for name, found in sorted(values.items())}


def validate(inventory, manifest_paths):
    if inventory.get("schema_version") != "1.0" or inventory.get("type") != "chipseq_report_input":
        raise ValueError("inventory must declare schema_version=1.0 and type=chipseq_report_input")
    project = inventory.get("project")
    if not isinstance(project, dict):
        raise ValueError("inventory project must be an object")
    for field in ("project_id", "dataset", "genome_id", "build"):
        if not text(project.get(field)):
            raise ValueError(f"project.{field} is required")
        project[field] = text(project[field])
    required = inventory.get("required_components")
    entries = inventory.get("components")
    if not isinstance(required, list) or not isinstance(entries, list):
        raise ValueError("required_components and components must be arrays")
    if len(required) != len(set(required)) or any(value not in COMPONENTS for value in required):
        raise ValueError("required_components contains duplicate or unsupported roles")
    requested = Counter()
    for entry in entries:
        if not isinstance(entry, dict) or entry.get("component") not in COMPONENTS or not text(entry.get("manifest")):
            raise ValueError("each component entry requires supported component and manifest")
        if not isinstance(entry.get("artifacts", []), list):
            raise ValueError("component artifacts must be an array")
        requested[entry["component"]] += 1
    if len(manifest_paths) != len(entries):
        raise ValueError(f"inventory declares {len(entries)} manifests but Nextflow staged {len(manifest_paths)}")

    documents = []
    detected = Counter()
    seen = set()
    component_docs = defaultdict(list)
    for path in manifest_paths:
        document = load_json(path)
        schema = text(document.get("schema_version"))
        manifest_type = text(document.get("type"))
        if not schema or not manifest_type:
            raise ValueError(f"manifest lacks schema_version/type: {path}")
        component = TYPE_COMPONENT.get(manifest_type)
        if component is None:
            raise ValueError(f"unsupported manifest type {manifest_type!r}: {path}")
        digest = sha256(path)
        identifier = text(document.get("id")) or f"{manifest_type}:{digest[:12]}"
        identity = (manifest_type, identifier)
        if identity in seen:
            raise ValueError(f"duplicate manifest identity: {identity}")
        seen.add(identity)
        status = normalize_status(document)
        info = {
            "type": manifest_type, "id": identifier, "schema_version": schema,
            "sha256": digest, "status": status,
        }
        detected[component] += 1
        component_docs[component].append((document, info))
        documents.append(document)
    if requested != detected:
        raise ValueError(f"inventory roles disagree with manifest types: requested={dict(requested)}, detected={dict(detected)}")

    compatible("dataset", project["dataset"], documents)
    compatible("genome_id", project["genome_id"], documents)
    compatible("build", project["build"], documents)

    record_samples = {}
    records = []
    for document in documents:
        for item in iter_dicts(document):
            record_id = text(item.get("record_id"))
            sample_id = text(item.get("sample_id"))
            if not record_id:
                continue
            if record_id in record_samples and sample_id and record_samples[record_id] not in (None, sample_id):
                raise ValueError(f"record_id {record_id!r} maps to conflicting sample IDs")
            record_samples[record_id] = sample_id or record_samples.get(record_id)
    for record_id, sample_id in sorted(record_samples.items()):
        records.append({"record_id": record_id, "sample_id": sample_id})

    components = {}
    severity = {"failed": 4, "incomplete": 3, "not_implemented": 2, "available": 1}
    for component in COMPONENTS:
        supplied = component_docs.get(component, [])
        if not supplied:
            status = "not_requested"
        else:
            statuses = [info["status"] for _document, info in supplied]
            status = max(statuses, key=lambda value: severity[value])
            if len(set(statuses)) > 1 and "failed" not in statuses:
                status = "incomplete"
        components[component] = {"status": status, "manifests": [info for _document, info in supplied]}
    missing = [component for component in required if components[component]["status"] == "not_requested"]
    if missing:
        raise ValueError(f"required components not supplied: {missing}")

    statuses = [value["status"] for value in components.values() if value["status"] != "not_requested"]
    overall = "available" if statuses and all(value == "available" for value in statuses) else "incomplete"
    return {
        "schema_version": "1.0", "type": "chipseq_report_context",
        "id": f"{project['project_id']}.chipseq_report", "project": project,
        "required_components": required, "components": components,
        "records": records, "versions": collect_versions(documents), "status": overall,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--inventory", required=True)
    parser.add_argument("--manifest", action="append", default=[])
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    inventory = load_json(args.inventory)
    result = validate(inventory, args.manifest)
    Path(args.output).write_text(json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Validated {sum(len(value['manifests']) for value in result['components'].values())} manifests")


if __name__ == "__main__":
    main()
