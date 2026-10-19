#!/usr/bin/env python3
import argparse
import base64
import hashlib
import json
import os
import sys


EXPECTED_COLUMNS = {"narrow": 10, "broad": 9}
GROUP_FIELDS = ("dataset", "experiment_id", "condition", "target", "genome_id", "peak_type")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def load_json(path, label):
    if not os.path.isfile(path) or os.path.getsize(path) == 0:
        raise ValueError(f"{label} is missing or empty: {path}")
    with open(path, encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"{label} must contain a JSON object")
    return value


def validate_peak_file(path, peak_type):
    expected = EXPECTED_COLUMNS[peak_type]
    count = 0
    if not os.path.isfile(path):
        raise ValueError(f"semantic peak file is missing: {path}")
    with open(path, encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            columns = line.rstrip("\n").split("\t")
            if len(columns) != expected:
                raise ValueError(f"{path} line {line_number}: {peak_type}Peak requires {expected} columns")
            try:
                start, end = int(columns[1]), int(columns[2])
                float(columns[4])
                float(columns[6])
                if peak_type == "narrow":
                    int(columns[9])
            except ValueError as error:
                raise ValueError(f"{path} line {line_number}: invalid peak field: {error}")
            if not columns[0] or any(char.isspace() for char in columns[0]):
                raise ValueError(f"{path} line {line_number}: invalid chromosome {columns[0]!r}")
            if start < 0 or end <= start:
                raise ValueError(f"{path} line {line_number}: invalid half-open coordinates")
            count += 1
    return count


def index_paths(paths, label):
    result = {}
    for path in paths:
        name = os.path.basename(os.path.normpath(path))
        if name in result:
            raise ValueError(f"duplicate staged {label} basename: {name}")
        result[name] = path
    return result


def positive_probability(value, field):
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be an explicit number")
    if not 0 < parsed <= 1:
        raise ValueError(f"{field} must be > 0 and <= 1")
    return parsed


def validate_group(records, spec):
    if len(records) < 2:
        raise ValueError("Consensus/IDR requires at least two replicate evidence units")
    for field in GROUP_FIELDS:
        values = {str(record.get(field, "")).strip() for record in records}
        if "" in values:
            raise ValueError(f"group contains a missing {field}")
        if len(values) != 1:
            raise ValueError(f"cross-talk detected: group contains incompatible {field} values {sorted(values)}")
    if spec.get("require_same_caller", True):
        callers = {(record.get("caller"), record.get("caller_version")) for record in records}
        if len(callers) != 1:
            raise ValueError(f"group contains incompatible peak callers: {sorted(callers)}")

    replicate_mode = str(spec.get("replicate_mode", "biological")).lower()
    replicate_policy = str(spec.get("replicate_policy", "require_premerged")).lower()
    if replicate_mode not in {"biological", "technical"}:
        raise ValueError("replicate_mode must be biological or technical")
    if replicate_policy not in {"preserve", "require_premerged"}:
        raise ValueError("replicate_policy must be preserve or require_premerged; merge is not implemented")
    if replicate_mode == "biological" and replicate_policy != "require_premerged":
        raise ValueError("biological replicate mode requires replicate_policy=require_premerged in v1")
    if replicate_mode == "technical" and replicate_policy != "preserve":
        raise ValueError("technical replicate mode requires replicate_policy=preserve")

    keys = set()
    biological_counts = {}
    for record in records:
        biological = str(record.get("biological_replicate", "")).strip()
        technical = str(record.get("technical_replicate", "")).strip()
        if not biological:
            raise ValueError(f"record {record.get('record_id')}: biological_replicate is missing")
        if not technical:
            raise ValueError(f"record {record.get('record_id')}: technical_replicate is missing")
        biological_counts[biological] = biological_counts.get(biological, 0) + 1
        key = biological if replicate_mode == "biological" else f"{biological}.{technical}"
        if key in keys and replicate_mode == "technical":
            raise ValueError(f"duplicate {replicate_mode} replicate key: {key}")
        keys.add(key)
        record["evidence_replicate_id"] = key
    if replicate_mode == "biological":
        duplicates = sorted(key for key, count in biological_counts.items() if count > 1)
        if duplicates:
            raise ValueError(f"technical replicates are not premerged for biological replicate(s): {duplicates}")
    return replicate_mode, replicate_policy


def build_request(records, peak_dirs, peak_manifests, qc_manifests, spec):
    replicate_mode, replicate_policy = validate_group(records, spec)
    strategy = str(spec.get("strategy", "")).lower()
    if strategy not in {"union", "intersection", "replicate_support", "idr"}:
        raise ValueError("strategy must be union, intersection, replicate_support, or idr")
    peak_type = records[0]["peak_type"]
    directory_index = index_paths(peak_dirs, "peak directory")
    peak_manifest_docs = {document["id"]: (document, path) for path in peak_manifests for document in [load_json(path, "peak manifest")]}
    qc_manifest_docs = {document["id"]: (document, path) for path in qc_manifests for document in [load_json(path, "Peak QC manifest")]}
    if len(peak_manifest_docs) != len(peak_manifests) or len(qc_manifest_docs) != len(qc_manifests):
        raise ValueError("duplicate peak or Peak QC manifest id")

    normalized = []
    for record in sorted(records, key=lambda value: value["evidence_replicate_id"]):
        peak_id = record["peak_id"]
        if peak_id not in peak_manifest_docs or peak_id not in qc_manifest_docs:
            raise ValueError(f"record {record['record_id']}: missing Peak Calling or Peak QC manifest for {peak_id}")
        peak_document, peak_manifest_path = peak_manifest_docs[peak_id]
        qc_document, qc_manifest_path = qc_manifest_docs[peak_id]
        if peak_document.get("type") != "peak_calling" or qc_document.get("type") != "peak_qc_frip":
            raise ValueError(f"{peak_id}: invalid manifest types for Consensus/IDR")
        for field in ("record_id", "sample_id", "target", "biological_replicate", "technical_replicate", "peak_type", "caller", "caller_version"):
            if str(peak_document.get(field, "")) != str(record.get(field, "")):
                raise ValueError(f"{peak_id}: Peak Calling manifest disagrees on {field}")
            if str(qc_document.get(field, "")) != str(record.get(field, "")):
                raise ValueError(f"{peak_id}: Peak QC manifest disagrees on {field}")
        directory_name = record["peak_directory"]
        if directory_name not in directory_index:
            raise ValueError(f"{peak_id}: staged peak directory {directory_name!r} is missing")
        extension = "narrowPeak" if peak_type == "narrow" else "broadPeak"
        peak_file = os.path.join(directory_index[directory_name], f"peaks.{extension}")
        peak_count = validate_peak_file(peak_file, peak_type)
        normalized.append({
            **record,
            "peak_directory": directory_name,
            "peak_file": f"peaks.{extension}",
            "peak_count": peak_count,
            "peak_manifest": os.path.basename(peak_manifest_path),
            "peak_manifest_sha256": sha256(peak_manifest_path),
            "peak_qc_manifest": os.path.basename(qc_manifest_path),
            "peak_qc_manifest_sha256": sha256(qc_manifest_path),
        })

    count = len(normalized)
    min_replicates = spec.get("min_replicates")
    if strategy == "union":
        support_threshold = 1
    elif strategy == "intersection":
        support_threshold = count
    elif strategy == "replicate_support":
        try:
            support_threshold = int(min_replicates)
        except (TypeError, ValueError):
            raise ValueError("replicate_support requires explicit integer min_replicates")
        if not 2 <= support_threshold <= count:
            raise ValueError(f"min_replicates must be between 2 and replicate count {count}")
    else:
        support_threshold = None
        if replicate_mode != "biological" or replicate_policy != "require_premerged":
            raise ValueError("IDR v1 requires premerged biological replicates")
        if count != 2:
            raise ValueError("IDR provider v1 requires exactly two biological replicates")
        if peak_type != "narrow":
            raise ValueError("IDR provider v1 accepts narrowPeak only; broadPeak is not converted")
        if not spec.get("require_same_caller", True):
            raise ValueError("IDR provider v1 requires require_same_caller=true")
        spec["idr_threshold"] = positive_probability(spec.get("idr_threshold"), "idr_threshold")
        rank_metric = str(spec.get("rank_metric") or "").lower()
        if rank_metric not in {"signal_value", "p_value", "q_value"}:
            raise ValueError("IDR requires explicit rank_metric: signal_value, p_value, or q_value")
        spec["rank_metric"] = rank_metric

    first = normalized[0]
    return {
        "schema_version": "1.0", "type": "consensus_idr_request",
        "id": first["group_id"], "strategy": strategy,
        "provider": "idr" if strategy == "idr" else "bedtools_multiinter",
        "provider_version": "2.0.4.2" if strategy == "idr" else "2.31.1",
        "dataset": first["dataset"], "experiment_id": first["experiment_id"],
        "condition": first["condition"], "treatment": first.get("treatment") or None,
        "target": first["target"], "genome_id": first["genome_id"],
        "peak_type": peak_type, "caller": first["caller"],
        "caller_version": first["caller_version"],
        "replicate_mode": replicate_mode, "replicate_policy": replicate_policy,
        "replicate_count": count, "support_threshold": support_threshold,
        "parameters": spec, "replicates": normalized,
        "status": "valid",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--peak-dir", action="append", required=True)
    parser.add_argument("--peak-manifest", action="append", required=True)
    parser.add_argument("--qc-manifest", action="append", required=True)
    parser.add_argument("--records-base64", required=True)
    parser.add_argument("--spec-base64", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        records = json.loads(base64.b64decode(args.records_base64).decode("utf-8"))
        spec = json.loads(base64.b64decode(args.spec_base64).decode("utf-8"))
        if not isinstance(records, list) or not records:
            raise ValueError("records must be a non-empty JSON list")
        request = build_request(records, args.peak_dir, args.peak_manifest, args.qc_manifest, spec)
        for path in (args.request, args.report):
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(request, handle, indent=2, sort_keys=True)
                handle.write("\n")
        print(f"validated {request['strategy']} group {request['id']} with {request['replicate_count']} evidence units")
    except (ValueError, KeyError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
